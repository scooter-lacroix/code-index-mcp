"""
Code Index MCP Server

This MCP server allows LLMs to index, search, and analyze code from a project directory.
It provides tools for file discovery, content retrieval, and code analysis.
"""
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Dict, List, Optional, Tuple, Any
import os
import pathlib
import json
import fnmatch
import sys
import tempfile
import subprocess
import time
import asyncio
from .lazy_loader import LazyContentManager
from mcp.server.fastmcp import FastMCP, Context, Image
from mcp import types

# Import the ProjectSettings class and constants - using relative import
from .optimized_project_settings import OptimizedProjectSettings
from .constants import SETTINGS_DIR
from .ignore_patterns import IgnorePatternMatcher
from .config_manager import ConfigManager
from .incremental_indexer import IncrementalIndexer
from .parallel_processor import ParallelIndexer, IndexingTask, IndexingResult
from .memory_profiler import MemoryProfiler, MemoryLimits, MemoryAwareLazyContentManager, create_memory_config_from_yaml
from .performance_monitor import PerformanceMonitor, get_performance_monitor, create_performance_monitor_from_config
from .progress_tracker import (
    progress_manager, ProgressContext, ProgressTracker, CancellationToken,
    ProgressEventType, OperationStatus, LoggingProgressHandler
)

# Create the MCP server
mcp = FastMCP("CodeIndexer", dependencies=["pathlib"])

# In-memory references (will be loaded from persistent storage)
file_index = {}
lazy_content_manager = LazyContentManager(max_loaded_files=100)

# Global memory profiler - will be initialized when project is set
memory_profiler = None
memory_aware_manager = None

# Global performance monitor - will be initialized when project is set
performance_monitor = None

supported_extensions = [
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
    '.cs', '.go', '.rb', '.php', '.swift', '.kt', '.rs', '.scala', '.sh',
    '.bash', '.html', '.css', '.scss', '.md', '.json', '.xml', '.yml', '.yaml', '.zig',
    # Frontend frameworks
    '.vue', '.svelte', '.mjs', '.cjs',
    # Style languages
    '.less', '.sass', '.stylus', '.styl',
    # Template engines
    '.hbs', '.handlebars', '.ejs', '.pug',
    # Modern frontend
    '.astro', '.mdx',
    # Database and SQL
    '.sql', '.ddl', '.dml', '.mysql', '.postgresql', '.psql', '.sqlite',
    '.mssql', '.oracle', '.ora', '.db2',
    # Database objects
    '.proc', '.procedure', '.func', '.function', '.view', '.trigger', '.index',
    # Database frameworks and tools
    '.migration', '.seed', '.fixture', '.schema',
    # NoSQL and modern databases
    '.cql', '.cypher', '.sparql', '.gql',
    # Database migration tools
    '.liquibase', '.flyway'
]

@dataclass
class CodeIndexerContext:
    """Context for the Code Indexer MCP server."""
    base_path: str
    settings: OptimizedProjectSettings
    file_count: int = 0

@asynccontextmanager
async def indexer_lifespan(server: FastMCP) -> AsyncIterator[CodeIndexerContext]:
    """Manage the lifecycle of the Code Indexer MCP server."""
    # Don't set a default path, user must explicitly set project path
    base_path = ""  # Empty string to indicate no path is set

    print("Initializing Code Indexer MCP server...")

    # Initialize settings manager with skip_load=True to skip loading files
    settings = OptimizedProjectSettings(base_path, skip_load=True, storage_backend='sqlite', use_trie_index=True)

    # Initialize context
    context = CodeIndexerContext(
        base_path=base_path,
        settings=settings
    )

    try:
        print("Server ready. Waiting for user to set project path...")
        # Provide context to the server
        yield context
    finally:
        # Only save index if project path has been set
        if context.base_path and file_index:
            print(f"Saving index for project: {context.base_path}")
            settings.save_index(file_index)

        # Export memory profile on shutdown if configured
        global memory_profiler
        if memory_profiler:
            try:
                config_manager = ConfigManager()
                config_data = config_manager.load_config()
                
                if config_data.get('memory', {}).get('export_profile_on_shutdown', True):
                    import tempfile
                    timestamp = int(time.time())
                    profile_path = os.path.join(tempfile.gettempdir(), f"memory_profile_shutdown_{timestamp}.json")
                    memory_profiler.export_profile(profile_path)
                    print(f"Memory profile exported to: {profile_path}")
                
                # Stop monitoring
                memory_profiler.stop_monitoring()
                print("Memory monitoring stopped")
            except Exception as e:
                print(f"Error during memory profiler shutdown: {e}")

        # Save memory stats for loaded files
        memory_stats = lazy_content_manager.get_memory_stats()
        print(f"Memory Stats: {memory_stats}")

# Initialize the server with our lifespan manager
mcp = FastMCP("CodeIndexer", lifespan=indexer_lifespan)

# ----- RESOURCES -----

@mcp.resource("storage://info")
def get_storage_info() -> str:
    """Get storage information for the current configuration."""
    ctx = mcp.get_context()
    settings = ctx.request_context.lifespan_context.settings
    storage_info = settings.get_storage_info()
    return json.dumps(storage_info, indent=2)

@mcp.resource("config://code-indexer")
def get_config() -> str:
    """Get the current configuration of the Code Indexer."""
    ctx = mcp.get_context()

    # Get the base path from context
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return json.dumps({
            "status": "not_configured",
            "message": "Project path not set. Please use set_project_path to set a project directory first.",
            "supported_extensions": supported_extensions
        }, indent=2)

    # Get file count
    file_count = ctx.request_context.lifespan_context.file_count

    # Get settings stats
    settings = ctx.request_context.lifespan_context.settings
    settings_stats = settings.get_stats()

    config = {
        "base_path": base_path,
        "supported_extensions": supported_extensions,
        "file_count": file_count,
        "settings_directory": settings.settings_path,
        "settings_stats": settings_stats
    }

    return json.dumps(config, indent=2)

@mcp.resource("files://{file_path}")
def get_file_content(file_path: str) -> str:
    """Get the content of a specific file using lazy loading."""
    ctx = mcp.get_context()

    # Get the base path from context
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return "Error: Project path not set. Please use set_project_path to set a project directory first."

    # Handle absolute paths (especially Windows paths starting with drive letters)
    if os.path.isabs(file_path) or (len(file_path) > 1 and file_path[1] == ':'):
        # Absolute paths are not allowed via this endpoint
        return f"Error: Absolute file paths like '{file_path}' are not allowed. Please use paths relative to the project root."

    # Normalize the file path
    norm_path = os.path.normpath(file_path)

    # Check for path traversal attempts
    if "..\\" in norm_path or "../" in norm_path or norm_path.startswith(".."):
        return f"Error: Invalid file path: {file_path} (directory traversal not allowed)"

    # Construct the full path and verify it's within the project bounds
    full_path = os.path.join(base_path, norm_path)
    real_full_path = os.path.realpath(full_path)
    real_base_path = os.path.realpath(base_path)

    if not real_full_path.startswith(real_base_path):
        return f"Error: Access denied. File path must be within project directory."

    # Use LazyContentManager to load content
    lazy_content = lazy_content_manager.get_file_content(full_path)
    content = lazy_content.content

    if content is None:
        return f"Error reading file: Unable to decode or access"

    return content

@mcp.resource("structure://project")
def get_project_structure() -> str:
    """Get the structure of the project as a JSON tree."""
    ctx = mcp.get_context()

    # Get the base path from context
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return json.dumps({
            "status": "not_configured",
            "message": "Project path not set. Please use set_project_path to set a project directory first."
        }, indent=2)

    # Check if we need to refresh the index
    if not file_index:
        _index_project(base_path)
        # Update file count in context
        ctx.request_context.lifespan_context.file_count = _count_files(file_index)
        # Save updated index
        ctx.request_context.lifespan_context.settings.save_index(file_index)

    return json.dumps(file_index, indent=2)

@mcp.resource("settings://stats")
def get_settings_stats() -> str:
    """Get statistics about the settings directory and files."""
    ctx = mcp.get_context()

    # Get settings manager from context
    settings = ctx.request_context.lifespan_context.settings

    # Get settings stats
    stats = settings.get_stats()

    return json.dumps(stats, indent=2)

# ----- TOOLS -----

