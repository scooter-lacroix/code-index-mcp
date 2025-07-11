# Lazy Loading Implementation Summary

## Overview
Successfully implemented lazy loading of file contents for the Code Index MCP Server. This implementation ensures that file content is only loaded when actually required by analysis/search operations, significantly improving memory efficiency.

## Key Changes Made

### 1. Created Lazy Loading Module (`src/code_index_mcp/lazy_loader.py`)
- **LazyFileContent**: Represents a file whose content is loaded on demand
- **LazyContentManager**: Manages lazy loading with LRU memory management 
- **ChunkedFileReader**: Reads large files in chunks for memory efficiency
- **MemoryMappedFileReader**: Memory-mapped file reader for very large files

### 2. Updated Server Implementation (`src/code_index_mcp/server.py`)
- Replaced `code_content_cache` with `LazyContentManager`
- Updated `get_file_content()` resource to use lazy loading
- Updated `get_file_summary()` tool to use lazy loading
- Added `get_lazy_loading_stats()` tool for monitoring memory usage
- Removed eager content caching from indexing operations

### 3. Memory Management Features
- **LRU Eviction**: Automatically unloads least recently used files when memory limit is exceeded
- **Configurable Limits**: Default limit of 100 loaded files (configurable)
- **Thread-Safe**: Uses locks to ensure thread safety
- **WeakValueDictionary**: Automatic cleanup of unused file references

## Benefits Achieved

### Memory Efficiency
- **Deferred Loading**: File content is only read when actually needed
- **Memory Limits**: Configurable maximum number of loaded files in memory
- **Automatic Cleanup**: LRU eviction prevents memory bloat

### Performance Improvements
- **Faster Indexing**: Index creation only stores metadata (type, path, extension)
- **Reduced Memory Footprint**: Large codebases no longer load all files into memory
- **On-Demand Access**: Content loading happens transparently when accessed

### Monitoring and Control
- **Memory Statistics**: Track loaded files, memory pressure, and total managed files
- **Manual Control**: Ability to unload all cached content
- **Configurable Limits**: Adjust memory limits based on system resources

## Implementation Details

### File Metadata Only in Index
The main index now only stores:
```python
{
    "type": "file",
    "path": "relative/path/to/file.py", 
    "ext": ".py"
}
```

### Lazy Content Loading
```python
# Content is loaded only when accessed
lazy_content = lazy_content_manager.get_file_content(full_path)
content = lazy_content.content  # Triggers loading if not already loaded
```

### Memory Management
- Tracks access order for LRU eviction
- Enforces memory limits when content is loaded
- Provides statistics for monitoring

## Testing
Created comprehensive tests (`test_lazy_loading.py`) that verify:
- ✅ Basic lazy loading functionality
- ✅ Memory management and LRU eviction  
- ✅ File property access without content loading
- ✅ Concurrent access handling

## File Structure Changes
```
src/code_index_mcp/
├── lazy_loader.py          # NEW: Lazy loading implementation
├── server.py               # MODIFIED: Updated to use lazy loading
└── ...                     # Other existing files unchanged
```

## Usage Example
```python
# Get memory statistics
stats = lazy_content_manager.get_memory_stats()
# {
#   'total_managed_files': 150,
#   'loaded_files': 12,
#   'max_loaded_files': 100,
#   'memory_pressure': 0.12
# }

# File content loaded on demand
lazy_content = lazy_content_manager.get_file_content(file_path)
content = lazy_content.content  # Only loads if not already cached

# Check if content is loaded without triggering load
is_loaded = lazy_content.is_content_loaded()
```

## Configuration
The lazy loading behavior can be configured:
- **max_loaded_files**: Maximum number of files to keep in memory (default: 100)
- **Memory management**: Automatic LRU eviction when limit is exceeded
- **Unload control**: Manual unloading of all cached content when needed

This implementation successfully achieves the goal of **deferring file content reading until required by analysis/search operations** while maintaining excellent performance and providing robust memory management capabilities.
