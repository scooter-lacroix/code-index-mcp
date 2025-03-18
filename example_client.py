"""
Example client script for the Code Index MCP Server.

This script shows how to programmatically interact with the Code Index MCP Server.
"""
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # Create server parameters for stdio connection
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            
            print("Connected to Code Index MCP Server\n")
            
            # List available tools
            print("Available Tools:")
            tools = await session.list_tools()
            for tool in tools:
                print(f"  - {tool['name']}: {tool['description']}")
            print()
            
            # Set project path (use a known code directory)
            print("Setting project path...")
            result = await session.call_tool(
                "set_project_path", 
                arguments={"path": "."}  # Index the current directory
            )
            print(f"Result: {result}\n")
            
            # Get project structure
            print("Getting project structure...")
            content, _ = await session.read_resource("structure://project")
            structure = json.loads(content)
            print(f"Project structure: {len(structure)} top-level items\n")
            
            # Search for some code
            print("Searching for 'mcp.tool'...")
            results = await session.call_tool(
                "search_code",
                arguments={
                    "query": "mcp.tool",
                    "extensions": [".py"],
                    "case_sensitive": False
                }
            )
            print(f"Found {len(results)} files with matches:")
            for file, matches in results.items():
                print(f"  - {file}: {len(matches)} matches")
            print()
            
            # Get a file summary
            print("Getting file summary for server.py...")
            summary = await session.call_tool(
                "get_file_summary",
                arguments={"file_path": "server.py"}
            )
            print(f"File summary:")
            print(f"  - Lines: {summary.get('line_count')}")
            print(f"  - Functions: {summary.get('function_count', 'N/A')}")
            print(f"  - Classes: {summary.get('class_count', 'N/A')}")
            print()

if __name__ == "__main__":
    asyncio.run(main())