@mcp.tool()
def set_project_path(path: str, ctx: Context) -> str:
    """Set the base project path for indexing."""
    # Validate and normalize path
    try:
        norm_path = os.path.normpath(path)
        abs_path = os.path.abspath(norm_path)

        if not os.path.exists(abs_path):
            return f"Error: Path does not exist: {abs_path}"

        if not os.path.isdir(abs_path):
            return f"Error: Path is not a directory: {abs_path}"

        # Clear existing in-memory index and unload cached content
        global file_index, lazy_content_manager, memory_profiler, memory_aware_manager, performance_monitor
        file_index = {}  # Always reset to dictionary - will be loaded as TrieFileIndex if available
        lazy_content_manager.unload_all()

        # Update the base path in context
        ctx.request_context.lifespan_context.base_path = abs_path

        # Create a new settings manager for the new path (don't skip loading files)
        ctx.request_context.lifespan_context.settings = OptimizedProjectSettings(abs_path, skip_load=False, storage_backend='sqlite', use_trie_index=True)
        
        # Initialize memory profiler with configuration from settings
        try:
            config_manager = ConfigManager()
            config_data = config_manager.load_config()
            memory_limits = create_memory_config_from_yaml(config_data)
            
            # Stop existing profiler if running
            if memory_profiler:
                memory_profiler.stop_monitoring()
            
            # Create new memory profiler
            memory_profiler = MemoryProfiler(memory_limits)
            
            # Create memory-aware manager
            memory_aware_manager = MemoryAwareLazyContentManager(memory_profiler, lazy_content_manager)
            
            # Start monitoring if enabled
            if config_data.get('memory', {}).get('enable_monitoring', True):
                interval = config_data.get('memory', {}).get('monitoring_interval', 30.0)
                memory_profiler.start_monitoring(interval)
                print(f"Memory monitoring started with {interval}s interval")
            
            print(f"Memory profiler initialized: {memory_limits}")
        except Exception as e:
            print(f"Warning: Could not initialize memory profiler: {e}")
        
        # Initialize performance monitor with configuration from settings
        try:
            config_manager = ConfigManager()
            config_data = config_manager.load_config()
            
            # Create performance monitor from configuration
            performance_monitor = create_performance_monitor_from_config(config_data)
            
            print(f"Performance monitor initialized")
        except Exception as e:
            print(f"Warning: Could not initialize performance monitor: {e}")
            # Fallback to default performance monitor
            performance_monitor = PerformanceMonitor()

        # Print the settings path for debugging
        settings_path = ctx.request_context.lifespan_context.settings.settings_path
        print(f"Project settings path: {settings_path}")

        # Try to load existing index and cache
        print(f"Project path set to: {abs_path}")
        print(f"Attempting to load existing index and cache...")

        # Try to load index
        loaded_index = ctx.request_context.lifespan_context.settings.load_index()
        if loaded_index:
            print(f"Existing index found and loaded successfully")
            # Convert TrieFileIndex to dictionary format for compatibility
            if hasattr(loaded_index, 'get_all_files'):
                # This is a TrieFileIndex - convert to dict format
                file_index = {}
                for file_path, file_info in loaded_index.get_all_files():
                    # Navigate to correct directory in index
                    current_dir = file_index
                    rel_path = os.path.dirname(file_path)
                    
                    if rel_path and rel_path != '.':
                        path_parts = rel_path.replace('\\', '/').split('/')
                        for part in path_parts:
                            if part not in current_dir:
                                current_dir[part] = {}
                            current_dir = current_dir[part]
                    
                    # Add file to index
                    filename = os.path.basename(file_path)
                    current_dir[filename] = {
                        "type": "file",
                        "path": file_path,
                        "ext": file_info.get('extension', '')
                    }
                print(f"Converted TrieFileIndex to dictionary format")
            else:
                file_index = loaded_index
            
            file_count = _count_files(file_index)
            ctx.request_context.lifespan_context.file_count = file_count

            # Note: File content will be loaded lazily when accessed

            # Get search capabilities info
            search_tool = ctx.request_context.lifespan_context.settings.get_preferred_search_tool()
            
            if search_tool is None:
                search_info = " Basic search available."
            else:
                search_info = f" Advanced search enabled ({search_tool.name})."
            
            return f"Project path set to: {abs_path}. Loaded existing index with {file_count} files.{search_info}"
        else:
            print(f"No existing index found, creating new index...")

        # If no existing index, create a new one
        file_count = _index_project(abs_path)
        ctx.request_context.lifespan_context.file_count = file_count

        # Save the new index
        ctx.request_context.lifespan_context.settings.save_index(file_index)

        # Save project config
        config = {
            "base_path": abs_path,
            "supported_extensions": supported_extensions,
            "last_indexed": ctx.request_context.lifespan_context.settings.load_config().get('last_indexed', None)
        }
        ctx.request_context.lifespan_context.settings.save_config(config)

        # Get search capabilities info (this will trigger lazy detection)
        search_tool = ctx.request_context.lifespan_context.settings.get_preferred_search_tool()
        
        if search_tool is None:
            search_info = " Basic search available."
        else:
            search_info = f" Advanced search enabled ({search_tool.name})."

        return f"Project path set to: {abs_path}. Indexed {file_count} files.{search_info}"
    except Exception as e:
        return f"Error setting project path: {e}"

@mcp.tool()
async def search_code_advanced(
    pattern: str,
    ctx: Context,
    case_sensitive: bool = True,
    context_lines: int = 0,
    file_pattern: Optional[str] = None,
    fuzzy: bool = False,
    page: int = 1,
    page_size: int = 20
) -> Dict[str, Any]:
    """
    Search for a code pattern in the project using an advanced, fast tool.
    
    This tool automatically selects the best available command-line search tool 
    (like ugrep, ripgrep, ag, or grep) for maximum performance.
    
    Args:
        pattern: The search pattern (can be a regex if fuzzy=True).
        case_sensitive: Whether the search should be case-sensitive.
        context_lines: Number of lines to show before and after the match.
        file_pattern: A glob pattern to filter files to search in (e.g., "*.py").
        fuzzy: If True, treats the pattern as a regular expression. 
               If False, performs a literal/fixed-string search.
               For 'ugrep', this enables fuzzy matching features.
        page: Page number for paginated results.
        page_size: Number of results per page.
               
    Returns:
        A dictionary containing the search results or an error message.
    """
    base_path = ctx.request_context.lifespan_context.base_path
    if not base_path:
        return {"error": "Project path not set. Please use set_project_path first."}

    settings = ctx.request_context.lifespan_context.settings
    # Use global lazy_content_manager for now
    global lazy_content_manager
    strategy = settings.get_preferred_search_tool()

    if not strategy:
        return {"error": "No search strategies available. This is unexpected."}

    print(f"Using search strategy: {strategy.name}")

    # Create query key for caching
    query_key = "{}:{}:{}:{}:{}:{}".format(pattern, case_sensitive, context_lines, file_pattern, fuzzy, page)
    cached_result = lazy_content_manager.get_cached_search_result(query_key)
    if cached_result:
        print(f"Returning cached result for query: {query_key}")
        # Log cache hit
        if performance_monitor:
            performance_monitor.increment_counter("search_cache_hits_total")
            performance_monitor.log_structured("info", "Search cache hit", pattern=pattern, query_key=query_key)
        return cached_result
    
    # Log cache miss
    if performance_monitor:
        performance_monitor.increment_counter("search_cache_misses_total")

    # Use performance monitoring context manager for timing
    if performance_monitor:
        with performance_monitor.time_operation("search", 
                                               pattern=pattern, 
                                               strategy=strategy.name,
                                               file_pattern=file_pattern,
                                               case_sensitive=case_sensitive,
                                               fuzzy=fuzzy) as operation:
            try:
                # Use async search with progress callback
                def progress_callback(progress: float):
                    print(f"Search progress: {progress:.1%}")
                
                results = await strategy.search_async(
                    pattern=pattern,
                    base_path=base_path,
                    case_sensitive=case_sensitive,
                    context_lines=context_lines,
                    file_pattern=file_pattern,
                    fuzzy=fuzzy,
                    progress_callback=progress_callback
                )
                
                # Count results for metrics
                total_matches = sum(len(matches) for matches in results.values())
                operation.metadata.update({
                    "files_searched": len(results),
                    "total_matches": total_matches
                })
                
                paginated_results = lazy_content_manager.paginate_results(results, page, page_size)
                lazy_content_manager.cache_search_result(query_key, paginated_results)
                print(f"Cached new result for query: {query_key}")
                
                # Log successful search
                performance_monitor.log_structured("info", "Search completed successfully", 
                                                  pattern=pattern, 
                                                  strategy=strategy.name,
                                                  files_searched=len(results),
                                                  total_matches=total_matches,
                                                  duration_ms=operation.duration_ms)
                return paginated_results
            except Exception as e:
                # Log search error
                performance_monitor.log_structured("error", "Search failed", 
                                                  pattern=pattern, 
                                                  strategy=strategy.name,
                                                  error=str(e))
                performance_monitor.increment_counter("search_errors_total")
                return {"error": f"Search failed using '{strategy.name}': {e}"}
    else:
        # Fallback without monitoring
        try:
            # Use async search with progress callback
            def progress_callback(progress: float):
                print(f"Search progress: {progress:.1%}")
            
            results = await strategy.search_async(
                pattern=pattern,
                base_path=base_path,
                case_sensitive=case_sensitive,
                context_lines=context_lines,
                file_pattern=file_pattern,
                fuzzy=fuzzy,
                progress_callback=progress_callback
            )
            
            paginated_results = lazy_content_manager.paginate_results(results, page, page_size)
            lazy_content_manager.cache_search_result(query_key, paginated_results)
            print(f"Cached new result for query: {query_key}")
            return paginated_results
        except Exception as e:
            return {"error": f"Search failed using '{strategy.name}': {e}"}
@mcp.tool()
def find_files(pattern: str, ctx: Context) -> List[str]:
    """Find files in the project matching a specific glob pattern."""
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return ["Error: Project path not set. Please use set_project_path to set a project directory first."]

    # Check if we need to index the project
    if not file_index:
        _index_project(base_path)
        ctx.request_context.lifespan_context.file_count = _count_files(file_index)
        ctx.request_context.lifespan_context.settings.save_index(file_index)

    matching_files = []
    for file_path, _info in _get_all_files(file_index):
        if fnmatch.fnmatch(file_path, pattern):
            matching_files.append(file_path)

    return matching_files

