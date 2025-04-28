# Code Index MCP

Code Index MCP is a Model Context Protocol server that enables large language models (LLMs) to index, search, and analyze code in project directories.

## Features

- Index and navigate project file structures
- Search for specific patterns in code
- Get detailed file summaries
- Analyze code structure and complexity
- Support for multiple programming languages
- Persistent storage of project settings

## Installation

This project uses two key tools:

1. **uv**: A fast Python package manager for dependency installation
2. **uvx**: A command-line tool provided by this package to run the Code Index MCP server

### Installation Steps

1. Ensure you have Python 3.10 or later installed

2. Install uv (recommended but not required):
   ```bash
   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Install the code-index-mcp package to get the uvx command:
   ```bash
   # Using uv (recommended)
   uv pip install code-index-mcp

   # Or using traditional pip
   pip install code-index-mcp
   ```

4. After installation, you can use the uvx command:
   ```bash
   uvx /path/to/your/project
   ```

### Installing from Source

If you want to install from source code:

1. Clone the repository:
   ```bash
   git clone https://github.com/johnhuang316/code-index-mcp.git
   cd code-index-mcp
   ```

2. Install the package (this will also install the uvx command):
   ```bash
   # Using uv (recommended)
   uv pip install -e .

   # Or using traditional pip
   pip install -e .
   ```

## Usage

### Running the Server Directly

There are multiple ways to run the server:

```bash
# Using the uvx command (requires installing the package first)
uvx

# Using uv to run the script directly (doesn't require installing the package)
uv run run.py

# Using Python directly (doesn't require installing the package)
python -m code_index_mcp.server
```

UV will automatically handle all dependency installations based on the project's configuration.

### Using Docker

You can also use Code Index MCP as a containerized tool with Docker:

```bash
# Build the Docker image
docker build -t code-index-mcp .

# Use the container as a tool to analyze your code
docker run --rm -i code-index-mcp
```

This containerized approach works well with Claude Desktop, which treats MCP servers as on-demand processes rather than persistent servers. Claude Desktop will start the container when needed and communicate with it via stdio, keeping it running only for the duration of the session.

When using the containerized version, you'll need to set the project path explicitly using the `set_project_path` tool, just like in the non-containerized version.

### Integrating with Claude Desktop

You can easily integrate Code Index MCP with Claude Desktop:

#### Prerequisites

1. Make sure you have completed the appropriate installation steps above
2. Verify that the command you plan to use is available:
   - For Option 1: Verify `uvx` is available by running `uvx --help` in your terminal
   - For Option 2: Make sure you have the source code repository
   - For Option 3: Ensure Docker is installed and the image is built

#### Configuration Steps

1. Find or create the Claude Desktop configuration file:
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS/Linux: `~/Library/Application Support/Claude/claude_desktop_config.json`

2. Add the appropriate configuration based on your preferred method:

#### Option 1: Using uvx (Recommended, requires package installation)

   **For Windows**:

   ```json
   {
     "mcpServers": {
       "code-indexer": {
         "command": "uvx",
         "args": [
            "C:\\Users\\username\\path\\to\\project"
          ]
       }
     }
   }
   ```

   **For macOS/Linux**:

   ```json
   {
     "mcpServers": {
       "code-indexer": {
         "command": "uvx",
         "args": [
            "/Users/username/path/to/project"
          ]
       }
     }
   }
   ```

   **Note**: The `uvx` command is available after installing the package with `pip install code-index-mcp` or `uv pip install code-index-mcp`.

#### Option 2: Using Python directly (No package installation required)

   ```json
   {
     "mcpServers": {
       "code-indexer": {
         "command": "python",
         "args": [
           "-m",
           "code_index_mcp.server"
         ],
         "cwd": "C:\\path\\to\\code-index-mcp"
       }
     }
   }
   ```

   **Note**: This option requires specifying the full path to the source code repository in the `cwd` parameter.

#### Option 3: Using Docker (Containerized)

1. Build the Docker image as described in the Docker section above
2. Find or create the Claude Desktop configuration file (same locations as above)
3. Add the following configuration:

   ```json
   {
     "mcpServers": {
       "code-indexer": {
         "command": "docker",
         "args": [
            "run",
            "-i",
            "--rm",
            "code-index-mcp"
          ]
       }
     }
   }
   ```

   **Note**: This configuration allows Claude Desktop to start the containerized MCP tool on demand.

4. Restart Claude Desktop to use Code Indexer for analyzing code projects

Claude Desktop will start the MCP server as an on-demand process when needed, communicate with it via stdio, and keep it running only for the duration of your session.

### Basic Workflow

1. **Set Project Path** (required first step):

   - When using for the first time, you must set the project path to analyze
   - Through Claude command: "I need to analyze a project, help me set up the project path"
   - Provide the complete project directory path
2. **Code Search**:

   - Search for specific keywords or patterns: "Search for 'function name' in the project"
   - Filter by file type: "Search for 'import' in all .py files"
3. **File Analysis**:

   - Analyze specific files: "Analyze the file src/main.py"
   - Get file summaries: "Give me a list of functions in utils/helpers.js"
3. **Project Navigation**:

   - View project structure: "Show me the structure of this project"
   - Find files matching specific patterns: "Find all test_*.py files"

## Technical Details

### Persistent Storage

All index and settings data are stored in the system temporary directory, in a subfolder specific to each project:

- Windows: `%TEMP%\code_indexer\[project_hash]\`
- Linux/macOS: `/tmp/code_indexer/[project_hash]/`

Each project's data includes:
- `config.json`: Project configuration information
- `file_index.pickle`: File index data
- `content_cache.pickle`: File content cache

This approach ensures that:
1. Different projects' data are kept separate
2. The data is automatically cleaned up by the OS when no longer needed
3. In containerized environments, the data is stored in the container's temporary directory

### Dependency Management with UV

Code Index MCP uses UV for dependency management, which provides several advantages:

- Automatic dependency resolution based on project requirements
- Faster package installation and environment setup
- Consistent dependency versions via the lock file

### Supported File Types

The following file types are currently supported for indexing and analysis:

- Python (.py)
- JavaScript/TypeScript (.js, .ts, .jsx, .tsx)
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
- Shell (.sh, .bash)
- HTML/CSS (.html, .css, .scss)
- Markdown (.md)
- JSON (.json)
- XML (.xml)
- YAML (.yml, .yaml)

## Security Considerations

- File path validation prevents directory traversal attacks
- Absolute path access is not allowed
- Project path must be explicitly set, with no default value
- Index data is stored in the system temporary directory, not in the project directory
- Each project's data is stored in a separate directory based on the project path's hash

## Contributing

Contributions via issues or pull requests to add new features or fix bugs are welcome.

---

*For documentation in Chinese, please see [README_zh.md](README_zh.md).*
