"""
Storage interface for code index backends.

This module defines the interface that all storage backends must implement
to ensure consistent API across different storage implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Iterator, Tuple


class StorageInterface(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def put(self, key: str, value: Any) -> bool:
        """Store a key-value pair.
        
        Args:
            key: The key to store
            value: The value to store
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value by key.
        
        Args:
            key: The key to retrieve
            
        Returns:
            The value if found, None otherwise
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a key-value pair.
        
        Args:
            key: The key to delete
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a key exists.
        
        Args:
            key: The key to check
            
        Returns:
            True if key exists, False otherwise
        """
        pass
    
    @abstractmethod
    def keys(self, pattern: Optional[str] = None) -> Iterator[str]:
        """Iterate over keys, optionally filtered by pattern.
        
        Args:
            pattern: Optional pattern to filter keys
            
        Yields:
            Keys matching the pattern
        """
        pass
    
    @abstractmethod
    def items(self, pattern: Optional[str] = None) -> Iterator[Tuple[str, Any]]:
        """Iterate over key-value pairs, optionally filtered by pattern.
        
        Args:
            pattern: Optional pattern to filter keys
            
        Yields:
            Key-value pairs matching the pattern
        """
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """Clear all data.
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def size(self) -> int:
        """Get the number of stored items.
        
        Returns:
            Number of items in storage
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the storage backend and release resources."""
        pass
    
    @abstractmethod
    def flush(self) -> bool:
        """Flush any pending operations to persistent storage.
        
        Returns:
            True if successful, False otherwise
        """
        pass


class FileIndexInterface(ABC):
    """Abstract interface for file index storage."""
    
    @abstractmethod
    def add_file(self, file_path: str, file_type: str, extension: str, 
                 metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add a file to the index.
        
        Args:
            file_path: Path to the file
            file_type: Type of the file (e.g., 'file', 'directory')
            extension: File extension
            metadata: Optional metadata dictionary
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def remove_file(self, file_path: str) -> bool:
        """Remove a file from the index.
        
        Args:
            file_path: Path to the file to remove
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get information about a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File information dictionary if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_files_by_pattern(self, pattern: str) -> List[str]:
        """Find files matching a pattern.
        
        Args:
            pattern: Pattern to search for
            
        Returns:
            List of file paths matching the pattern
        """
        pass
    
    @abstractmethod
    def find_files_by_extension(self, extension: str) -> List[str]:
        """Find files with a specific extension.
        
        Args:
            extension: File extension to search for
            
        Returns:
            List of file paths with the specified extension
        """
        pass
    
    @abstractmethod
    def get_directory_structure(self, directory_path: str = "") -> Dict[str, Any]:
        """Get the directory structure.
        
        Args:
            directory_path: Optional directory path to get structure for
            
        Returns:
            Dictionary representing the directory structure
        """
        pass
    
    @abstractmethod
    def get_all_files(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Get all files in the index.
        
        Returns:
            List of tuples (file_path, file_info)
        """
        pass