@mcp.tool()
def get_file_summary(file_path: str, ctx: Context) -> Dict[str, Any]:
    """
    Get a summary of a specific file using lazy loading, including:
    - Line count
    - Function/class definitions (for supported languages)
    - Import statements
    - Basic complexity metrics
    """
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return {"error": "Project path not set. Please use set_project_path to set a project directory first."}

    # Normalize the file path
    norm_path = os.path.normpath(file_path)
    if norm_path.startswith('..'):
        return {"error": f"Invalid file path: {file_path}"}

    full_path = os.path.join(base_path, norm_path)

    try:
        # Get file content using lazy loading
        lazy_content = lazy_content_manager.get_file_content(full_path)
        content = lazy_content.content
        
        if content is None:
            return {"error": "Unable to read file content"}

        # Basic file info
        lines = content.splitlines()
        line_count = len(lines)

        # File extension for language-specific analysis
        _, ext = os.path.splitext(norm_path)

        summary = {
            "file_path": norm_path,
            "line_count": line_count,
            "size_bytes": os.path.getsize(full_path),
            "extension": ext,
        }

        # Language-specific analysis
        if ext == '.py':
            # Python analysis
            imports = []
            classes = []
            functions = []

            for i, line in enumerate(lines):
                line = line.strip()

                # Check for imports
                if line.startswith('import ') or line.startswith('from '):
                    imports.append(line)

                # Check for class definitions
                if line.startswith('class '):
                    classes.append({
                        "line": i + 1,
                        "name": line.replace('class ', '').split('(')[0].split(':')[0].strip()
                    })

                # Check for function definitions
                if line.startswith('def '):
                    functions.append({
                        "line": i + 1,
                        "name": line.replace('def ', '').split('(')[0].strip()
                    })

            summary.update({
                "imports": imports,
                "classes": classes,
                "functions": functions,
                "import_count": len(imports),
                "class_count": len(classes),
                "function_count": len(functions),
            })

        elif ext in ['.js', '.jsx', '.ts', '.tsx']:
            # JavaScript/TypeScript analysis
            imports = []
            classes = []
            functions = []

            for i, line in enumerate(lines):
                line = line.strip()

                # Check for imports
                if line.startswith('import ') or line.startswith('require('):
                    imports.append(line)

                # Check for class definitions
                if line.startswith('class ') or 'class ' in line:
                    class_name = ""
                    if 'class ' in line:
                        parts = line.split('class ')[1]
                        class_name = parts.split(' ')[0].split('{')[0].split('extends')[0].strip()
                    classes.append({
                        "line": i + 1,
                        "name": class_name
                    })

                # Check for function definitions
                if 'function ' in line or '=>' in line:
                    functions.append({
                        "line": i + 1,
                        "content": line
                    })

            summary.update({
                "imports": imports,
                "classes": classes,
                "functions": functions,
                "import_count": len(imports),
                "class_count": len(classes),
                "function_count": len(functions),
            })

        return summary
    except Exception as e:
        return {"error": f"Error analyzing file: {e}"}

@mcp.tool()
async def refresh_index(ctx: Context) -> Dict[str, Any]:
    """Refresh the project index using incremental indexing with progress tracking."""
    import asyncio  # Ensure asyncio is available in this function scope
    
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return {
            "error": "Project path not set. Please use set_project_path to set a project directory first.",
            "success": False
        }

    try:
        # Create progress tracker for indexing
        tracker = progress_manager.create_tracker(
            operation_name="Index Refresh",
            total_items=1000,  # Initial estimate, will be updated
            stages=["Scanning", "Indexing", "Saving"]
        )

        # Add console logging handler
        console_handler = LoggingProgressHandler()
        tracker.add_event_handler(console_handler)

        async with ProgressContext(
            operation_name="Index Refresh",
            total_items=1000,  # Will be updated with actual file count
            stages=["Scanning", "Indexing", "Saving"]
        ) as progress_tracker:
            
            # Add cleanup task to save partial state on cancellation
            def cleanup_partial_state():
                try:
                    if file_index:
                        ctx.request_context.lifespan_context.settings.save_index(file_index)
                        print("Saved partial index state during cancellation")
                except Exception as e:
                    print(f"Error saving partial state: {e}")
            
            progress_tracker.add_cleanup_task(cleanup_partial_state)
            
            # Stage 1: Scanning
            await progress_tracker.update_progress(
                stage_index=0,
                message="Starting directory scan..."
            )
            
            # Count files first for accurate progress tracking
            total_files = 0
            for root, dirs, files in os.walk(base_path):
                total_files += len(files)
                # Check for cancellation periodically
                if total_files % 100 == 0:
                    progress_tracker.cancellation_token.check_cancelled()
            
            # Update total items with actual count
            progress_tracker.total_items = max(total_files, 1)
            
            await progress_tracker.update_progress(
                message=f"Found {total_files} files to process"
            )
            
            # Stage 2: Indexing
            await progress_tracker.update_progress(
                stage_index=1,
                message="Starting incremental indexing..."
            )
            
            # Re-index the project with incremental indexing and progress tracking
            file_count = await _index_project_with_progress(base_path, progress_tracker)
            ctx.request_context.lifespan_context.file_count = file_count
            
            # Stage 3: Saving
            await progress_tracker.update_progress(
                stage_index=2,
                message="Saving index and metadata..."
            )
            
            # Save the updated index
            ctx.request_context.lifespan_context.settings.save_index(file_index)
            
            # Update the last indexed timestamp in config
            config = ctx.request_context.lifespan_context.settings.load_config()
            ctx.request_context.lifespan_context.settings.save_config({
                **config,
                'last_indexed': ctx.request_context.lifespan_context.settings._get_timestamp()
            })
            
            await progress_tracker.update_progress(
                message="Index refresh completed successfully"
            )

        # Get incremental indexing stats for the response
        settings = ctx.request_context.lifespan_context.settings
        indexer = IncrementalIndexer(settings)
        stats = indexer.get_stats()

        return {
            "success": True,
            "message": f"Project re-indexed using incremental indexing. Found {file_count} files.",
            "operation_id": progress_tracker.operation_id,
            "files_processed": file_count,
            "metadata_stats": stats,
            "elapsed_time": progress_tracker.elapsed_time
        }
    except asyncio.CancelledError:
        return {
            "error": "Indexing operation was cancelled",
            "success": False,
            "cancelled": True
        }
    except Exception as e:
        return {
            "error": f"Error during incremental re-indexing: {e}",
            "success": False
        }

@mcp.tool()
async def force_reindex(ctx: Context, clear_cache: bool = True) -> Dict[str, Any]:
    """Force a complete re-index of the project, ignoring incremental metadata.
    
    Args:
        clear_cache: Whether to clear all cached data before re-indexing (default: True)
    """
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return {
            "error": "Project path not set. Please use set_project_path to set a project directory first.",
            "success": False
        }

    try:
        global performance_monitor
        
        # Start timing the force reindex operation
        if performance_monitor:
            performance_monitor.log_structured("info", "Starting force re-index operation", 
                                             base_path=base_path, clear_cache=clear_cache)
        
        # Clear caches if requested
        if clear_cache:
            print("Clearing all caches and metadata...")
            
            # Clear settings cache
            ctx.request_context.lifespan_context.settings.clear()
            
            # Clear lazy content manager cache
            global lazy_content_manager
            lazy_content_manager.unload_all()
            
            # Clear file index
            _safe_clear_file_index()
            
            # Clear incremental indexer metadata
            settings = ctx.request_context.lifespan_context.settings
            indexer = IncrementalIndexer(settings)
            indexer.clear_metadata()
            
            # Force garbage collection
            import gc
            gc.collect()
            
            print("Cache clearing completed.")

        # Create progress tracker for force indexing
        async with ProgressContext(
            operation_name="Force Re-Index",
            total_items=1000,  # Will be updated with actual file count
            stages=["Clearing", "Scanning", "Full Indexing", "Saving"]
        ) as progress_tracker:
            
            # Stage 1: Clearing (if cache clearing)
            if clear_cache:
                await progress_tracker.update_progress(
                    stage_index=0,
                    message="Cleared all caches and metadata"
                )
            
            # Stage 2: Scanning
            await progress_tracker.update_progress(
                stage_index=1,
                message="Starting complete directory scan..."
            )
            
            # Count files for progress tracking
            total_files = 0
            print(f"Scanning directory: {base_path}")
            
            for root, dirs, files in os.walk(base_path):
                total_files += len(files)
                # Check for cancellation and provide progress updates
                if total_files % 1000 == 0:
                    progress_tracker.cancellation_token.check_cancelled()
                    await progress_tracker.update_progress(
                        message=f"Scanned {total_files} files so far..."
                    )
            
            # Update total items with actual count
            progress_tracker.total_items = max(total_files, 1)
            
            await progress_tracker.update_progress(
                message=f"Complete scan finished: {total_files} files found"
            )
            
            print(f"Force re-indexing {total_files} files...")
            
            # Stage 3: Full Indexing
            await progress_tracker.update_progress(
                stage_index=2,
                message=f"Starting full indexing of {total_files} files..."
            )
            
            # Force full re-index by using the regular indexing function
            # but with cleared metadata so everything is treated as new
            file_count = await _index_project_with_progress(base_path, progress_tracker)
            ctx.request_context.lifespan_context.file_count = file_count
            
            # Stage 4: Saving
            await progress_tracker.update_progress(
                stage_index=3,
                message="Saving complete index and metadata..."
            )
            
            # Save the new index
            ctx.request_context.lifespan_context.settings.save_index(file_index)
            
            # Update config with new timestamp
            config = ctx.request_context.lifespan_context.settings.load_config()
            ctx.request_context.lifespan_context.settings.save_config({
                **config,
                'last_indexed': ctx.request_context.lifespan_context.settings._get_timestamp(),
                'force_reindex_count': config.get('force_reindex_count', 0) + 1
            })
            
            await progress_tracker.update_progress(
                message="Force re-index completed successfully"
            )

        # Get final stats
        settings = ctx.request_context.lifespan_context.settings
        indexer = IncrementalIndexer(settings)
        stats = indexer.get_stats()
        
        # Log completion
        if performance_monitor:
            performance_monitor.log_structured("info", "Force re-index completed successfully", 
                                             base_path=base_path, files_processed=file_count,
                                             elapsed_time=progress_tracker.elapsed_time)
            performance_monitor.increment_counter("force_reindex_operations_total")

        return {
            "success": True,
            "message": f"Force re-index completed. Processed {file_count} files from scratch.",
            "operation_id": progress_tracker.operation_id,
            "files_processed": file_count,
            "cache_cleared": clear_cache,
            "metadata_stats": stats,
            "elapsed_time": progress_tracker.elapsed_time
        }
        
    except asyncio.CancelledError:
        return {
            "error": "Force re-index operation was cancelled",
            "success": False,
            "cancelled": True
        }
    except Exception as e:
        if performance_monitor:
            performance_monitor.log_structured("error", "Force re-index failed", 
                                             error=str(e), base_path=base_path)
        return {
            "error": f"Error during force re-indexing: {e}",
            "success": False
        }

