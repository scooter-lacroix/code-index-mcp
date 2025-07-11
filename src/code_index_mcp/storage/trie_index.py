"""
Trie-based file index.

This module implements a file index using a Trie data structure for efficient
storage and retrieval of file paths.
"""

from typing import Any, Dict, Optional, List, Tuple
from collections import defaultdict
from .storage_interface import FileIndexInterface


class TrieNode:
    def __init__(self):
        self.children = defaultdict(TrieNode)
        self.is_end_of_word = False
        self.file_info: Optional[Dict[str, Any]] = None


class TrieFileIndex(FileIndexInterface):
    """File index using Trie data structure."""
    
    def __init__(self):
        self.root = TrieNode()

    def add_file(self, file_path: str, file_type: str, extension: str, 
                 metadata: Optional[Dict[str, Any]] = None) -> bool:
        current = self.root
        parts = file_path.split('/')
        for part in parts:
            current = current.children[part]
        current.is_end_of_word = True
        current.file_info = {
            "type": file_type,
            "extension": extension,
            **(metadata or {})
        }
        return True

    def remove_file(self, file_path: str) -> bool:
        def _remove(node: TrieNode, parts: List[str], depth: int) -> bool:
            if depth == len(parts):
                if not node.is_end_of_word:
                    return False  # File not found
                node.is_end_of_word = False
                return not node.children  # If no children, node can be deleted
            part = parts[depth]
            if part not in node.children:
                return False  # File not found
            can_delete = _remove(node.children[part], parts, depth + 1)
            if can_delete:
                del node.children[part]
                return not node.children and not node.is_end_of_word
            return False
        return _remove(self.root, file_path.split('/'), 0)

    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        current = self.root
        parts = file_path.split('/')
        for part in parts:
            if part not in current.children:
                return None
            current = current.children[part]
        return current.file_info if current.is_end_of_word else None

    def find_files_by_pattern(self, pattern: str) -> List[str]:
        raise NotImplementedError("Pattern search not implemented in TrieFileIndex")

    def find_files_by_extension(self, extension: str) -> List[str]:
        result = []
        def _search(node: TrieNode, path: str):
            if node.is_end_of_word and node.file_info and node.file_info['extension'] == extension:
                result.append(path)
            for part, child_node in node.children.items():
                _search(child_node, f"{path}/{part}" if path else part)
        _search(self.root, "")
        return result

    def get_directory_structure(self, directory_path: str = "") -> Dict[str, Any]:
        raise NotImplementedError("Directory structure retrieval not implemented in TrieFileIndex")

    def get_all_files(self) -> List[Tuple[str, Dict[str, Any]]]:
        files = []
        def _gather_files(node: TrieNode, path: str):
            if node.is_end_of_word:
                files.append((path, node.file_info))
            for part, child_node in node.children.items():
                _gather_files(child_node, f"{path}/{part}" if path else part)
        _gather_files(self.root, "")
        return files
    
    def clear(self) -> None:
        """Clear all files from the index."""
        self.root = TrieNode()

