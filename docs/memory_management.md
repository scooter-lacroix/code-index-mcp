# Memory Management and Profiling System

## Overview

The Code Index MCP Server now includes a comprehensive memory management and profiling system that tracks peak usage, enforces soft and hard limits on heap growth, and triggers cleanup or spill-to-disk mechanisms when thresholds are exceeded.

## Features

### 1. Memory Profiling and Tracking

- **Real-time monitoring**: Continuous tracking of process memory usage, heap size, and garbage collection statistics
- **Peak memory tracking**: Records and maintains the highest memory usage reached
- **Snapshot system**: Regular memory snapshots with timestamps for historical analysis
- **Process metrics**: Tracks active threads, loaded files, and cached queries

### 2. Memory Limits and Thresholds

The system supports multiple configurable limits:

- **Soft Limit**: Triggers cleanup when exceeded (default: 512MB)
- **Hard Limit**: Triggers aggressive cleanup (default: 1024MB)
- **GC Threshold**: Triggers garbage collection (default: 256MB)
- **Spill Threshold**: Triggers spill-to-disk operations (default: 768MB)
- **Max Loaded Files**: Limits number of files kept in memory (default: 100)
- **Max Cached Queries**: Limits number of cached search results (default: 50)

### 3. Automatic Cleanup Mechanisms

When memory limits are exceeded, the system automatically:

1. **Garbage Collection**: Forces Python garbage collection to free unreferenced objects
2. **Content Cleanup**: Unloads file content from least recently used files
3. **Cache Cleanup**: Clears query result caches
4. **Spill to Disk**: Saves cached data to temporary files on disk
5. **Aggressive Cleanup**: Unloads all content when hard limits are exceeded

### 4. Spill-to-Disk System

- **Automatic spilling**: Query results and other data can be saved to disk when memory is low
- **Transparent recovery**: Spilled data is automatically loaded back when needed
- **Cleanup on exit**: Temporary spill files are cleaned up on server shutdown

## Configuration

### YAML Configuration

Memory management is configured in `config.yaml` under the `memory` section:

```yaml
memory:
  # Soft memory limit in MB (triggers cleanup)
  soft_limit_mb: 512.0
  
  # Hard memory limit in MB (triggers aggressive cleanup)
  hard_limit_mb: 1024.0
  
  # Maximum number of files to keep loaded in memory
  max_loaded_files: 100
  
  # Maximum number of cached search queries
  max_cached_queries: 50
  
  # Memory threshold for triggering garbage collection (MB)
  gc_threshold_mb: 256.0
  
  # Memory threshold for spilling data to disk (MB)
  spill_threshold_mb: 768.0
  
  # Enable continuous memory monitoring
  enable_monitoring: true
  
  # Memory monitoring interval in seconds
  monitoring_interval: 30.0
  
  # Enable memory profiling and export
  enable_profiling: true
  
  # Export memory profile on shutdown
  export_profile_on_shutdown: true
```

## Available Tools

The system provides several MCP tools for memory management:

### 1. `get_memory_profile()`
Returns comprehensive memory statistics including:
- Current memory usage and peak usage
- Memory snapshots history
- Garbage collection statistics
- Loaded files and cached queries count
- Memory violations and limit status

### 2. `trigger_memory_cleanup()`
Manually triggers memory cleanup operations:
- Unloads file content from memory
- Clears query caches
- Forces garbage collection
- Returns before/after statistics

### 3. `configure_memory_limits()`
Dynamically updates memory limits at runtime:
- `soft_limit_mb`: Set soft memory limit
- `hard_limit_mb`: Set hard memory limit  
- `max_loaded_files`: Set maximum loaded files
- `max_cached_queries`: Set maximum cached queries

### 4. `export_memory_profile(file_path?)`
Exports detailed memory profile to a JSON file:
- All memory snapshots with timestamps
- Comprehensive statistics
- Configuration and limit information
- Optional custom file path

## Integration with Existing Systems

### Lazy Content Manager Integration

The memory profiler integrates seamlessly with the existing `LazyContentManager`:

- **Memory-aware content management**: File content is automatically unloaded when memory limits are approached
- **LRU eviction**: Least recently used files are unloaded first
- **Query cache management**: Search query caches are automatically managed and can be spilled to disk

### Automatic Initialization

The memory profiler is automatically initialized when a project path is set:

1. Loads configuration from `config.yaml`
2. Creates memory profiler with specified limits
3. Sets up memory-aware content manager
4. Starts continuous monitoring if enabled

## Memory Monitoring

### Continuous Monitoring

When enabled, the system continuously monitors memory usage at configurable intervals (default: 30 seconds) and automatically:

- Takes memory snapshots
- Checks for limit violations
- Triggers appropriate cleanup actions
- Logs memory events

### Manual Monitoring

Use the `get_memory_profile()` tool to get real-time memory statistics at any time.

## Best Practices

### 1. Configuration Tuning

- Set `soft_limit_mb` to about 50% of available system memory
- Set `hard_limit_mb` to about 75% of available system memory
- Adjust `max_loaded_files` based on typical file sizes in your projects
- Use shorter `monitoring_interval` for memory-constrained environments

### 2. Performance Considerations

- Memory cleanup operations may cause brief performance impacts
- Spill-to-disk operations involve I/O overhead
- Consider disabling monitoring in production if not needed

### 3. Debugging Memory Issues

- Enable `export_profile_on_shutdown` to analyze memory usage patterns
- Use `get_memory_profile()` to monitor memory during heavy operations
- Check spill directory (`/tmp/code_index_mcp_spill/`) for persistent spilled data

## Technical Implementation

### Core Components

1. **`MemoryProfiler`**: Main profiling and limit enforcement engine
2. **`MemorySnapshot`**: Data structure for memory state at a point in time
3. **`MemoryLimits`**: Configuration data structure for all limits
4. **`MemoryAwareLazyContentManager`**: Integration with lazy loading system
5. **`MemoryAwareManager`**: Base class for memory-aware components

### Memory Tracking

The profiler uses Python's `psutil` library to track:
- Process RSS (Resident Set Size) memory
- Python object count via `gc.get_objects()`
- Garbage collection statistics
- Thread count and other process metrics

### Cleanup Callbacks

The system uses a callback-based architecture where components register cleanup functions that are automatically called when memory limits are exceeded.

## Troubleshooting

### Common Issues

1. **Memory limits too low**: Adjust `soft_limit_mb` and `hard_limit_mb` upward
2. **Frequent cleanup operations**: Increase `max_loaded_files` or reduce file sizes
3. **Spill files accumulating**: Check cleanup on shutdown and manual cleanup calls
4. **Performance degradation**: Increase monitoring interval or disable continuous monitoring

### Debug Commands

```bash
# Check current memory usage
get_memory_profile()

# Force cleanup
trigger_memory_cleanup()

# Export detailed profile
export_memory_profile("/tmp/memory_debug.json")
```

## Future Enhancements

Potential improvements include:

- Memory usage prediction based on file sizes
- Compression of spilled data
- Memory pool management
- Integration with external monitoring systems
- Custom cleanup strategies per file type