@mcp.tool()
def get_settings_info(ctx: Context) -> Dict[str, Any]:
    """Get information about the project settings."""
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        # Even if base_path is not set, we can still show the temp directory
        temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR)
        return {
            "status": "not_configured",
            "message": "Project path not set. Please use set_project_path to set a project directory first.",
            "temp_directory": temp_dir,
            "temp_directory_exists": os.path.exists(temp_dir)
        }

    settings = ctx.request_context.lifespan_context.settings

    # Get config
    config = settings.load_config()

    # Get stats
    stats = settings.get_stats()

    # Get temp directory
    temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR)

    return {
        "settings_directory": settings.settings_path,
        "temp_directory": temp_dir,
        "temp_directory_exists": os.path.exists(temp_dir),
        "config": config,
        "stats": stats,
        "exists": os.path.exists(settings.settings_path)
    }

@mcp.tool()
def create_temp_directory() -> Dict[str, Any]:
    """Create the temporary directory used for storing index data."""
    temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR)

    result = {
        "temp_directory": temp_dir,
        "existed_before": os.path.exists(temp_dir),
    }

    try:
        # Use OptimizedProjectSettings to handle directory creation consistently
        temp_settings = OptimizedProjectSettings("", skip_load=True)
        
        result["created"] = not result["existed_before"]
        result["exists_now"] = os.path.exists(temp_dir)
        result["is_directory"] = os.path.isdir(temp_dir)
    except Exception as e:
        result["error"] = str(e)

    return result

@mcp.tool()
def check_temp_directory() -> Dict[str, Any]:
    """Check the temporary directory used for storing index data."""
    temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR)

    result = {
        "temp_directory": temp_dir,
        "exists": os.path.exists(temp_dir),
        "is_directory": os.path.isdir(temp_dir) if os.path.exists(temp_dir) else False,
        "temp_root": tempfile.gettempdir(),
    }

    # If the directory exists, list its contents
    if result["exists"] and result["is_directory"]:
        try:
            contents = os.listdir(temp_dir)
            result["contents"] = contents
            result["subdirectories"] = []

            # Check each subdirectory
            for item in contents:
                item_path = os.path.join(temp_dir, item)
                if os.path.isdir(item_path):
                    subdir_info = {
                        "name": item,
                        "path": item_path,
                        "contents": os.listdir(item_path) if os.path.exists(item_path) else []
                    }
                    result["subdirectories"].append(subdir_info)
        except Exception as e:
            result["error"] = str(e)

    return result

@mcp.tool()
def clear_settings(ctx: Context) -> str:
    """Clear all settings and cached data."""
    settings = ctx.request_context.lifespan_context.settings
    settings.clear()
    return "Project settings, index, and cache have been cleared."

@mcp.tool()
def reset_server_state(ctx: Context) -> str:
    """Completely reset the server state including global variables."""
    global file_index, lazy_content_manager, memory_profiler, memory_aware_manager, performance_monitor
    
    try:
        # Reset global file_index to empty dict
        file_index = {}
        
        # Clear lazy content manager
        lazy_content_manager.unload_all()
        
        # Reset context to empty state
        ctx.request_context.lifespan_context.base_path = ""
        ctx.request_context.lifespan_context.file_count = 0
        
        # Create fresh settings with skip_load=True
        ctx.request_context.lifespan_context.settings = OptimizedProjectSettings("", skip_load=True, storage_backend='sqlite', use_trie_index=True)
        
        # Stop memory profiler if running
        if memory_profiler:
            try:
                memory_profiler.stop_monitoring()
            except:
                pass
        memory_profiler = None
        memory_aware_manager = None
        performance_monitor = None
        
        return "Server state completely reset. All global variables and context cleared."
    except Exception as e:
        return f"Error resetting server state: {e}"

@mcp.tool()
def refresh_search_tools(ctx: Context) -> str:
    """
    Manually re-detect the available command-line search tools on the system.
    This is useful if you have installed a new tool (like ripgrep) after starting the server.
    """
    settings = ctx.request_context.lifespan_context.settings
    settings.refresh_available_strategies()
    
    config = settings.get_search_tools_config()
    
    return f"Search tools refreshed. Available: {config['available_tools']}. Preferred: {config['preferred_tool']}."

@mcp.tool()
def get_ignore_patterns(ctx: Context) -> Dict[str, Any]:
    """Get information about the loaded ignore patterns."""
    base_path = ctx.request_context.lifespan_context.base_path
    
    # Check if base_path is set
    if not base_path:
        return {
            "error": "Project path not set. Please use set_project_path to set a project directory first."
        }
    
    # Initialize ignore pattern matcher
    ignore_matcher = IgnorePatternMatcher(base_path)
    
    # Get pattern information
    pattern_info = ignore_matcher.get_pattern_sources()
    all_patterns = ignore_matcher.get_patterns()
    
    return {
        "base_path": base_path,
        "pattern_sources": pattern_info,
        "all_patterns": all_patterns,
        "gitignore_path": str(ignore_matcher.base_path / '.gitignore'),
        "ignore_path": str(ignore_matcher.base_path / '.ignore'),
        "default_excludes": list(ignore_matcher.DEFAULT_EXCLUDES)
    }

@mcp.tool()
def get_filtering_config() -> Dict[str, Any]:
    """Get information about the current filtering configuration."""
    config_manager = ConfigManager()
    
    # Get filtering stats
    filtering_stats = config_manager.get_filtering_stats()
    
    # Add some examples of current limits
    examples = {
        "file_size_examples": {
            "python_file_limit": config_manager.get_max_file_size("example.py"),
            "javascript_file_limit": config_manager.get_max_file_size("example.js"),
            "json_file_limit": config_manager.get_max_file_size("example.json"),
            "markdown_file_limit": config_manager.get_max_file_size("example.md"),
            "default_file_limit": config_manager.get_max_file_size("example.unknown"),
        },
        "directory_limits": {
            "max_files_per_directory": config_manager.get_max_files_per_directory(),
            "max_subdirectories_per_directory": config_manager.get_max_subdirectories_per_directory(),
        }
    }
    
    return {
        "filtering_configuration": filtering_stats,
        "examples": examples,
        "performance_settings": {
            "logging_enabled": config_manager.should_log_filtering_decisions(),
            "parallel_processing": config_manager.is_parallel_processing_enabled(),
            "max_workers": config_manager.get_max_workers(),
            "directory_caching": config_manager.is_directory_scan_caching_enabled(),
        }
    }

@mcp.tool()
def get_lazy_loading_stats() -> Dict[str, Any]:
    """Get statistics about the lazy loading memory management."""
    global lazy_content_manager
    
    memory_stats = lazy_content_manager.get_memory_stats()
    
    return {
        "lazy_loading_enabled": True,
        "memory_stats": memory_stats,
        "description": "File contents are loaded on-demand to optimize memory usage"
    }

@mcp.tool()
def get_incremental_indexing_stats(ctx: Context) -> Dict[str, Any]:
    """Get statistics about incremental indexing metadata."""
    base_path = ctx.request_context.lifespan_context.base_path
    
    # Check if base_path is set
    if not base_path:
        return {
            "error": "Project path not set. Please use set_project_path to set a project directory first."
        }
    
    try:
        # Initialize incremental indexer
        settings = ctx.request_context.lifespan_context.settings
        indexer = IncrementalIndexer(settings)
        
        # Get indexer statistics
        stats = indexer.get_stats()
        
        return {
            "base_path": base_path,
            "incremental_indexing_enabled": True,
            "metadata_stats": stats,
            "metadata_file_path": settings.get_metadata_path()
        }
    except Exception as e:
        return {
            "error": f"Error getting incremental indexing stats: {e}",
            "base_path": base_path
        }

