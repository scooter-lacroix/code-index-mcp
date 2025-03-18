"""
Test script for the Code Index MCP Server.

Run this script to test the basic functionality of the server.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Create temporary test files
TEST_FILES = {
    'main.py': '''
def hello():
    """Says hello"""
    print("Hello, world!")

if __name__ == "__main__":
    hello()
''',
    'utils/helper.py': '''
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
''',
    'config.json': '''
{
    "name": "test-project",
    "version": "1.0.0"
}
'''
}

class TestCodeIndexServer(unittest.TestCase):
    def setUp(self):
        """Create a temporary directory with test files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        
        # Create test files
        for path, content in TEST_FILES.items():
            file_path = self.base_path / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            
        # Add server.py to Python path
        sys.path.insert(0, os.getcwd())
        
    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()
        
    def test_index_project(self):
        """Test that the project indexing function works."""
        # Import functions from server.py
        from server import _index_project, file_index
        
        # Index the temp directory
        file_count = _index_project(str(self.base_path))
        
        # Check that all files were indexed
        self.assertEqual(file_count, 3)
        
        # Check that the directory structure is correct
        self.assertIn('main.py', file_index)
        self.assertIn('config.json', file_index)
        self.assertIn('utils', file_index)
        self.assertIn('helper.py', file_index['utils'])
        
    def test_get_all_files(self):
        """Test that the get_all_files function works."""
        # Import functions from server.py
        from server import _index_project, _get_all_files
        
        # Index the temp directory
        _index_project(str(self.base_path))
        
        # Get all files
        from server import file_index
        files = _get_all_files(file_index)
        
        # Check that all files were found
        self.assertEqual(len(files), 3)
        
        # Check file paths
        paths = [f[0] for f in files]
        self.assertIn('main.py', paths)
        self.assertIn('config.json', paths)
        self.assertIn('utils/helper.py', paths)

if __name__ == "__main__":
    unittest.main()
