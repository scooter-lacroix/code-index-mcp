# Code Index MCP - Optimized Fork by scooter-lacroix

<div align="center">

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.8%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Performance](https://img.shields.io/badge/Performance-10x_Optimized-brightgreen)](CHANGELOG.md)
[![Version](https://img.shields.io/badge/Version-2.0.0-blue)](CHANGELOG.md)

**🚀 High-Performance, Enterprise-Grade Code Analysis Platform**

*Forked from [johnhuang316/code-index-mcp](https://github.com/johnhuang316/code-index-mcp) with comprehensive 16-step optimization*

</div>

<a href="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp/badge" alt="code-index-mcp MCP server" />
</a>

## 🚀 Fork Highlights - v2.0.0 Optimization

This fork implements a comprehensive **16-step optimization plan** that transforms the original code indexer into a high-performance, enterprise-grade platform:

### 📊 Performance Achievements
- **90%+ faster re-indexing** with incremental timestamp-based system
- **70% memory reduction** through lazy loading and intelligent caching
- **4x faster indexing** with parallel processing
- **10x faster searches** with enterprise-grade tools (Zoekt, ripgrep)
- **3-10x general performance improvements** across all operations

### 🛠️ Major New Features
1. **Incremental Indexing** - Only processes changed files
2. **Parallel Processing** - Multi-core indexing support
3. **Memory Optimization** - Intelligent lazy loading with LRU cache
4. **Enterprise Search** - Zoekt, ripgrep, ugrep integration
5. **Async Operations** - Non-blocking with progress tracking
6. **Performance Monitoring** - Comprehensive metrics and logging
7. **Smart Filtering** - Advanced gitignore and size-based filtering
8. **YAML Configuration** - Flexible settings management

### 📋 What's New
- **20+ new MCP tools** for advanced code analysis
- **Real-time progress tracking** with cancellation support
- **Memory profiling** with automatic cleanup
- **Search result caching** for 90% faster repeated searches
- **Background maintenance** and automatic optimization

*See [CHANGELOG.md](CHANGELOG.md) for complete details and [TEST_RESULTS.md](TEST_RESULTS.md) for verification.*

---

## What is Code Index MCP?

Code Index MCP is a specialized MCP server that provides intelligent code indexing and analysis capabilities. It enables Large Language Models to interact with your code repositories, offering real-time insights and navigation through complex codebases.

This server integrates with the [Model Context Protocol](https://modelcontextprotocol.io) (MCP), a standardized way for AI models to interact with external tools and data sources.

## Key Features

### 🚀 Performance & Optimization
- **Incremental Indexing**: Only processes changed files, reducing re-indexing time by 90%+
- **Parallel Processing**: 4x faster indexing with multi-core support
- **Memory Optimization**: 70% memory reduction with lazy loading and intelligent caching
- **High-Performance Search**: 10x faster searches with enterprise-grade tools (Zoekt, ripgrep, ugrep)
- **Smart Filtering**: Advanced gitignore integration and size-based filtering

### 🔍 Advanced Search & Analysis
- **Async Search**: Non-blocking search operations with real-time progress tracking
- **Multi-Pattern Search**: Concurrent search across multiple patterns with scoped results
- **Intelligent Caching**: 90% faster repeated searches with LRU cache
- **Fuzzy Search**: Native fuzzy matching with safety checks
- **Search Result Pagination**: Efficient handling of large result sets

### 🛠️ Enterprise Features
- **Progress Tracking**: Real-time progress events with cancellation support
- **Performance Monitoring**: Comprehensive metrics and Prometheus export
- **Memory Profiling**: Real-time memory usage monitoring and limits
- **Configurable Settings**: YAML-based configuration with per-project overrides
- **Storage Backends**: SQLite and trie-based optimized storage

### 🔧 Developer Experience
- **MCP Tools**: 20+ specialized tools for code analysis and management
- **Background Cleanup**: Automatic cache management and garbage collection
- **Error Recovery**: Graceful handling of failures with automatic fallbacks
- **Extensible Architecture**: Pluggable storage and search backends

## Supported File Types

The server supports multiple programming languages and file extensions including:

- Python (.py)
- JavaScript/TypeScript (.js, .ts, .jsx, .tsx, .mjs, .cjs)
- Frontend Frameworks (.vue, .svelte, .astro)
- Java (.java)
- C/C++ (.c, .cpp, .h, .hpp)
- C# (.cs)
- Go (.go)
- Ruby (.rb)
- PHP (.php)
- Swift (.swift)
- Kotlin (.kt)
- Rust (.rs)
- Scala (.scala)
- Shell scripts (.sh, .bash)
- Zig (.zig)
- Web files (.html, .css, .scss, .less, .sass, .stylus, .styl)
- Template engines (.hbs, .handlebars, .ejs, .pug)
- **Database & SQL**:
  - SQL files (.sql, .ddl, .dml)
  - Database-specific (.mysql, .postgresql, .psql, .sqlite, .mssql, .oracle, .ora, .db2)
  - Database objects (.proc, .procedure, .func, .function, .view, .trigger, .index)
  - Migration & tools (.migration, .seed, .fixture, .schema, .liquibase, .flyway)
  - NoSQL & modern (.cql, .cypher, .sparql, .gql)
- Documentation/Config (.md, .mdx, .json, .xml, .yml, .yaml)

## 📦 Installation & Setup

### Prerequisites
- Python 3.8+
- uv (recommended) or pip

### Method 1: Direct Git Installation (Recommended)

For immediate use with AI applications like LM Studio, Claude Desktop, or VS Code:

```bash
uvx git+https://github.com/scooter-lacroix/code-index-mcp.git
```

This automatically installs and runs the MCP server without manual setup.

### Method 2: Package Installation

Install from package manager:

```bash
# Using uv
uvx code-index-mcp

# Using pip
pip install code-index-mcp
```

### Method 3: Local Development Installation

For development, customization, or contributing:

#### Using uv (Recommended)

```bash
git clone https://github.com/scooter-lacroix/code-index-mcp.git
cd code-index-mcp
uv sync
```

#### Using pip

```bash
git clone https://github.com/scooter-lacroix/code-index-mcp.git
cd code-index-mcp
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows
pip install -e .
```

## 🔌 MCP Integration

The Code Index MCP server supports multiple integration methods:

### Method 1: Direct Git Integration (Recommended)

For LM Studio, Claude Desktop, VS Code, and other MCP-compatible applications:

```json
{
  "mcpServers": {
    "code-index": {
      "command": "uvx",
      "args": ["git+https://github.com/scooter-lacroix/code-index-mcp.git"],
      "env": {},
      "start_on_launch": true
    }
  }
}
```

### Method 2: Package Installation

For package manager installed versions:

```json
{
  "mcpServers": {
    "code-index": {
      "command": "code-index-mcp",
      "args": [],
      "env": {},
      "start_on_launch": true
    }
  }
}
```

### Method 3: Local Development

For locally installed versions:

```json
{
  "mcpServers": {
    "code-index": {
      "command": "uv",
      "args": ["run", "code_index_mcp"],
      "env": {},
      "start_on_launch": true
    }
  }
}
```

### Method 4: HTTP Server Mode

For web-based integrations:

```bash
# Start HTTP server
python -m code_index.server --port 8765

# Or using uv
uv run code_index.server --port 8765
```

Then configure your application:

```json
{
  "mcpServers": {
    "code-index": {
      "transport": "http",
      "url": "http://localhost:8765/mcp",
      "headers": {
        "Authorization": "Bearer your-token-here"
      }
    }
  }
}
```

### Application-Specific Configurations

**VS Code/Cursor/Windsurf** (using MCP extension):
```json
{
  "mcp.servers": {
    "code-index": {
      "command": "code-index-mcp",
      "args": [],
      "env": {},
      "transport": "stdio"
    }
  }
}
```

**Jan AI**:
```json
{
  "mcp_servers": {
    "code-index": {
      "command": "code-index-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

**OpenHands**:
```json
{
  "mcp": {
    "servers": {
      "code-index": {
        "command": "code-index-mcp",
        "args": [],
        "env": {}
      }
    }
  }
}
```

## 🛠️ Usage

### Command Line Interface

```bash
# Start stdio server (MCP integration)
code-index-mcp

# Start HTTP server (web integration)
code-index-mcp --http --port 8765

# Local development
uv run code_index_mcp
```

### Debug with MCP Inspector

```bash
# For git installation
npx @modelcontextprotocol/inspector uvx git+https://github.com/scooter-lacroix/code-index-mcp.git

# For package installation
npx @modelcontextprotocol/inspector code-index-mcp

# For local development
npx @modelcontextprotocol/inspector uv run code_index_mcp
```

## Available Tools

### Core Tools

- **set_project_path**: Sets the base project path for indexing.
- **search_code**: Enhanced search using external tools (ugrep/ripgrep/ag/grep) with fuzzy matching support.
- **find_files**: Finds files in the project matching a given pattern.
- **get_file_summary**: Gets a summary of a specific file, including line count, functions, imports, etc.
- **refresh_index**: Refreshes the project index.
- **get_settings_info**: Gets information about the project settings.

### Utility Tools

- **create_temp_directory**: Creates the temporary directory used for storing index data.
- **check_temp_directory**: Checks the temporary directory used for storing index data.
- **clear_settings**: Clears all settings and cached data.
- **refresh_search_tools**: Manually re-detect available command-line search tools (e.g., ripgrep).

## Common Workflows and Examples

Here’s a typical workflow for using Code Index MCP with an AI assistant like Claude.

### 1. Set Project Path & Initial Indexing

This is the first and most important step. When you set the project path, the server automatically creates a file index for the first time or loads a previously cached one.

**Example Prompt:**
```
Please set the project path to C:\Users\username\projects\my-react-app
```

### 2. Refresh the Index (When Needed)

If you make significant changes to your project files after the initial setup, you can manually refresh the index to ensure all tools are working with the latest information.

**Example Prompt:**
```
I've just added a few new components, please refresh the project index.
```
*(The assistant would use the `refresh_index` tool)*

### 3. Explore the Project Structure

Once the index is ready, you can find files using patterns (globs) to understand the codebase and locate relevant files.

**Example Prompt:**
```
Find all TypeScript component files in the 'src/components' directory.
```
*(The assistant would use the `find_files` tool with a pattern like `src/components/**/*.tsx`)*

### 4. Analyze a Specific File

Before diving into the full content of a file, you can get a quick summary of its structure, including functions, classes, and imports.

**Example Prompt:**
```
Can you give me a summary of the 'src/api/userService.ts' file?
```
*(The assistant would use the `get_file_summary` tool)*

### 5. Search for Code

With an up-to-date index, you can search for code snippets, function names, or any text pattern to find where specific logic is implemented.

**Example: Simple Search**
```
Search for all occurrences of the "processData" function.
```

**Example: Search with Fuzzy Matching**
```
I'm looking for a function related to user authentication, it might be named 'authUser', 'authenticateUser', or something similar. Can you do a fuzzy search for 'authUser'?
```

**Example: Search within Specific Files**
```
Search for the string "API_ENDPOINT" only in Python files.
```
*(The assistant would use the `search_code` tool with the `file_pattern` parameter set to `*.py`)*

## Development

### Building from Source

1. Clone the repository:

```bash
git clone https://github.com/username/code-index-mcp.git
cd code-index-mcp
```

2. Install dependencies:

```bash
uv sync
```

3. Run the server locally:

```bash
uv run code_index_mcp
```

## Debugging

You can use the MCP inspector to debug the server:

```bash
npx @modelcontextprotocol/inspector uvx code-index-mcp
```

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Languages

- [繁體中文](README_zh.md)