@mcp.tool()
def get_memory_profile() -> Dict[str, Any]:
    """Get comprehensive memory profiling statistics."""
    global memory_profiler, lazy_content_manager
    
    if memory_profiler is None:
        return {
            "error": "Memory profiler not initialized. Please set a project path first.",
            "initialized": False
        }
    
    try:
        # Get current memory stats from lazy content manager
        content_stats = lazy_content_manager.get_memory_stats()
        
        # Take a memory snapshot with current stats
        snapshot = memory_profiler.take_snapshot(
            loaded_files=content_stats['loaded_files'],
            cached_queries=content_stats['query_cache_size']
        )
        
        # Get comprehensive profiler stats
        profiler_stats = memory_profiler.get_stats()
        
        return {
            "initialized": True,
            "current_snapshot": {
                "timestamp": snapshot.timestamp,
                "process_memory_mb": snapshot.process_memory_mb,
                "heap_size_mb": snapshot.heap_size_mb,
                "peak_memory_mb": snapshot.peak_memory_mb,
                "gc_objects": snapshot.gc_objects,
                "gc_collections": snapshot.gc_collections,
                "active_threads": snapshot.active_threads,
                "loaded_files": snapshot.loaded_files,
                "cached_queries": snapshot.cached_queries
            },
            "profiler_stats": profiler_stats,
            "content_manager_stats": content_stats
        }
    except Exception as e:
        return {
            "error": f"Error getting memory profile: {e}",
            "initialized": True
        }

@mcp.tool()
def trigger_memory_cleanup() -> Dict[str, Any]:
    """Manually trigger memory cleanup and garbage collection."""
    global memory_profiler, memory_aware_manager, lazy_content_manager
    
    if memory_profiler is None:
        return {
            "error": "Memory profiler not initialized. Please set a project path first.",
            "success": False
        }
    
    try:
        # Get stats before cleanup
        stats_before = lazy_content_manager.get_memory_stats()
        
        # Trigger cleanup through memory aware manager if available
        if memory_aware_manager:
            memory_aware_manager.cleanup()
        else:
            # Fallback to direct cleanup
            lazy_content_manager.unload_all()
        
        # Force garbage collection
        import gc
        collected = gc.collect()
        
        # Get stats after cleanup
        stats_after = lazy_content_manager.get_memory_stats()
        
        # Take new memory snapshot
        snapshot = memory_profiler.take_snapshot(
            loaded_files=stats_after['loaded_files'],
            cached_queries=stats_after['query_cache_size']
        )
        
        return {
            "success": True,
            "cleanup_results": {
                "gc_objects_collected": collected,
                "before_cleanup": stats_before,
                "after_cleanup": stats_after,
                "memory_freed_mb": max(0, stats_before.get('total_managed_files', 0) - stats_after.get('total_managed_files', 0))
            },
            "current_memory_mb": snapshot.process_memory_mb,
            "peak_memory_mb": snapshot.peak_memory_mb
        }
    except Exception as e:
        return {
            "error": f"Error during memory cleanup: {e}",
            "success": False
        }

@mcp.tool()
def configure_memory_limits(soft_limit_mb: Optional[float] = None, 
                          hard_limit_mb: Optional[float] = None,
                          max_loaded_files: Optional[int] = None,
                          max_cached_queries: Optional[int] = None) -> Dict[str, Any]:
    """Update memory limits configuration."""
    global memory_profiler
    
    if memory_profiler is None:
        return {
            "error": "Memory profiler not initialized. Please set a project path first.",
            "success": False
        }
    
    try:
        # Update limits if provided
        limits = memory_profiler.limits
        old_limits = {
            "soft_limit_mb": limits.soft_limit_mb,
            "hard_limit_mb": limits.hard_limit_mb,
            "max_loaded_files": limits.max_loaded_files,
            "max_cached_queries": limits.max_cached_queries
        }
        
        if soft_limit_mb is not None:
            limits.soft_limit_mb = soft_limit_mb
        if hard_limit_mb is not None:
            limits.hard_limit_mb = hard_limit_mb
        if max_loaded_files is not None:
            limits.max_loaded_files = max_loaded_files
        if max_cached_queries is not None:
            limits.max_cached_queries = max_cached_queries
        
        new_limits = {
            "soft_limit_mb": limits.soft_limit_mb,
            "hard_limit_mb": limits.hard_limit_mb,
            "max_loaded_files": limits.max_loaded_files,
            "max_cached_queries": limits.max_cached_queries
        }
        
        return {
            "success": True,
            "old_limits": old_limits,
            "new_limits": new_limits,
            "message": "Memory limits updated successfully"
        }
    except Exception as e:
        return {
            "error": f"Error updating memory limits: {e}",
            "success": False
        }

@mcp.tool()
def export_memory_profile(file_path: Optional[str] = None) -> Dict[str, Any]:
    """Export detailed memory profile to a file."""
    global memory_profiler
    
    if memory_profiler is None:
        return {
            "error": "Memory profiler not initialized. Please set a project path first.",
            "success": False
        }
    
    try:
        import tempfile
        import os
        
        # Use provided path or generate a default one
        if file_path is None:
            timestamp = int(time.time())
            file_path = os.path.join(tempfile.gettempdir(), f"memory_profile_{timestamp}.json")
        
        # Export profile
        memory_profiler.export_profile(file_path)
        
        return {
            "success": True,
            "file_path": file_path,
            "message": f"Memory profile exported to {file_path}"
        }
    except Exception as e:
        return {
            "error": f"Error exporting memory profile: {e}",
            "success": False
        }

@mcp.tool()
def get_performance_metrics() -> Dict[str, Any]:
    """Get comprehensive performance monitoring metrics and statistics."""
    global performance_monitor
    
    if performance_monitor is None:
        return {
            "error": "Performance monitor not initialized. Please set a project path first.",
            "initialized": False
        }
    
    try:
        # Get all performance metrics
        metrics = performance_monitor.get_metrics_summary()
        
        # Get operation statistics
        operation_stats = performance_monitor.get_operation_stats()
        
        # Get structured logs (last 100 entries) - note: this method doesn't exist, will use empty list
        logs = []  # TODO: implement log retrieval if needed
        
        return {
            "initialized": True,
            "metrics": metrics,
            "operation_stats": operation_stats,
            "recent_logs": logs,
            "monitoring_enabled": True
        }
    except Exception as e:
        return {
            "error": f"Error getting performance metrics: {e}",
            "initialized": True
        }

@mcp.tool()
def export_performance_metrics(file_path: Optional[str] = None) -> Dict[str, Any]:
    """Export performance metrics to a JSON file."""
    global performance_monitor
    
    if performance_monitor is None:
        return {
            "error": "Performance monitor not initialized. Please set a project path first.",
            "success": False
        }
    
    try:
        import tempfile
        import os
        
        # Use provided path or generate a default one
        if file_path is None:
            timestamp = int(time.time())
            file_path = os.path.join(tempfile.gettempdir(), f"performance_metrics_{timestamp}.json")
        
        # Export metrics  
        performance_monitor.export_metrics_json(file_path)
        
        return {
            "success": True,
            "file_path": file_path,
            "message": f"Performance metrics exported to {file_path}"
        }
    except Exception as e:
        return {
            "error": f"Error exporting performance metrics: {e}",
            "success": False
        }

# ----- PROGRESS TRACKING TOOLS -----

@mcp.tool()
def get_active_operations() -> Dict[str, Any]:
    """Get status of all active operations with progress tracking."""
    try:
        active_ops = progress_manager.get_active_operations()
        all_ops = progress_manager.get_all_operations_status()
        
        return {
            "success": True,
            "active_operations": active_ops,
            "total_operations": len(all_ops),
            "active_count": len(active_ops)
        }
    except Exception as e:
        return {
            "error": f"Error getting active operations: {e}",
            "success": False
        }

@mcp.tool()
def get_operation_status(operation_id: str) -> Dict[str, Any]:
    """Get detailed status of a specific operation."""
    try:
        tracker = progress_manager.get_tracker(operation_id)
        if not tracker:
            return {
                "error": f"Operation {operation_id} not found",
                "success": False
            }
        
        status = tracker.get_status()
        return {
            "success": True,
            "operation_status": status
        }
    except Exception as e:
        return {
            "error": f"Error getting operation status: {e}",
            "success": False
        }

@mcp.tool()
async def cancel_operation(operation_id: str, reason: str = "Operation cancelled by user") -> Dict[str, Any]:
    """Cancel a specific operation."""
    try:
        success = await progress_manager.cancel_operation(operation_id, reason)
        if success:
            return {
                "success": True,
                "message": f"Operation {operation_id} cancelled successfully",
                "operation_id": operation_id,
                "reason": reason
            }
        else:
            return {
                "error": f"Operation {operation_id} not found or already completed",
                "success": False
            }
    except Exception as e:
        return {
            "error": f"Error cancelling operation: {e}",
            "success": False
        }

@mcp.tool()
async def cancel_all_operations(reason: str = "All operations cancelled by user") -> Dict[str, Any]:
    """Cancel all active operations."""
    try:
        active_ops_before = progress_manager.get_active_operations()
        await progress_manager.cancel_all_operations(reason)
        
        return {
            "success": True,
            "message": "All operations cancelled successfully",
            "operations_cancelled": len(active_ops_before),
            "reason": reason
        }
    except Exception as e:
        return {
            "error": f"Error cancelling all operations: {e}",
            "success": False
        }

