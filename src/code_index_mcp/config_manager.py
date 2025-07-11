"""
Configuration Manager for Code Index MCP

This module handles loading and managing configuration from YAML files,
including file size and directory filtering settings.
"""
import os
import yaml
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
import fnmatch


class ConfigManager:
    """Manages configuration for the Code Index MCP server."""
    
    def __init__(self, config_path: Optional[str] = None, project_path: Optional[str] = None):
        """Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file. If None, looks for config.yaml
                        in the current directory or project root.
            project_path: Path to the project directory for per-project overrides.
        """
        self.config_path = self._find_config_path(config_path)
        self.project_path = project_path
        self.config = self._load_config()
        self.project_overrides = self._load_project_overrides()
    
    def _find_config_path(self, config_path: Optional[str] = None) -> Optional[str]:
        """Find the configuration file path."""
        if config_path and os.path.exists(config_path):
            return config_path
        
        # Look for config.yaml in common locations
        possible_paths = [
            "config.yaml",
            "config.yml",
            os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml"),
            os.path.join(os.path.dirname(__file__), "..", "..", "config.yml"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return os.path.abspath(path)
        
        return None
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path:
            return self._get_default_config()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config or self._get_default_config()
        except Exception as e:
            print(f"Error loading config from {self.config_path}: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration when no config file is found."""
        return {
            "file_filtering": {
                "max_file_size": 5242880,  # 5MB
                "type_specific_limits": {
                    ".py": 1048576,   # 1MB
                    ".js": 1048576,   # 1MB
                    ".ts": 1048576,   # 1MB
                    ".jsx": 1048576,  # 1MB
                    ".tsx": 1048576,  # 1MB
                    ".java": 1048576, # 1MB
                    ".json": 524288,  # 512KB
                    ".yaml": 524288,  # 512KB
                    ".yml": 524288,   # 512KB
                    ".xml": 524288,   # 512KB
                }
            },
            "directory_filtering": {
                "max_files_per_directory": 1000,
                "max_subdirectories_per_directory": 100,
                "skip_large_directories": [
                    "**/node_modules/**",
                    "**/venv/**",
                    "**/.venv/**",
                    "**/site-packages/**",
                    "**/dist/**",
                    "**/build/**",
                    "**/.git/**",
                    "**/allure-results/**",
                    "**/allure-report/**",
                ]
            },
            "explicit_inclusions": {
                "files": [],
                "directories": [],
                "extensions": []
            },
            "performance": {
                "parallel_processing": False,
                "max_workers": 4,
                "cache_directory_scans": True,
                "log_filtering_decisions": False
            }
        }
    
    def get_max_file_size(self, file_path: str) -> int:
        """Get maximum file size for a specific file."""
        file_filtering = self.config.get("file_filtering", {})
        
        # Check explicit inclusions first
        if self._is_explicitly_included_file(file_path):
            return float('inf')  # No size limit for explicitly included files
        
        # Get file extension
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Check type-specific limits
        type_limits = file_filtering.get("type_specific_limits", {})
        if ext in type_limits:
            return type_limits[ext]
        
        # Return default max size
        return file_filtering.get("max_file_size", 5242880)
    
    def should_skip_file_by_size(self, file_path: str, file_size: int) -> bool:
        """Check if a file should be skipped based on its size."""
        max_size = self.get_max_file_size(file_path)
        return file_size > max_size
    
    def get_max_files_per_directory(self) -> int:
        """Get maximum number of files per directory."""
        return self.config.get("directory_filtering", {}).get("max_files_per_directory", 1000)
    
    def get_max_subdirectories_per_directory(self) -> int:
        """Get maximum number of subdirectories per directory."""
        return self.config.get("directory_filtering", {}).get("max_subdirectories_per_directory", 100)
    
    def should_skip_directory_by_count(self, directory_path: str, file_count: int, subdir_count: int) -> bool:
        """Check if a directory should be skipped based on file/subdirectory count."""
        if self._is_explicitly_included_directory(directory_path):
            return False
        
        max_files = self.get_max_files_per_directory()
        max_subdirs = self.get_max_subdirectories_per_directory()
        
        return file_count > max_files or subdir_count > max_subdirs
    
    def should_skip_directory_by_pattern(self, directory_path: str) -> bool:
        """Check if a directory should be skipped based on patterns."""
        if self._is_explicitly_included_directory(directory_path):
            return False
        
        skip_patterns = self.config.get("directory_filtering", {}).get("skip_large_directories", [])
        
        for pattern in skip_patterns:
            if fnmatch.fnmatch(directory_path, pattern):
                return True
        
        return False
    
    def _is_explicitly_included_file(self, file_path: str) -> bool:
        """Check if a file is explicitly included."""
        inclusions = self.config.get("explicit_inclusions", {})
        
        # Check file patterns
        file_patterns = inclusions.get("files", [])
        for pattern in file_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return True
        
        # Check extensions
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        included_extensions = inclusions.get("extensions", [])
        if ext in included_extensions:
            return True
        
        return False
    
    def _is_explicitly_included_directory(self, directory_path: str) -> bool:
        """Check if a directory is explicitly included."""
        inclusions = self.config.get("explicit_inclusions", {})
        directory_patterns = inclusions.get("directories", [])
        
        for pattern in directory_patterns:
            if fnmatch.fnmatch(directory_path, pattern):
                return True
        
        return False
    
    def should_log_filtering_decisions(self) -> bool:
        """Check if filtering decisions should be logged."""
        return self.config.get("performance", {}).get("log_filtering_decisions", False)
    
    def is_parallel_processing_enabled(self) -> bool:
        """Check if parallel processing is enabled."""
        return self.config.get("performance", {}).get("parallel_processing", False)
    
    def get_max_workers(self) -> int:
        """Get maximum number of workers for parallel processing."""
        return self.config.get("performance", {}).get("max_workers", 4)
    
    def is_directory_scan_caching_enabled(self) -> bool:
        """Check if directory scan caching is enabled."""
        return self.config.get("performance", {}).get("cache_directory_scans", True)
    
    def get_filtering_stats(self) -> Dict[str, Any]:
        """Get statistics about current filtering configuration."""
        return {
            "config_path": self.config_path,
            "has_config_file": self.config_path is not None,
            "file_filtering": {
                "default_max_size": self.config.get("file_filtering", {}).get("max_file_size", 5242880),
                "type_specific_limits_count": len(self.config.get("file_filtering", {}).get("type_specific_limits", {})),
            },
            "directory_filtering": {
                "max_files_per_directory": self.get_max_files_per_directory(),
                "max_subdirectories_per_directory": self.get_max_subdirectories_per_directory(),
                "skip_patterns_count": len(self.config.get("directory_filtering", {}).get("skip_large_directories", [])),
            },
            "explicit_inclusions": {
                "files_count": len(self.config.get("explicit_inclusions", {}).get("files", [])),
                "directories_count": len(self.config.get("explicit_inclusions", {}).get("directories", [])),
                "extensions_count": len(self.config.get("explicit_inclusions", {}).get("extensions", [])),
            },
            "performance": {
                "parallel_processing": self.is_parallel_processing_enabled(),
                "max_workers": self.get_max_workers(),
                "logging_enabled": self.should_log_filtering_decisions(),
            }
        }
    
    def _load_project_overrides(self) -> Dict[str, Any]:
        """Load per-project configuration overrides."""
        if not self.project_path:
            return {}
        
        # Look for project-specific config files
        project_config_paths = [
            os.path.join(self.project_path, ".code-index.yaml"),
            os.path.join(self.project_path, ".code-index.yml"),
            os.path.join(self.project_path, "code-index.yaml"),
            os.path.join(self.project_path, "code-index.yml"),
        ]
        
        for config_path in project_config_paths:
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        overrides = yaml.safe_load(f)
                    print(f"Loaded project overrides from: {config_path}")
                    return overrides or {}
                except Exception as e:
                    print(f"Error loading project overrides from {config_path}: {e}")
        
        return {}
    
    def _merge_config(self, base_config: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Merge project overrides with base configuration."""
        merged = base_config.copy()
        
        def deep_merge(target: Dict[str, Any], source: Dict[str, Any]):
            for key, value in source.items():
                if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                    deep_merge(target[key], value)
                else:
                    target[key] = value
        
        deep_merge(merged, overrides)
        return merged
    
    def get_config(self, key: Optional[str] = None) -> Any:
        """Get configuration value with project overrides applied."""
        merged_config = self._merge_config(self.config, self.project_overrides)
        
        if key is None:
            return merged_config
        
        # Support dot notation for nested keys
        keys = key.split('.')
        value = merged_config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        return value
    
    def get_ignore_patterns(self) -> List[str]:
        """Get ignore patterns from configuration."""
        patterns = self.get_config('ignore_patterns')
        if patterns is None:
            return []
        return patterns if isinstance(patterns, list) else []
    
    def get_size_limits(self) -> Dict[str, Any]:
        """Get size limits from configuration."""
        size_limits = self.get_config('size_limits')
        if size_limits is None:
            return {
                'max_file_size': 1073741824,  # 1GB
                'type_specific_limits': {}
            }
        return size_limits
    
    def get_directory_thresholds(self) -> Dict[str, Any]:
        """Get directory thresholds from configuration."""
        thresholds = self.get_config('directory_thresholds')
        if thresholds is None:
            return {
                'max_files_per_directory': 10000,
                'max_subdirectories_per_directory': 1000
            }
        return thresholds
    
    def get_memory_caps(self) -> Dict[str, Any]:
        """Get memory caps from configuration."""
        memory_caps = self.get_config('memory_caps')
        if memory_caps is None:
            return {
                'soft_limit_mb': 8192,  # 8GB
                'hard_limit_mb': 16384  # 16GB
            }
        return memory_caps
    
    def get_preferred_search_tool(self) -> Optional[str]:
        """Get preferred search tool from configuration."""
        return self.get_config('preferred_search_tool')
    
    def reload_config(self):
        """Reload configuration from file."""
        self.config = self._load_config()
        self.project_overrides = self._load_project_overrides()
