"""
Memory Profiler and Management System

This module provides comprehensive memory tracking, profiling, and enforcement
of memory limits with cleanup and spill-to-disk capabilities.
"""

import gc
import os
import sys
import time
import psutil
import tempfile
import threading
import pickle
import json
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import deque
from threading import Lock, Event
import weakref
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """Represents a memory usage snapshot at a point in time."""
    timestamp: float
    process_memory_mb: float
    heap_size_mb: float
    peak_memory_mb: float
    gc_objects: int
    gc_collections: Tuple[int, int, int]  # gen0, gen1, gen2 collections
    active_threads: int
    loaded_files: int
    cached_queries: int


@dataclass
class MemoryLimits:
    """Memory limits configuration."""
    soft_limit_mb: float = 512.0  # 512MB soft limit
    hard_limit_mb: float = 1024.0  # 1GB hard limit
    max_loaded_files: int = 100
    max_cached_queries: int = 50
    gc_threshold_mb: float = 256.0  # Trigger GC at 256MB
    spill_threshold_mb: float = 768.0  # Spill to disk at 768MB


class MemoryProfiler:
    """Memory profiler that tracks peak usage and enforces limits."""
    
    def __init__(self, limits: Optional[MemoryLimits] = None):
        self.limits = limits or MemoryLimits()
        self.snapshots: deque = deque(maxlen=100)  # Keep last 100 snapshots
        self.peak_memory_mb = 0.0
        self.start_time = time.time()
        self.process = psutil.Process()
        self._lock = Lock()
        self._monitoring = False
        self._monitor_thread = None
        self._shutdown_event = Event()
        
        # Callbacks for memory events
        self.cleanup_callbacks: List[Callable] = []
        self.spill_callbacks: List[Callable] = []
        self.limit_exceeded_callbacks: List[Callable] = []
        
        # Spill storage
        self.spill_dir = Path(tempfile.gettempdir()) / "code_index_mcp_spill"
        self.spill_dir.mkdir(exist_ok=True)
        self.spilled_data: Dict[str, str] = {}  # key -> file_path mapping
        
        # Initialize baseline memory usage
        self._baseline_memory = self._get_memory_usage()
        
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            memory_info = self.process.memory_info()
            return memory_info.rss / 1024 / 1024  # Convert to MB
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0
    
    def _get_heap_size(self) -> float:
        """Estimate heap size in MB."""
        try:
            # Get object count and estimate size
            objects = gc.get_objects()
            total_size = sum(sys.getsizeof(obj) for obj in objects[:1000])  # Sample first 1000
            estimated_total = (total_size / 1000) * len(objects)
            return estimated_total / 1024 / 1024  # Convert to MB
        except Exception:
            return 0.0
    
    def _get_gc_stats(self) -> Tuple[int, int, int]:
        """Get garbage collection statistics."""
        try:
            stats = gc.get_stats()
            return (
                stats[0]['collections'] if len(stats) > 0 else 0,
                stats[1]['collections'] if len(stats) > 1 else 0,
                stats[2]['collections'] if len(stats) > 2 else 0
            )
        except Exception:
            return (0, 0, 0)
    
    def take_snapshot(self, loaded_files: int = 0, cached_queries: int = 0) -> MemorySnapshot:
        """Take a memory snapshot."""
        current_memory = self._get_memory_usage()
        heap_size = self._get_heap_size()
        
        # Update peak memory
        if current_memory > self.peak_memory_mb:
            self.peak_memory_mb = current_memory
        
        snapshot = MemorySnapshot(
            timestamp=time.time(),
            process_memory_mb=current_memory,
            heap_size_mb=heap_size,
            peak_memory_mb=self.peak_memory_mb,
            gc_objects=len(gc.get_objects()),
            gc_collections=self._get_gc_stats(),
            active_threads=threading.active_count(),
            loaded_files=loaded_files,
            cached_queries=cached_queries
        )
        
        with self._lock:
            self.snapshots.append(snapshot)
        
        return snapshot
    
    def check_limits(self, snapshot: MemorySnapshot) -> Dict[str, bool]:
        """Check if memory limits are exceeded."""
        violations = {
            'soft_limit': snapshot.process_memory_mb > self.limits.soft_limit_mb,
            'hard_limit': snapshot.process_memory_mb > self.limits.hard_limit_mb,
            'gc_threshold': snapshot.process_memory_mb > self.limits.gc_threshold_mb,
            'spill_threshold': snapshot.process_memory_mb > self.limits.spill_threshold_mb,
            'max_loaded_files': snapshot.loaded_files > self.limits.max_loaded_files,
            'max_cached_queries': snapshot.cached_queries > self.limits.max_cached_queries
        }
        
        return violations
    
    def enforce_limits(self, snapshot: MemorySnapshot) -> Dict[str, Any]:
        """Enforce memory limits and trigger appropriate actions."""
        violations = self.check_limits(snapshot)
        actions_taken = {
            'garbage_collection': False,
            'cleanup_triggered': False,
            'spill_triggered': False,
            'limit_exceeded': False
        }
        
        # Trigger garbage collection
        if violations['gc_threshold']:
            logger.info(f"Triggering garbage collection at {snapshot.process_memory_mb:.2f}MB")
            collected = gc.collect()
            actions_taken['garbage_collection'] = True
            logger.info(f"Garbage collection freed {collected} objects")
        
        # Trigger cleanup
        if violations['soft_limit'] or violations['max_loaded_files'] or violations['max_cached_queries']:
            logger.info(f"Triggering cleanup at {snapshot.process_memory_mb:.2f}MB")
            self._trigger_cleanup()
            actions_taken['cleanup_triggered'] = True
        
        # Trigger spill to disk
        if violations['spill_threshold']:
            logger.info(f"Triggering spill to disk at {snapshot.process_memory_mb:.2f}MB")
            self._trigger_spill()
            actions_taken['spill_triggered'] = True
        
        # Hard limit exceeded
        if violations['hard_limit']:
            logger.warning(f"Hard memory limit exceeded: {snapshot.process_memory_mb:.2f}MB")
            self._trigger_limit_exceeded()
            actions_taken['limit_exceeded'] = True
        
        return actions_taken
    
    def _trigger_cleanup(self):
        """Trigger cleanup callbacks."""
        for callback in self.cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in cleanup callback: {e}")
    
    def _trigger_spill(self):
        """Trigger spill to disk callbacks."""
        for callback in self.spill_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in spill callback: {e}")
    
    def _trigger_limit_exceeded(self):
        """Trigger limit exceeded callbacks."""
        for callback in self.limit_exceeded_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in limit exceeded callback: {e}")
    
    def spill_to_disk(self, key: str, data: Any) -> bool:
        """Spill data to disk and return success status."""
        try:
            spill_file = self.spill_dir / f"{key}.pkl"
            with open(spill_file, 'wb') as f:
                pickle.dump(data, f)
            self.spilled_data[key] = str(spill_file)
            logger.info(f"Spilled data for key '{key}' to {spill_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to spill data for key '{key}': {e}")
            return False
    
    def load_from_disk(self, key: str) -> Optional[Any]:
        """Load spilled data from disk."""
        if key not in self.spilled_data:
            return None
        
        try:
            spill_file = Path(self.spilled_data[key])
            if not spill_file.exists():
                del self.spilled_data[key]
                return None
            
            with open(spill_file, 'rb') as f:
                data = pickle.load(f)
            logger.info(f"Loaded spilled data for key '{key}' from {spill_file}")
            return data
        except Exception as e:
            logger.error(f"Failed to load spilled data for key '{key}': {e}")
            return None
    
    def cleanup_spill_files(self):
        """Clean up spilled files."""
        for key, file_path in list(self.spilled_data.items()):
            try:
                Path(file_path).unlink(missing_ok=True)
                del self.spilled_data[key]
            except Exception as e:
                logger.error(f"Failed to cleanup spill file {file_path}: {e}")
    
    def start_monitoring(self, interval: float = 30.0):
        """Start continuous memory monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._shutdown_event.clear()
        
        def monitor_loop():
            while not self._shutdown_event.wait(interval):
                try:
                    snapshot = self.take_snapshot()
                    self.enforce_limits(snapshot)
                except Exception as e:
                    logger.error(f"Error in memory monitoring: {e}")
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring with {interval}s interval")
    
    def stop_monitoring(self):
        """Stop continuous memory monitoring."""
        if not self._monitoring:
            return
        
        self._monitoring = False
        self._shutdown_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        logger.info("Stopped memory monitoring")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics."""
        current_memory = self._get_memory_usage()
        heap_size = self._get_heap_size()
        
        with self._lock:
            recent_snapshots = list(self.snapshots)[-10:]  # Last 10 snapshots
        
        return {
            'current_memory_mb': current_memory,
            'peak_memory_mb': self.peak_memory_mb,
            'heap_size_mb': heap_size,
            'baseline_memory_mb': self._baseline_memory,
            'memory_growth_mb': current_memory - self._baseline_memory,
            'limits': asdict(self.limits),
            'violations': self.check_limits(self.take_snapshot()),
            'monitoring_active': self._monitoring,
            'snapshots_count': len(self.snapshots),
            'recent_snapshots': [asdict(s) for s in recent_snapshots],
            'spilled_items': len(self.spilled_data),
            'spill_directory': str(self.spill_dir),
            'gc_stats': self._get_gc_stats(),
            'uptime_seconds': time.time() - self.start_time
        }
    
    def register_cleanup_callback(self, callback: Callable):
        """Register a callback to be called when cleanup is needed."""
        self.cleanup_callbacks.append(callback)
    
    def register_spill_callback(self, callback: Callable):
        """Register a callback to be called when spill is needed."""
        self.spill_callbacks.append(callback)
    
    def register_limit_exceeded_callback(self, callback: Callable):
        """Register a callback to be called when hard limits are exceeded."""
        self.limit_exceeded_callbacks.append(callback)
    
    def export_profile(self, file_path: str):
        """Export memory profile to a file."""
        try:
            profile_data = {
                'stats': self.get_stats(),
                'all_snapshots': [asdict(s) for s in self.snapshots]
            }
            
            with open(file_path, 'w') as f:
                json.dump(profile_data, f, indent=2)
            
            logger.info(f"Memory profile exported to {file_path}")
        except Exception as e:
            logger.error(f"Failed to export memory profile: {e}")
    
    def __del__(self):
        """Cleanup on destruction."""
        self.stop_monitoring()
        self.cleanup_spill_files()