@mcp.tool()
def cleanup_completed_operations(max_age_hours: float = 1.0) -> Dict[str, Any]:
    """Clean up completed operations older than specified hours."""
    try:
        max_age_seconds = max_age_hours * 3600
        ops_before = len(progress_manager.get_all_operations_status())
        
        progress_manager.cleanup_completed_operations(max_age_seconds)
        
        ops_after = len(progress_manager.get_all_operations_status())
        cleaned_up = ops_before - ops_after
        
        return {
            "success": True,
            "message": f"Cleaned up {cleaned_up} completed operations",
            "operations_before": ops_before,
            "operations_after": ops_after,
            "operations_cleaned": cleaned_up,
            "max_age_hours": max_age_hours
        }
    except Exception as e:
        return {
            "error": f"Error cleaning up operations: {e}",
            "success": False
        }

# ----- PROMPTS -----

@mcp.prompt()
def analyze_code(file_path: str = "", query: str = "") -> list[types.PromptMessage]:
    """Prompt for analyzing code in the project."""
    messages = [
        types.PromptMessage(role="user", content=types.TextContent(type="text", text=f"""I need you to analyze some code from my project.

{f'Please analyze the file: {file_path}' if file_path else ''}
{f'I want to understand: {query}' if query else ''}

First, let me give you some context about the project structure. Then, I'll provide the code to analyze.
""")),
        types.PromptMessage(role="assistant", content=types.TextContent(type="text", text="I'll help you analyze the code. Let me first examine the project structure to get a better understanding of the codebase."))
    ]
    return messages

@mcp.prompt()
def code_search(query: str = "") -> types.TextContent:
    """Prompt for searching code in the project."""
    search_text = f"\"query\"" if not query else f"\"{query}\""
    return types.TextContent(type="text", text=f"""I need to search through my codebase for {search_text}.

Please help me find all occurrences of this query and explain what each match means in its context.
Focus on the most relevant files and provide a brief explanation of how each match is used in the code.

If there are too many results, prioritize the most important ones and summarize the patterns you see.""")

@mcp.prompt()
def set_project() -> list[types.PromptMessage]:
    """Prompt for setting the project path."""
    messages = [
        types.PromptMessage(role="user", content=types.TextContent(type="text", text="""
        I need to analyze code from a project, but I haven't set the project path yet. Please help me set up the project path and index the code.

        First, I need to specify which project directory to analyze.
        """)),
        types.PromptMessage(role="assistant", content=types.TextContent(type="text", text="""
        Before I can help you analyze any code, we need to set up the project path. This is a required first step.

        Please provide the full path to your project folder. For example:
        - Windows: "C:/Users/username/projects/my-project"
        - macOS/Linux: "/home/username/projects/my-project"

        Once you provide the path, I'll use the `set_project_path` tool to configure the code analyzer to work with your project.
        """))
    ]
    return messages

# ----- HELPER FUNCTIONS -----

def _safe_clear_file_index():
    """Safely clear the file_index regardless of its type."""
    global file_index
    
    # Always reset to empty dictionary to ensure compatibility
    file_index = {}

async def _index_project_with_progress(base_path: str, progress_tracker: ProgressTracker) -> int:
    """
    Create an index of the project files with progress tracking and cancellation support.
    Returns the number of files indexed.
    """
    global performance_monitor
    
    # Start timing the indexing operation
    indexing_context = None
    if performance_monitor:
        indexing_context = performance_monitor.time_operation("indexing", 
                                                             base_path=base_path,
                                                             operation_type="incremental_index_with_progress")
        indexing_context.__enter__()
        performance_monitor.log_structured("info", "Starting project indexing with progress tracking", base_path=base_path)
    
    file_count = 0
    filtered_files = 0
    filtered_dirs = 0
    _safe_clear_file_index()
    
    try:
        # Initialize configuration manager for filtering
        config_manager = ConfigManager()

        # Initialize ignore pattern matcher
        ignore_matcher = IgnorePatternMatcher(base_path)

        # Initialize incremental indexer
        settings = OptimizedProjectSettings(base_path)
        indexer = IncrementalIndexer(settings)

        # Update progress
        await progress_tracker.update_progress(
            message="Initialized indexing components"
        )
        progress_tracker.cancellation_token.check_cancelled()

        # Get pattern information for debugging
        pattern_info = ignore_matcher.get_pattern_sources()
        print(f"Ignore patterns loaded: {pattern_info}")

        # Get filtering configuration
        filtering_stats = config_manager.get_filtering_stats()
        print(f"Filtering configuration: {filtering_stats}")

        should_log = config_manager.should_log_filtering_decisions()

        # Gather current file list with progress updates
        current_file_list = []
        scanned_files = 0
        
        await progress_tracker.update_progress(
            message="Scanning project directory..."
        )

        for root, dirs, files in os.walk(base_path):
            # Check for cancellation periodically
            if scanned_files % 50 == 0:
                progress_tracker.cancellation_token.check_cancelled()
                await progress_tracker.update_progress(
                    message=f"Scanned {scanned_files} files so far..."
                )
            
            # Create relative path from base_path
            rel_path = os.path.relpath(root, base_path)
            
            # Skip the current directory if it should be ignored by pattern matcher
            if rel_path != '.' and ignore_matcher.should_ignore_directory(rel_path):
                dirs[:] = []  # Don't recurse into subdirectories
                continue
            
            # Check if directory should be skipped due to size/count filtering
            if rel_path != '.' and config_manager.should_skip_directory_by_pattern(rel_path):
                if should_log:
                    print(f"Skipping directory by pattern: {rel_path}")
                dirs[:] = []  # Don't recurse into subdirectories
                filtered_dirs += 1
                continue
            
            # Count files and subdirectories for directory filtering
            visible_files = []
            for file in files:
                scanned_files += 1
                
                # Skip hidden files and files with unsupported extensions
                _, ext = os.path.splitext(file)
                if file.startswith('.') or ext not in supported_extensions:
                    continue
                
                # Create file path for checking
                file_path = os.path.join(rel_path, file).replace('\\', '/')
                if rel_path == '.':
                    file_path = file
                
                # Check if file should be ignored by pattern matcher
                if ignore_matcher.should_ignore(file_path):
                    continue
                
                # Check file size
                full_file_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(full_file_path)
                    if config_manager.should_skip_file_by_size(file_path, file_size):
                        if should_log:
                            print(f"Skipping large file: {file_path} ({file_size} bytes)")
                        filtered_files += 1
                        continue
                except (OSError, IOError) as e:
                    if should_log:
                        print(f"Error getting file size for {file_path}: {e}")
                    continue
                
                visible_files.append((file, file_path, ext))
            
            visible_dirs = [d for d in dirs if not ignore_matcher.should_ignore_directory(
                os.path.join(rel_path, d) if rel_path != '.' else d
            )]
            
            # Apply directory count filtering
            if config_manager.should_skip_directory_by_count(rel_path, len(visible_files), len(visible_dirs)):
                if should_log:
                    print(f"Skipping directory by count: {rel_path} ({len(visible_files)} files, {len(visible_dirs)} subdirs)")
                dirs[:] = []  # Don't recurse into subdirectories
                filtered_dirs += 1
                continue
            
            # Filter directories using the ignore pattern matcher
            dirs[:] = visible_dirs
            
            # Add files to current file list for incremental indexing
            for file, file_path, ext in visible_files:
                current_file_list.append(file_path)

        # Update progress tracker with actual file count
        progress_tracker.total_items = max(len(current_file_list), 1)
        
        await progress_tracker.update_progress(
            message=f"Identified {len(current_file_list)} files to process"
        )
        progress_tracker.cancellation_token.check_cancelled()

        # Identify changed files using incremental indexer
        added_files, modified_files, deleted_files = indexer.get_changed_files(base_path, current_file_list)

        # Clean up deleted files metadata
        indexer.clean_deleted_files(deleted_files)

        print(f"Incremental indexing: Added: {len(added_files)}, Modified: {len(modified_files)}, Deleted: {len(deleted_files)}")
        
        await progress_tracker.update_progress(
            message=f"Incremental analysis: {len(added_files)} added, {len(modified_files)} modified, {len(deleted_files)} deleted"
        )
        progress_tracker.cancellation_token.check_cancelled()

        # Only process changed files (added + modified) for efficiency
        changed_files = added_files + modified_files
        if not changed_files and not deleted_files:
            print("No changes detected, using existing index")
            # Count existing files in the metadata
            file_count = len(indexer.file_metadata)
            await progress_tracker.update_progress(
                message=f"No changes detected, index is up to date with {file_count} files"
            )
            return file_count

        # Use parallel processing for chunked indexing of changed files
        if changed_files:
            print(f"Processing {len(changed_files)} changed files using parallel indexing...")
            
            await progress_tracker.update_progress(
                message=f"Processing {len(changed_files)} changed files..."
            )
            
            # Create indexing tasks for changed files
            indexing_tasks = []
            for file_path in changed_files:
                progress_tracker.cancellation_token.check_cancelled()
                
                full_file_path = os.path.join(base_path, file_path)
                
                # Skip if file doesn't exist (might have been deleted)
                if not os.path.exists(full_file_path):
                    continue
                
                # Get file info
                _, ext = os.path.splitext(file_path)
                task = IndexingTask(
                    directory_path=base_path,
                    files=[file_path],
                    task_id=file_path,
                    metadata={"extension": ext}
                )
                indexing_tasks.append(task)
            
            # Process tasks using parallel indexer
            if indexing_tasks:
                parallel_indexer = ParallelIndexer()
                
                # Process files in parallel chunks with progress updates
                try:
                    # Run the parallel processing with progress callback
                    async def progress_callback(completed: int, total: int):
                        progress_tracker.cancellation_token.check_cancelled()
                        progress_percent = (completed / total) * 100 if total > 0 else 0
                        await progress_tracker.update_progress(
                            items_processed=completed - progress_tracker.items_processed,
                            message=f"Processed {completed}/{total} files ({progress_percent:.1f}%)"
                        )
                    
                    # Run the parallel processing
                    results = await parallel_indexer.process_files(indexing_tasks)
                    
                    progress_tracker.cancellation_token.check_cancelled()
                    
                    # Merge results into file_index
                    for result in results:
                        progress_tracker.cancellation_token.check_cancelled()
                        
                        if result.success:
                            # Process each indexed file in the result
                            for file_info in result.indexed_files:
                                file_path = file_info['path']
                                
                                # Navigate to the correct directory in the index
                                current_dir = file_index
                                rel_path = os.path.dirname(file_path)
                                
                                # Skip the '.' directory (base_path itself)
                                if rel_path and rel_path != '.':
                                    # Split the path and navigate/create the tree
                                    path_parts = rel_path.replace('\\', '/').split('/')
                                    for part in path_parts:
                                        if part not in current_dir:
                                            current_dir[part] = {}
                                        current_dir = current_dir[part]
                                
                                # Add file to index
                                filename = os.path.basename(file_path)
                                current_dir[filename] = {
                                    "type": "file",
                                    "path": file_path,
                                    "ext": file_info.get("extension", "")
                                }
                                file_count += 1
                                
                                # Update file metadata
                                full_file_path = os.path.join(base_path, file_path)
                                indexer.update_file_metadata(file_path, full_file_path)
                        else:
                            print(f"Failed to index task {result.task_id}: {result.errors}")
                            
                    await progress_tracker.update_progress(
                        message=f"Parallel indexing completed: {file_count} files processed"
                    )
                    print(f"Parallel indexing completed: {file_count} files processed")
                except Exception as e:
                    print(f"Error in parallel processing: {e}")
                    # Fall back to sequential processing
                    print("Falling back to sequential processing...")
                    
                    await progress_tracker.update_progress(
                        message="Parallel processing failed, falling back to sequential..."
                    )
                    
                    # Sequential fallback (processing only changed files)
                    processed_files = 0
                    for file_path in changed_files:
                        progress_tracker.cancellation_token.check_cancelled()
                        
                        full_file_path = os.path.join(base_path, file_path)
                        
                        # Skip if file doesn't exist
                        if not os.path.exists(full_file_path):
                            continue
                        
                        # Navigate to the correct directory in the index
                        current_dir = file_index
                        rel_path = os.path.dirname(file_path)
                        
                        # Skip the '.' directory (base_path itself)
                        if rel_path and rel_path != '.':
                            # Split the path and navigate/create the tree
                            path_parts = rel_path.replace('\\', '/').split('/')
                            for part in path_parts:
                                if part not in current_dir:
                                    current_dir[part] = {}
                                current_dir = current_dir[part]
                        
                        # Add file to index
                        filename = os.path.basename(file_path)
                        _, ext = os.path.splitext(file_path)
                        current_dir[filename] = {
                            "type": "file",
                            "path": file_path,
                            "ext": ext
                        }
                        file_count += 1
                        processed_files += 1
                        
                        # Update file metadata
                        indexer.update_file_metadata(file_path, full_file_path)
                        
                        # Update progress periodically
                        if processed_files % 10 == 0:
                            progress_percent = (processed_files / len(changed_files)) * 100
                            await progress_tracker.update_progress(
                                items_processed=1,
                                message=f"Sequential processing: {processed_files}/{len(changed_files)} files ({progress_percent:.1f}%)"
                            )
            else:
                print("No files to process in parallel, using existing index")
                await progress_tracker.update_progress(
                    message="No files to process"
                )

        # Save updated metadata
        await progress_tracker.update_progress(
            message="Saving metadata..."
        )
        indexer.save_metadata()
        
        # Complete performance monitoring
        if performance_monitor and indexing_context:
            try:
                # Update operation metadata with results
                indexing_context.metadata.update({
                    "files_indexed": file_count,
                    "files_filtered": filtered_files,
                    "directories_filtered": filtered_dirs,
                    "added_files": len(added_files) if 'added_files' in locals() else 0,
                    "modified_files": len(modified_files) if 'modified_files' in locals() else 0,
                    "deleted_files": len(deleted_files) if 'deleted_files' in locals() else 0
                })
                
                # Exit the timing context
                indexing_context.__exit__(None, None, None)
                
                # Log completion
                performance_monitor.log_structured("info", "Project indexing with progress completed successfully", 
                                                  base_path=base_path,
                                                  files_indexed=file_count,
                                                  files_filtered=filtered_files,
                                                  directories_filtered=filtered_dirs,
                                                  duration_ms=indexing_context.duration_ms)
                
                # Increment success counter
                performance_monitor.increment_counter("indexing_operations_total")
                
            except Exception as e:
                # Log indexing error
                performance_monitor.log_structured("error", "Error during indexing performance monitoring", 
                                                  error=str(e))
                # Still exit the context to avoid resource leaks
                if indexing_context:
                    try:
                        indexing_context.__exit__(Exception, type(e), None)
                    except:
                        pass

        await progress_tracker.update_progress(
            message=f"Indexing completed: {file_count} files indexed, {filtered_files} files filtered, {filtered_dirs} directories filtered"
        )
        print(f"Indexing completed: {file_count} files indexed, {filtered_files} files filtered, {filtered_dirs} directories filtered")
        return file_count
        
    except asyncio.CancelledError:
        print("Indexing operation was cancelled")
        if performance_monitor and indexing_context:
            try:
                indexing_context.metadata.update({"cancelled": True})
                indexing_context.__exit__(None, None, None)
                performance_monitor.log_structured("warning", "Indexing operation cancelled", base_path=base_path)
            except:
                pass
        raise
    except Exception as e:
        print(f"Error during indexing: {e}")
        if performance_monitor and indexing_context:
            try:
                indexing_context.__exit__(Exception, type(e), None)
                performance_monitor.log_structured("error", "Indexing operation failed", error=str(e), base_path=base_path)
            except:
                pass
        raise

