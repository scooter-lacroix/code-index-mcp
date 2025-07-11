# File and Directory Filtering

The Code Index MCP server now includes advanced filtering capabilities to improve performance and accuracy when indexing large projects. This document explains how to configure and use these filtering features.

## Configuration

The filtering behavior is controlled by a `config.yaml` file that should be placed in the project root. If no configuration file is found, sensible defaults are used.

### Configuration File Structure

```yaml
# File size filtering
file_filtering:
  # Maximum file size in bytes (default: 5MB)
  max_file_size: 5242880  # 5MB in bytes
  
  # Maximum file size for different file types (optional overrides)
  type_specific_limits:
    ".py": 1048576    # 1MB for Python files
    ".js": 1048576    # 1MB for JavaScript files
    ".json": 524288   # 512KB for JSON files
    ".md": 10485760   # 10MB for Markdown files

# Directory filtering
directory_filtering:
  # Maximum number of files per directory
  max_files_per_directory: 1000
  
  # Maximum number of subdirectories per directory
  max_subdirectories_per_directory: 100
  
  # Skip directories with these patterns
  skip_large_directories:
    - "**/node_modules/**"
    - "**/venv/**"
    - "**/.venv/**"
    - "**/allure-results/**"
    # ... more patterns

# Explicit inclusions (override size/count limits)
explicit_inclusions:
  files: []       # File patterns to always include
  directories: [] # Directory patterns to always include
  extensions: []  # Extensions to always include

# Performance settings
performance:
  parallel_processing: true
  max_workers: 4
  cache_directory_scans: true
  log_filtering_decisions: false
```

## Filtering Types

### 1. File Size Filtering

Files larger than the configured limits are automatically skipped during indexing:

- **Global limit**: Default maximum file size (5MB)
- **Type-specific limits**: Different limits for different file extensions
- **Explicit inclusions**: Override size limits for specific patterns

**Examples:**
- Python files larger than 1MB are filtered out
- JSON files larger than 512KB are filtered out  
- Markdown files can be up to 10MB
- Unknown file types use the global 5MB limit

### 2. Directory Count Filtering

Directories with too many files or subdirectories are skipped:

- **File count limit**: Skip directories with more than 1000 files
- **Subdirectory limit**: Skip directories with more than 100 subdirectories
- **Explicit inclusions**: Override count limits for specific directory patterns

**Examples:**
- A directory with 2000 Python files would be skipped
- A directory with 150 subdirectories would be skipped
- Node modules directories are typically skipped by pattern anyway

### 3. Pattern-Based Directory Filtering

Certain directory patterns are automatically skipped:

- Build artifacts: `**/dist/**`, `**/build/**`, `**/target/**`
- Dependencies: `**/node_modules/**`, `**/venv/**`, `**/site-packages/**`
- Version control: `**/.git/**`, `**/.svn/**`, `**/.hg/**`
- Test reports: `**/allure-results/**`, `**/coverage/**`
- Cache directories: `**/.cache/**`, `**/.pytest_cache/**`
- Logs: `**/logs/**`, `**/log/**`

## Performance Impact

Based on testing with a large project (45,324 Python files):

### Before Filtering
- **Files indexed**: ~45,000+ files
- **Indexing time**: Very slow (multiple minutes)
- **Memory usage**: High
- **Search performance**: Degraded due to index size

### After Filtering  
- **Files indexed**: Significantly reduced (estimated 5,000-10,000 relevant files)
- **Indexing time**: Fast (seconds)
- **Memory usage**: Optimized
- **Search performance**: Improved due to smaller, more relevant index

### Filtering Statistics
The system provides detailed statistics about what was filtered:
- Number of files indexed
- Number of files filtered by size
- Number of directories filtered by count
- Number of directories filtered by pattern

## Using the Filtering Features

### 1. Check Current Configuration

Use the `get_filtering_config` tool to see current filtering settings:

```python
# This will show:
# - File size limits for different extensions
# - Directory count limits  
# - Performance settings
# - Examples of how files would be filtered
```

### 2. Enable Debug Logging

Set `log_filtering_decisions: true` in the performance section to see detailed logs about what is being filtered and why.

### 3. Custom Configuration

Create or modify `config.yaml` in your project root to customize filtering behavior:

```yaml
file_filtering:
  max_file_size: 2097152  # 2MB instead of 5MB
  type_specific_limits:
    ".py": 524288         # 512KB for Python files
    
directory_filtering:
  max_files_per_directory: 500  # Stricter limit
  
performance:
  log_filtering_decisions: true  # Enable debug logging
```

### 4. Explicit Inclusions

Override filtering for specific files or directories:

```yaml
explicit_inclusions:
  files:
    - "important_large_file.py"  # Always include this file
  directories:
    - "critical_large_dir"       # Always include this directory
  extensions:
    - ".critical"                # Always include this extension
```

## Default Configuration

If no `config.yaml` is found, the system uses these defaults:

- **Global file size limit**: 5MB
- **Python/JS/TS files**: 1MB limit
- **JSON/YAML/XML files**: 512KB limit
- **Markdown/text files**: 10MB limit
- **Max files per directory**: 1000
- **Max subdirectories**: 100
- **Common skip patterns**: node_modules, venv, build directories, etc.

## Best Practices

1. **Start with defaults**: The default configuration works well for most projects
2. **Enable logging**: Use `log_filtering_decisions: true` to understand what's being filtered
3. **Customize gradually**: Adjust limits based on your project's specific needs
4. **Use explicit inclusions**: For important files that exceed size limits
5. **Monitor performance**: Check indexing statistics to ensure optimal filtering

## Troubleshooting

### Important Files Being Filtered

- Add them to `explicit_inclusions.files`
- Increase the size limit for their file type
- Check if their directory is being filtered by count

### Too Many Files Being Filtered

- Increase file size limits
- Increase directory count limits  
- Remove patterns from `skip_large_directories`

### Slow Indexing

- Decrease file size limits
- Decrease directory count limits
- Add more patterns to `skip_large_directories`
- Enable parallel processing

The filtering system is designed to significantly improve performance while maintaining accuracy by focusing on the most relevant code files.