class MemoryAwareManager:
    """Base class for memory-aware managers that integrate with the profiler."""
    
    def __init__(self, profiler: MemoryProfiler):
        self.profiler = profiler
        self.profiler.register_cleanup_callback(self.cleanup)
        self.profiler.register_spill_callback(self.spill_to_disk)
        self.profiler.register_limit_exceeded_callback(self.handle_limit_exceeded)
    
    def cleanup(self):
        """Override in subclasses to implement cleanup logic."""
        pass
    
    def spill_to_disk(self):
        """Override in subclasses to implement spill logic."""
        pass
    
    def handle_limit_exceeded(self):
        """Override in subclasses to handle hard limit exceeded."""
        pass


class MemoryAwareLazyContentManager(MemoryAwareManager):
    """Memory-aware version of LazyContentManager."""
    
    def __init__(self, profiler: MemoryProfiler, lazy_content_manager):
        super().__init__(profiler)
        self.lazy_content_manager = lazy_content_manager
        self._spill_lock = Lock()
    
    def cleanup(self):
        """Clean up loaded content to reduce memory usage."""
        logger.info("Cleaning up loaded file content")
        
        # Get memory stats before cleanup
        stats_before = self.lazy_content_manager.get_memory_stats()
        
        # Unload content from least recently used files
        with self.lazy_content_manager._lock:
            loaded_files = [
                (path, lc) for path, lc in self.lazy_content_manager._loaded_files.items()
                if lc.is_content_loaded()
            ]
            
            # Unload half of the loaded files
            files_to_unload = len(loaded_files) // 2
            for i in range(files_to_unload):
                if i < len(self.lazy_content_manager._access_order):
                    path = self.lazy_content_manager._access_order[i]
                    if path in self.lazy_content_manager._loaded_files:
                        self.lazy_content_manager._loaded_files[path].unload_content()
        
        # Clear query cache
        self.lazy_content_manager.query_cache.cache.clear()
        
        # Force garbage collection
        gc.collect()
        
        # Get memory stats after cleanup
        stats_after = self.lazy_content_manager.get_memory_stats()
        
        logger.info(f"Cleanup completed: {stats_before['loaded_files']} -> {stats_after['loaded_files']} loaded files")
    
    def spill_to_disk(self):
        """Spill cached query results to disk."""
        with self._spill_lock:
            logger.info("Spilling query cache to disk")
            
            # Spill query cache to disk
            cache_items = list(self.lazy_content_manager.query_cache.cache.items())
            if cache_items:
                spill_key = f"query_cache_{int(time.time())}"
                if self.profiler.spill_to_disk(spill_key, cache_items):
                    self.lazy_content_manager.query_cache.cache.clear()
                    logger.info(f"Spilled {len(cache_items)} query cache items to disk")
    
    def handle_limit_exceeded(self):
        """Handle hard memory limit exceeded."""
        logger.warning("Hard memory limit exceeded - performing aggressive cleanup")
        
        # Aggressive cleanup: unload all content
        self.lazy_content_manager.unload_all()
        
        # Clear all caches
        self.lazy_content_manager.query_cache.cache.clear()
        
        # Force garbage collection
        gc.collect()
        
        logger.warning("Aggressive cleanup completed")


def create_memory_config_from_yaml(config_data: Dict[str, Any]) -> MemoryLimits:
    """Create memory limits configuration from YAML data."""
    memory_config = config_data.get('memory', {})
    
    return MemoryLimits(
        soft_limit_mb=memory_config.get('soft_limit_mb', 512.0),
        hard_limit_mb=memory_config.get('hard_limit_mb', 1024.0),
        max_loaded_files=memory_config.get('max_loaded_files', 100),
        max_cached_queries=memory_config.get('max_cached_queries', 50),
        gc_threshold_mb=memory_config.get('gc_threshold_mb', 256.0),
        spill_threshold_mb=memory_config.get('spill_threshold_mb', 768.0)
    )