def _index_project(base_path: str) -> int:
    """
    Create an index of the project files with size and directory count filtering.
    Returns the number of files indexed.
    """
    global performance_monitor
    
    # Start timing the indexing operation
    indexing_context = None
    if performance_monitor:
        indexing_context = performance_monitor.time_operation("indexing", 
                                                             base_path=base_path,
                                                             operation_type="full_index")
        indexing_context.__enter__()
        performance_monitor.log_structured("info", "Starting project indexing", base_path=base_path)
    
    file_count = 0
    filtered_files = 0
    filtered_dirs = 0
    _safe_clear_file_index()
    
    # Initialize configuration manager for filtering
    config_manager = ConfigManager()

    # Initialize ignore pattern matcher
    ignore_matcher = IgnorePatternMatcher(base_path)

    # Initialize incremental indexer
    settings = OptimizedProjectSettings(base_path)
    indexer = IncrementalIndexer(settings)

    # Get pattern information for debugging
    pattern_info = ignore_matcher.get_pattern_sources()
    print(f"Ignore patterns loaded: {pattern_info}")

    # Get filtering configuration
    filtering_stats = config_manager.get_filtering_stats()
    print(f"Filtering configuration: {filtering_stats}")

    should_log = config_manager.should_log_filtering_decisions()

    # Gather current file list
    current_file_list = []

    for root, dirs, files in os.walk(base_path):
        # Create relative path from base_path
        rel_path = os.path.relpath(root, base_path)
        
        # Skip the current directory if it should be ignored by pattern matcher
        if rel_path != '.' and ignore_matcher.should_ignore_directory(rel_path):
            dirs[:] = []  # Don't recurse into subdirectories
            continue
        
        # Check if directory should be skipped due to size/count filtering
        if rel_path != '.' and config_manager.should_skip_directory_by_pattern(rel_path):
            if should_log:
                print(f"Skipping directory by pattern: {rel_path}")
            dirs[:] = []  # Don't recurse into subdirectories
            filtered_dirs += 1
            continue
        
        # Count files and subdirectories for directory filtering
        visible_files = []
        for file in files:
            # Skip hidden files and files with unsupported extensions
            _, ext = os.path.splitext(file)
            if file.startswith('.') or ext not in supported_extensions:
                continue
            
            # Create file path for checking
            file_path = os.path.join(rel_path, file).replace('\\', '/')
            if rel_path == '.':
                file_path = file
            
            # Check if file should be ignored by pattern matcher
            if ignore_matcher.should_ignore(file_path):
                continue
            
            # Check file size
            full_file_path = os.path.join(root, file)
            try:
                file_size = os.path.getsize(full_file_path)
                if config_manager.should_skip_file_by_size(file_path, file_size):
                    if should_log:
                        print(f"Skipping large file: {file_path} ({file_size} bytes)")
                    filtered_files += 1
                    continue
            except (OSError, IOError) as e:
                if should_log:
                    print(f"Error getting file size for {file_path}: {e}")
                continue
            
            visible_files.append((file, file_path, ext))
        
        visible_dirs = [d for d in dirs if not ignore_matcher.should_ignore_directory(
            os.path.join(rel_path, d) if rel_path != '.' else d
        )]
        
        # Apply directory count filtering
        if config_manager.should_skip_directory_by_count(rel_path, len(visible_files), len(visible_dirs)):
            if should_log:
                print(f"Skipping directory by count: {rel_path} ({len(visible_files)} files, {len(visible_dirs)} subdirs)")
            dirs[:] = []  # Don't recurse into subdirectories
            filtered_dirs += 1
            continue
        
        # Filter directories using the ignore pattern matcher
        dirs[:] = visible_dirs
        
        # Add files to current file list for incremental indexing
        for file, file_path, ext in visible_files:
            current_file_list.append(file_path)

    # Identify changed files using incremental indexer
    added_files, modified_files, deleted_files = indexer.get_changed_files(base_path, current_file_list)

    # Clean up deleted files metadata
    indexer.clean_deleted_files(deleted_files)

    print(f"Incremental indexing: Added: {len(added_files)}, Modified: {len(modified_files)}, Deleted: {len(deleted_files)}")

    # Only process changed files (added + modified) for efficiency
    changed_files = added_files + modified_files
    if not changed_files and not deleted_files:
        print("No changes detected, using existing index")
        # Count existing files in the metadata
        file_count = len(indexer.file_metadata)
        return file_count

    # Use parallel processing for chunked indexing of changed files
    if changed_files:
        print(f"Processing {len(changed_files)} changed files using parallel indexing...")
        
        # Create indexing tasks for changed files
        indexing_tasks = []
        for file_path in changed_files:
            full_file_path = os.path.join(base_path, file_path)
            
            # Skip if file doesn't exist (might have been deleted)
            if not os.path.exists(full_file_path):
                continue
            
            # Get file info
            _, ext = os.path.splitext(file_path)
            task = IndexingTask(
                directory_path=base_path,
                files=[file_path],
                task_id=file_path,
                metadata={"extension": ext}
            )
            indexing_tasks.append(task)
        
        # Process tasks using parallel indexer
        if indexing_tasks:
            parallel_indexer = ParallelIndexer()
            
            # Process files in parallel chunks
            try:
                # Run the parallel processing
                results = asyncio.run(parallel_indexer.process_files(indexing_tasks))
                
                # Merge results into file_index
                for result in results:
                    if result.success:
                        # Process each indexed file in the result
                        for file_info in result.indexed_files:
                            file_path = file_info['path']
                            
                            # Navigate to the correct directory in the index
                            current_dir = file_index
                            rel_path = os.path.dirname(file_path)
                            
                            # Skip the '.' directory (base_path itself)
                            if rel_path and rel_path != '.':
                                # Split the path and navigate/create the tree
                                path_parts = rel_path.replace('\\', '/').split('/')
                                for part in path_parts:
                                    if part not in current_dir:
                                        current_dir[part] = {}
                                    current_dir = current_dir[part]
                            
                            # Add file to index
                            filename = os.path.basename(file_path)
                            current_dir[filename] = {
                                "type": "file",
                                "path": file_path,
                                "ext": file_info.get("extension", "")
                            }
                            file_count += 1
                            
                            # Update file metadata
                            full_file_path = os.path.join(base_path, file_path)
                            indexer.update_file_metadata(file_path, full_file_path)
                    else:
                        print(f"Failed to index task {result.task_id}: {result.errors}")
                        
                print(f"Parallel indexing completed: {file_count} files processed")
            except Exception as e:
                print(f"Error in parallel processing: {e}")
                # Fall back to sequential processing
                print("Falling back to sequential processing...")
                
                # Sequential fallback (existing logic)
                for root, dirs, files in os.walk(base_path):
                    # Create relative path from base_path
                    rel_path = os.path.relpath(root, base_path)
                    
                    # Skip the current directory if it should be ignored by pattern matcher
                    if rel_path != '.' and ignore_matcher.should_ignore_directory(rel_path):
                        dirs[:] = []  # Don't recurse into subdirectories
                        continue
                    
                    # Check if directory should be skipped due to size/count filtering
                    if rel_path != '.' and config_manager.should_skip_directory_by_pattern(rel_path):
                        dirs[:] = []  # Don't recurse into subdirectories
                        continue
                    
                    # Count files and subdirectories for directory filtering
                    visible_files = []
                    for file in files:
                        # Skip hidden files and files with unsupported extensions
                        _, ext = os.path.splitext(file)
                        if file.startswith('.') or ext not in supported_extensions:
                            continue
                        
                        # Create file path for checking
                        file_path = os.path.join(rel_path, file).replace('\\', '/')
                        if rel_path == '.':
                            file_path = file
                        
                        # Check if file should be ignored by pattern matcher
                        if ignore_matcher.should_ignore(file_path):
                            continue
                        
                        # Check file size
                        full_file_path = os.path.join(root, file)
                        try:
                            file_size = os.path.getsize(full_file_path)
                            if config_manager.should_skip_file_by_size(file_path, file_size):
                                continue
                        except (OSError, IOError):
                            continue
                        
                        visible_files.append((file, file_path, ext))
                    
                    visible_dirs = [d for d in dirs if not ignore_matcher.should_ignore_directory(
                        os.path.join(rel_path, d) if rel_path != '.' else d
                    )]
                    
                    # Apply directory count filtering
                    if config_manager.should_skip_directory_by_count(rel_path, len(visible_files), len(visible_dirs)):
                        dirs[:] = []  # Don't recurse into subdirectories
                        continue
                    
                    # Filter directories using the ignore pattern matcher
                    dirs[:] = visible_dirs
                    
                    current_dir = file_index

                    # Skip the '.' directory (base_path itself)
                    if rel_path != '.':
                        # Split the path and navigate/create the tree
                        path_parts = rel_path.replace('\\', '/').split('/')
                        for part in path_parts:
                            if part not in current_dir:
                                current_dir[part] = {}
                            current_dir = current_dir[part]

                    # Add files to current directory and update metadata
                    for file, file_path, ext in visible_files:
                        # Only add to index if it's a changed file or if we're doing a full rebuild
                        if not changed_files or file_path in changed_files:
                            current_dir[file] = {
                                "type": "file",
                                "path": file_path,
                                "ext": ext
                            }
                            file_count += 1

                            # Update file metadata for changed files
                            if file_path in changed_files:
                                full_file_path = os.path.join(base_path, file_path)
                                indexer.update_file_metadata(file_path, full_file_path)
    else:
        print("No files to process in parallel, using existing index")

    # Save updated metadata
    indexer.save_metadata()

    # Complete performance monitoring
    if performance_monitor and indexing_context:
        try:
            # Update operation metadata with results
            indexing_context.metadata.update({
                "files_indexed": file_count,
                "files_filtered": filtered_files,
                "directories_filtered": filtered_dirs,
                "added_files": len(added_files) if 'added_files' in locals() else 0,
                "modified_files": len(modified_files) if 'modified_files' in locals() else 0,
                "deleted_files": len(deleted_files) if 'deleted_files' in locals() else 0
            })
            
            # Exit the timing context
            indexing_context.__exit__(None, None, None)
            
            # Log completion
            performance_monitor.log_structured("info", "Project indexing completed successfully", 
                                              base_path=base_path,
                                              files_indexed=file_count,
                                              files_filtered=filtered_files,
                                              directories_filtered=filtered_dirs,
                                              duration_ms=indexing_context.duration_ms)
            
            # Increment success counter
            performance_monitor.increment_counter("indexing_operations_total")
            
        except Exception as e:
            # Log indexing error
            performance_monitor.log_structured("error", "Error during indexing performance monitoring", 
                                              error=str(e))
            # Still exit the context to avoid resource leaks
            if indexing_context:
                try:
                    indexing_context.__exit__(Exception, type(e), None)
                except:
                    pass

    print(f"Indexing completed: {file_count} files indexed, {filtered_files} files filtered, {filtered_dirs} directories filtered")
    return file_count

