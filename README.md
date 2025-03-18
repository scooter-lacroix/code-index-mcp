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

This project uses uv for environment management and dependency installation.

1. Ensure you have Python 3.10 or later installed
2. Install uv (recommended):
   ```bash
   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Set up the environment and install dependencies:
   ```bash
   # Create virtual environment and install dependencies
   uv venv
   uv pip install -r requirements.txt
   ```

## Usage

### Running the Server

```bash
# Using Python from the virtual environment
.venv/Scripts/python server.py  # Windows
.venv/bin/python server.py     # macOS/Linux

# Or more conveniently with uv
uv run server.py
```

### Integrating with Claude Desktop

You can manually configure Claude Desktop to integrate with Code Index MCP:

1. Ensure you have completed the environment setup as described above

2. Find or create the Claude Desktop configuration file:
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

3. Add the following configuration (replace with your actual path):
   ```json
   {
     "mcpServers": {
       "code-indexer": {
         "command": "uv",
         "args": ["run", "C:/path/to/your/code-index-mcp/server.py"]
       }
     }
   }
   ```

4. Restart Claude Desktop to use Code Indexer for analyzing code projects

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

4. **Project Navigation**:
   - View project structure: "Show me the structure of this project"
   - Find files matching specific patterns: "Find all test_*.py files"

## Technical Details

### Persistent Storage

All index and settings data are stored in the `.code_indexer` folder within the project directory:
- `config.json`: Project configuration information
- `file_index.pickle`: File index data
- `content_cache.pickle`: File content cache

This ensures that the entire project doesn't need to be re-indexed each time it's used.

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

## Contributing

Contributions via issues or pull requests to add new features or fix bugs are welcome.

---

*For documentation in Chinese, please see [README_zh.md](README_zh.md).*
