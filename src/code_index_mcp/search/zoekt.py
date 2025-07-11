"""
Zoekt Search Strategy

This module implements a search strategy using Zoekt, a fast trigram-based
code search engine designed for enterprise-scale performance.
"""

import os
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple
from .base import SearchStrategy, parse_search_output


class ZoektStrategy(SearchStrategy):
    """
    Zoekt search strategy for enterprise-grade performance.
    
    Zoekt is a fast trigram-based code search engine that builds an index
    for extremely fast searches. It's designed for large codebases and
    provides excellent performance for both literal and regex searches.
    """
    
    def __init__(self, index_dir: Optional[str] = None):
        """
        Initialize Zoekt strategy.
        
        Args:
            index_dir: Directory to store Zoekt index. If None, uses system temp.
        """
        self.index_dir = index_dir or os.path.join(tempfile.gettempdir(), "zoekt_index")
        self._zoekt_path = None
        self._zoekt_index_path = None
        self._index_initialized = False
    
    @property
    def name(self) -> str:
        """The name of the search tool."""
        return "zoekt"
    
    def is_available(self) -> bool:
        """Check if Zoekt is available on the system."""
        try:
            # First try standard PATH lookup
            self._zoekt_path = shutil.which("zoekt")
            self._zoekt_index_path = shutil.which("zoekt-index")
            
            # If not found in PATH, try common Go installation locations
            if not self._zoekt_path or not self._zoekt_index_path:
                # Get Go path from environment or use default
                go_paths = []
                
                # Try to get GOPATH from environment
                try:
                    gopath_result = subprocess.run(
                        ["go", "env", "GOPATH"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if gopath_result.returncode == 0:
                        gopath = gopath_result.stdout.strip()
                        if gopath:
                            go_paths.append(os.path.join(gopath, "bin"))
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    pass
                
                # Add common Go binary locations
                home_dir = os.path.expanduser("~")
                go_paths.extend([
                    os.path.join(home_dir, "go", "bin"),
                    "/usr/local/go/bin",
                    "/opt/go/bin"
                ])
                
                # Search for zoekt binaries in Go paths
                for go_bin_path in go_paths:
                    if os.path.exists(go_bin_path):
                        zoekt_path = os.path.join(go_bin_path, "zoekt")
                        zoekt_index_path = os.path.join(go_bin_path, "zoekt-index")
                        
                        if os.path.exists(zoekt_path) and os.path.exists(zoekt_index_path):
                            self._zoekt_path = zoekt_path
                            self._zoekt_index_path = zoekt_index_path
                            break
            
            # If still not found, return False
            if not self._zoekt_path or not self._zoekt_index_path:
                return False
            
            # Test if we can run zoekt
            result = subprocess.run(
                [self._zoekt_path, "--help"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
    
    def _ensure_index_exists(self, base_path: str) -> bool:
        """
        Ensure that a Zoekt index exists for the given base path.
        
        Args:
            base_path: The base directory to index
            
        Returns:
            True if index exists or was created successfully, False otherwise
        """
        if not os.path.exists(self.index_dir):
            os.makedirs(self.index_dir, exist_ok=True)
        
        # Check if index already exists and is up to date
        index_files = [f for f in os.listdir(self.index_dir) if f.endswith('.zoekt')]
        if index_files and self._index_initialized:
            return True
        
        try:
            # Create index using zoekt-index
            cmd = [
                self._zoekt_index_path,
                "-index", self.index_dir,
                base_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout for indexing
            )
            
            if result.returncode == 0:
                self._index_initialized = True
                return True
            else:
                print(f"Zoekt indexing failed: {result.stderr}")
                return False
                
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            print(f"Error creating Zoekt index: {e}")
            return False
    
    def search(
        self,
        pattern: str,
        base_path: str,
        case_sensitive: bool = True,
        context_lines: int = 0,
        file_pattern: Optional[str] = None,
        fuzzy: bool = False
    ) -> Dict[str, List[Tuple[int, str]]]:
        """
        Execute a search using Zoekt.
        
        Args:
            pattern: The search pattern
            base_path: The root directory to search in
            case_sensitive: Whether the search is case-sensitive
            context_lines: Number of context lines to show around each match
            file_pattern: Glob pattern to filter files (e.g., "*.py")
            fuzzy: Whether to enable fuzzy search (treated as regex for Zoekt)
            
        Returns:
            A dictionary mapping filenames to lists of (line_number, line_content) tuples
        """
        if not self.is_available():
            raise RuntimeError("Zoekt is not available on this system")
        
        # Ensure index exists
        if not self._ensure_index_exists(base_path):
            raise RuntimeError("Failed to create or access Zoekt index")
        
        try:
            # Build zoekt command with parallel and scoped search
            cmd = [self._zoekt_path, "-index_dir", self.index_dir, "--parallelism", str(os.cpu_count())]
            
            # Add case sensitivity flag
            if not case_sensitive:
                cmd.append("-i")
            
            # Add context lines
            if context_lines > 0:
                cmd.extend(["-A", str(context_lines), "-B", str(context_lines)])
            
            # Add file pattern if specified
            if file_pattern:
                # Convert glob pattern to regex for Zoekt
                if file_pattern.startswith("*."):
                    # Simple extension pattern
                    ext = file_pattern[2:]
                    cmd.extend(["-f", f".*\\.{ext}$"])
                else:
                    # More complex pattern - convert to regex
                    import fnmatch
                    regex_pattern = fnmatch.translate(file_pattern)
                    cmd.extend(["-f", regex_pattern])
            
            # Add the search pattern
            if fuzzy:
                # For fuzzy search, treat as regex
                cmd.append(pattern)
            else:
                # For literal search, escape special regex characters
                import re
                escaped_pattern = re.escape(pattern)
                cmd.append(escaped_pattern)
            
            # Execute search
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout for searches
            )
            
            if result.returncode == 0:
                # Parse Zoekt output format
                return self._parse_zoekt_output(result.stdout, base_path)
            else:
                # Handle search errors
                if result.returncode == 1:
                    # No matches found - this is normal
                    return {}
                else:
                    raise RuntimeError(f"Zoekt search failed: {result.stderr}")
                    
        except subprocess.TimeoutExpired:
            raise RuntimeError("Zoekt search timed out")
        except (FileNotFoundError, OSError) as e:
            raise RuntimeError(f"Error running Zoekt: {e}")
    
    def _parse_zoekt_output(self, output: str, base_path: str) -> Dict[str, List[Tuple[int, str]]]:
        """
        Parse Zoekt output format.
        
        Zoekt output format is similar to grep:
        filename:line_number:content
        
        Args:
            output: Raw output from Zoekt
            base_path: Base path for making paths relative
            
        Returns:
            Parsed search results
        """
        # Zoekt output is similar to grep, so we can reuse the parse function
        return parse_search_output(output, base_path)
    
    def refresh_index(self, base_path: str) -> bool:
        """
        Refresh the Zoekt index for the given base path.
        
        Args:
            base_path: The base directory to re-index
            
        Returns:
            True if index was refreshed successfully, False otherwise
        """
        try:
            # Remove existing index
            if os.path.exists(self.index_dir):
                import shutil
                shutil.rmtree(self.index_dir)
            
            # Reset initialization flag
            self._index_initialized = False
            
            # Recreate index
            return self._ensure_index_exists(base_path)
            
        except Exception as e:
            print(f"Error refreshing Zoekt index: {e}")
            return False
    
    def get_index_info(self) -> Dict[str, any]:
        """
        Get information about the current Zoekt index.
        
        Returns:
            Dictionary with index information
        """
        info = {
            "index_dir": self.index_dir,
            "index_exists": os.path.exists(self.index_dir),
            "index_initialized": self._index_initialized,
            "zoekt_path": self._zoekt_path,
            "zoekt_index_path": self._zoekt_index_path
        }
        
        if os.path.exists(self.index_dir):
            index_files = [f for f in os.listdir(self.index_dir) if f.endswith('.zoekt')]
            info["index_files"] = index_files
            info["index_file_count"] = len(index_files)
            
            # Calculate total index size
            total_size = 0
            for filename in index_files:
                file_path = os.path.join(self.index_dir, filename)
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
            info["index_size_bytes"] = total_size
            info["index_size_mb"] = round(total_size / (1024 * 1024), 2)
        
        return info
