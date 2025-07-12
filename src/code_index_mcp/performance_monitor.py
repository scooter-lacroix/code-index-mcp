"""
Performance Monitoring and Metrics System

This module provides comprehensive performance monitoring for indexing and search operations,
including timers, counters, structured logging, and metrics export capabilities.
"""

import time
import json
import logging
import threading
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, asdict, field
from collections import defaultdict, deque
from contextlib import contextmanager
from pathlib import Path
import os
from datetime import datetime


@dataclass
class OperationMetrics:
    """Metrics for a single operation."""
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self, success: bool = True, error_message: Optional[str] = None, **metadata):
        """Mark operation as finished."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success
        self.error_message = error_message
        self.metadata.update(metadata)


@dataclass
class Counter:
    """Thread-safe counter for metrics."""
    name: str
    value: int = 0
    description: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        self._lock = threading.Lock()
    
    def increment(self, amount: int = 1):
        """Increment counter by amount."""
        with self._lock:
            self.value += amount
    
    def decrement(self, amount: int = 1):
        """Decrement counter by amount."""
        with self._lock:
            self.value -= amount
    
    def reset(self):
        """Reset counter to zero."""
        with self._lock:
            self.value = 0
    
    def get_value(self) -> int:
        """Get current counter value."""
        with self._lock:
            return self.value


@dataclass
class Histogram:
    """Thread-safe histogram for timing data."""
    name: str
    buckets: List[float] = field(default_factory=lambda: [0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 1000.0])
    values: List[float] = field(default_factory=list)
    description: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        self._lock = threading.Lock()
        self.bucket_counts = [0] * len(self.buckets)
        self.total_count = 0
        self.sum_value = 0.0
    
    def observe(self, value: float):
        """Add a value to the histogram."""
        with self._lock:
            self.values.append(value)
            self.total_count += 1
            self.sum_value += value
            
            # Update bucket counts
            for i, bucket in enumerate(self.buckets):
                if value <= bucket:
                    self.bucket_counts[i] += 1
    
    def get_percentile(self, percentile: float) -> float:
        """Get percentile value."""
        with self._lock:
            if not self.values:
                return 0.0
            sorted_values = sorted(self.values)
            index = int(len(sorted_values) * percentile / 100.0)
            return sorted_values[min(index, len(sorted_values) - 1)]
    
    def get_average(self) -> float:
        """Get average value."""
        with self._lock:
            return self.sum_value / self.total_count if self.total_count > 0 else 0.0


class PerformanceMonitor:
    """Main performance monitoring class."""
    
    def __init__(self, enable_logging: bool = True, log_level: str = "INFO"):
        self.counters: Dict[str, Counter] = {}
        self.histograms: Dict[str, Histogram] = {}
        self.active_operations: Dict[str, OperationMetrics] = {}
        self.completed_operations: deque = deque(maxlen=1000)  # Keep last 1000 operations
        self._lock = threading.Lock()
        
        # Configure logging
        self.enable_logging = enable_logging
        self.logger = logging.getLogger(f"{__name__}.PerformanceMonitor")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Structured logging formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        # Metrics collection state
        self._metrics_collection_enabled = True
        self._start_time = time.time()
        
        # Initialize common counters
        self.register_counter("indexing_operations_total", "Total number of indexing operations")
        self.register_counter("indexing_files_processed_total", "Total number of files processed during indexing")
        self.register_counter("indexing_errors_total", "Total number of indexing errors")
        self.register_counter("search_operations_total", "Total number of search operations")
        self.register_counter("search_cache_hits_total", "Total number of search cache hits")
        self.register_counter("search_cache_misses_total", "Total number of search cache misses")
        self.register_counter("search_errors_total", "Total number of search errors")
        self.register_counter("memory_cleanup_operations_total", "Total number of memory cleanup operations")
        
        # Initialize common histograms
        self.register_histogram("indexing_operation_duration_ms", "Duration of indexing operations in milliseconds")
        self.register_histogram("search_operation_duration_ms", "Duration of search operations in milliseconds")
        self.register_histogram("file_processing_duration_ms", "Duration of individual file processing in milliseconds")
        self.register_histogram("memory_usage_mb", "Memory usage in megabytes")
    
    def register_counter(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None) -> Counter:
        """Register a new counter."""
        with self._lock:
            if name not in self.counters:
                self.counters[name] = Counter(name, description=description, labels=labels or {})
            return self.counters[name]
    
    def register_histogram(self, name: str, description: str = "", buckets: Optional[List[float]] = None, labels: Optional[Dict[str, str]] = None) -> Histogram:
        """Register a new histogram."""
        with self._lock:
            if name not in self.histograms:
                self.histograms[name] = Histogram(name, buckets=buckets or [], description=description, labels=labels or {})
            return self.histograms[name]
    
    def get_counter(self, name: str) -> Optional[Counter]:
        """Get a counter by name."""
        return self.counters.get(name)
    
    def get_histogram(self, name: str) -> Optional[Histogram]:
        """Get a histogram by name."""
        return self.histograms.get(name)
    
    def increment_counter(self, name: str, amount: int = 1, labels: Optional[Dict[str, str]] = None):
        """Increment a counter."""
        counter = self.get_counter(name)
        if counter:
            counter.increment(amount)
            if self.enable_logging:
                self.logger.debug(f"Counter {name} incremented by {amount}, new value: {counter.get_value()}")
    
    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Add a value to a histogram."""
        histogram = self.get_histogram(name)
        if histogram:
            histogram.observe(value)
            if self.enable_logging:
                self.logger.debug(f"Histogram {name} observed value: {value}")
    
    @contextmanager
    def time_operation(self, operation_name: str, **metadata):
        """Context manager for timing operations."""
        operation_id = f"{operation_name}_{int(time.time() * 1000000)}"
        operation = OperationMetrics(operation_name, time.time(), metadata=metadata)
        
        with self._lock:
            self.active_operations[operation_id] = operation
        
        try:
            yield operation
            operation.finish(success=True)
            
            # Log successful operation
            if self.enable_logging:
                # Safely get duration_ms after finish() is called
                duration = getattr(operation, 'duration_ms', 0) or 0
                self.logger.info(
                    f"Operation completed successfully",
                    extra={
                        "operation_name": operation_name,
                        "duration_ms": duration,
                        "metadata": metadata
                    }
                )
            
            # Update metrics
            duration = getattr(operation, 'duration_ms', 0) or 0
            self.observe_histogram(f"{operation_name}_duration_ms", duration)
            self.increment_counter(f"{operation_name}_operations_total")
            
        except Exception as e:
            operation.finish(success=False, error_message=str(e))
            
            # Log failed operation
            if self.enable_logging:
                # Safely get duration_ms after finish() is called
                duration = getattr(operation, 'duration_ms', 0) or 0
                self.logger.error(
                    f"Operation failed",
                    extra={
                        "operation_name": operation_name,
                        "duration_ms": duration,
                        "error_message": str(e),
                        "metadata": metadata
                    },
                    exc_info=True
                )
            
            # Update error metrics
            self.increment_counter(f"{operation_name}_errors_total")
            raise
        
        finally:
            with self._lock:
                if operation_id in self.active_operations:
                    del self.active_operations[operation_id]
                self.completed_operations.append(operation)
    
    def start_operation(self, operation_name: str, **metadata) -> str:
        """Start a new operation and return its ID."""
        operation_id = f"{operation_name}_{int(time.time() * 1000000)}"
        operation = OperationMetrics(operation_name, time.time(), metadata=metadata)
        
        with self._lock:
            self.active_operations[operation_id] = operation
        
        if self.enable_logging:
            self.logger.info(
                f"Operation started",
                extra={
                    "operation_name": operation_name,
                    "operation_id": operation_id,
                    "metadata": metadata
                }
            )
        
        return operation_id
    
    def finish_operation(self, operation_id: str, success: bool = True, error_message: Optional[str] = None, **metadata):
        """Finish an operation by ID."""
        with self._lock:
            operation = self.active_operations.get(operation_id)
            if not operation:
                return
            
            operation.finish(success=success, error_message=error_message, **metadata)
            del self.active_operations[operation_id]
            self.completed_operations.append(operation)
        
        # Log operation completion
        if self.enable_logging:
            # Safely get duration_ms
            duration = getattr(operation, 'duration_ms', 0) or 0
            if success:
                self.logger.info(
                    f"Operation completed successfully",
                    extra={
                        "operation_name": operation.operation_name,
                        "operation_id": operation_id,
                        "duration_ms": duration,
                        "metadata": operation.metadata
                    }
                )
            else:
                self.logger.error(
                    f"Operation failed",
                    extra={
                        "operation_name": operation.operation_name,
                        "operation_id": operation_id,
                        "duration_ms": duration,
                        "error_message": error_message,
                        "metadata": operation.metadata
                    }
                )
        
        # Update metrics
        duration = getattr(operation, 'duration_ms', 0) or 0
        self.observe_histogram(f"{operation.operation_name}_duration_ms", duration)
        if success:
            self.increment_counter(f"{operation.operation_name}_operations_total")
        else:
            self.increment_counter(f"{operation.operation_name}_errors_total")
    
    def log_structured(self, level: str, message: str, **extra_data):
        """Log a structured message with extra data."""
        if not self.enable_logging:
            return
        
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message, extra=extra_data)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        with self._lock:
            counter_data = {}
            for name, counter in self.counters.items():
                counter_data[name] = {
                    "value": counter.get_value(),
                    "description": counter.description,
                    "labels": counter.labels
                }
            
            histogram_data = {}
            for name, histogram in self.histograms.items():
                histogram_data[name] = {
                    "count": histogram.total_count,
                    "sum": histogram.sum_value,
                    "average": histogram.get_average(),
                    "p50": histogram.get_percentile(50),
                    "p95": histogram.get_percentile(95),
                    "p99": histogram.get_percentile(99),
                    "description": histogram.description,
                    "labels": histogram.labels
                }
            
            active_ops = len(self.active_operations)
            completed_ops = len(self.completed_operations)
            
            return {
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": time.time() - self._start_time,
                "counters": counter_data,
                "histograms": histogram_data,
                "operations": {
                    "active": active_ops,
                    "completed": completed_ops
                }
            }
    
    def export_metrics_json(self, file_path: Optional[str] = None) -> str:
        """Export metrics to JSON format."""
        metrics = self.get_metrics_summary()
        json_data = json.dumps(metrics, indent=2)
        
        if file_path:
            with open(file_path, 'w') as f:
                f.write(json_data)
            self.logger.info(f"Metrics exported to {file_path}")
        
        return json_data
    
    def export_metrics_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        # Add metadata
        lines.append(f"# HELP performance_monitor_uptime_seconds Uptime of the performance monitor")
        lines.append(f"# TYPE performance_monitor_uptime_seconds gauge")
        lines.append(f"performance_monitor_uptime_seconds {time.time() - self._start_time}")
        lines.append("")
        
        # Export counters
        for name, counter in self.counters.items():
            lines.append(f"# HELP {name} {counter.description}")
            lines.append(f"# TYPE {name} counter")
            
            labels_str = ""
            if counter.labels:
                label_parts = [f'{k}="{v}"' for k, v in counter.labels.items()]
                labels_str = "{" + ",".join(label_parts) + "}"
            
            lines.append(f"{name}{labels_str} {counter.get_value()}")
            lines.append("")
        
        # Export histograms
        for name, histogram in self.histograms.items():
            lines.append(f"# HELP {name} {histogram.description}")
            lines.append(f"# TYPE {name} histogram")
            
            labels_str = ""
            if histogram.labels:
                label_parts = [f'{k}="{v}"' for k, v in histogram.labels.items()]
                labels_str = "{" + ",".join(label_parts) + "}"
            
            # Export bucket counts
            for i, bucket in enumerate(histogram.buckets):
                bucket_labels = labels_str.rstrip("}") + f',le="{bucket}"' + "}" if labels_str else f'{{le="{bucket}"}}'
                lines.append(f"{name}_bucket{bucket_labels} {histogram.bucket_counts[i]}")
            
            # Export +Inf bucket
            inf_labels = labels_str.rstrip("}") + ',le="+Inf"' + "}" if labels_str else '{le="+Inf"}'
            lines.append(f"{name}_bucket{inf_labels} {histogram.total_count}")
            
            # Export sum and count
            lines.append(f"{name}_sum{labels_str} {histogram.sum_value}")
            lines.append(f"{name}_count{labels_str} {histogram.total_count}")
            lines.append("")
        
        return "\n".join(lines)
    
    def reset_metrics(self):
        """Reset all metrics."""
        with self._lock:
            for counter in self.counters.values():
                counter.reset()
            
            for histogram in self.histograms.values():
                histogram.values.clear()
                histogram.bucket_counts = [0] * len(histogram.buckets)
                histogram.total_count = 0
                histogram.sum_value = 0.0
            
            self.active_operations.clear()
            self.completed_operations.clear()
        
        self.logger.info("All metrics have been reset")
    
    def get_operation_stats(self) -> Dict[str, Any]:
        """Get statistics about operations."""
        with self._lock:
            completed = list(self.completed_operations)
            active = list(self.active_operations.values())
        
        # Group by operation name
        operation_stats = defaultdict(lambda: {
            "total_count": 0,
            "success_count": 0,
            "error_count": 0,
            "total_duration_ms": 0.0,
            "avg_duration_ms": 0.0,
            "min_duration_ms": float('inf'),
            "max_duration_ms": 0.0
        })
        
        for op in completed:
            stats = operation_stats[op.operation_name]
            stats["total_count"] += 1
            
            if op.success:
                stats["success_count"] += 1
            else:
                stats["error_count"] += 1
            
            if op.duration_ms is not None:
                stats["total_duration_ms"] += op.duration_ms
                stats["min_duration_ms"] = min(stats["min_duration_ms"], op.duration_ms)
                stats["max_duration_ms"] = max(stats["max_duration_ms"], op.duration_ms)
        
        # Calculate averages
        for stats in operation_stats.values():
            if stats["total_count"] > 0:
                stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["total_count"]
                if stats["min_duration_ms"] == float('inf'):
                    stats["min_duration_ms"] = 0.0
        
        return {
            "active_operations": len(active),
            "completed_operations": len(completed),
            "operation_stats": dict(operation_stats)
        }


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def create_performance_monitor_from_config(config: Dict[str, Any]) -> PerformanceMonitor:
    """Create a performance monitor from configuration."""
    monitoring_config = config.get("performance_monitoring", {})
    
    enable_logging = monitoring_config.get("enable_logging", True)
    log_level = monitoring_config.get("log_level", "INFO")
    
    monitor = PerformanceMonitor(enable_logging=enable_logging, log_level=log_level)
    
    # Configure custom counters if specified
    custom_counters = monitoring_config.get("custom_counters", [])
    for counter_config in custom_counters:
        name = counter_config.get("name")
        description = counter_config.get("description", "")
        labels = counter_config.get("labels", {})
        if name:
            monitor.register_counter(name, description, labels)
    
    # Configure custom histograms if specified
    custom_histograms = monitoring_config.get("custom_histograms", [])
    for histogram_config in custom_histograms:
        name = histogram_config.get("name")
        description = histogram_config.get("description", "")
        buckets = histogram_config.get("buckets")
        labels = histogram_config.get("labels", {})
        if name:
            monitor.register_histogram(name, description, buckets, labels)
    
    return monitor