def _count_files(directory) -> int:
    """
    Count the number of files in the index.
    Supports both dict and TrieFileIndex structures.
    """
    # Check if it's a TrieFileIndex with get_all_files method
    if hasattr(directory, 'get_all_files'):
        return len(directory.get_all_files())
    
    # Check if it's a TrieFileIndex with __len__ method
    if hasattr(directory, '__len__') and hasattr(directory, 'root'):
        return len(directory)
    
    # Check if it's a TrieFileIndex but can't call items() on it
    if hasattr(directory, 'root') and not hasattr(directory, 'items'):
        # This is a TrieFileIndex, but it doesn't have get_all_files
        # Try to get its length or return 0
        return getattr(directory, '_count', 0)
    
    # Handle regular dictionary structure
    if not isinstance(directory, dict):
        return 0
        
    count = 0
    for name, value in directory.items():
        if isinstance(value, dict):
            if "type" in value and value["type"] == "file":
                count += 1
            else:
                count += _count_files(value)
    return count

def _get_all_files(directory, prefix: str = "") -> List[Tuple[str, Dict]]:
    """Recursively get all files from the index.
    Supports both dict and TrieFileIndex structures.
    """
    # Check if it's a TrieFileIndex
    if hasattr(directory, 'get_all_files'):
        return directory.get_all_files()
    
    # Handle regular dictionary structure
    if not isinstance(directory, dict):
        return []
        
    all_files = []
    for name, item in directory.items():
        current_path = os.path.join(prefix, name)
        if isinstance(item, dict) and item.get('type') == 'file':
            all_files.append((current_path, item))
        elif isinstance(item, dict) and item.get('type') == 'directory':
            all_files.extend(_get_all_files(item.get('children', {}), current_path))
        elif isinstance(item, dict) and 'type' not in item:
            # Handle nested directory structure without explicit type
            all_files.extend(_get_all_files(item, current_path))
    return all_files

def main():
    """Main function to run the MCP server."""
    # Run the server. Tools are discovered automatically via decorators.
    mcp.run()

if __name__ == '__main__':
    # Set path to project root
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
