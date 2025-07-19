"""
SQLite-based storage backend.

This module implements storage backends using SQLite for efficient
key-value storage and full-text search capabilities.
"""

import sqlite3
import json
import os
import fnmatch
from typing import Any, Dict, Optional, List, Tuple, Iterator
from pathlib import Path
from .storage_interface import StorageInterface, FileIndexInterface


class SQLiteStorage(StorageInterface):
    """SQLite-based key-value storage with FTS support."""
    
    def __init__(self, db_path: str, enable_fts: bool = True):
        """Initialize SQLite storage.
        
        Args:
            db_path: Path to SQLite database file
            enable_fts: Whether to enable Full-Text Search
        """
        self.db_path = db_path
        self.enable_fts = enable_fts
        self._ensure_db_directory()
        self._init_db()
    
    def _ensure_db_directory(self):
        """Ensure the directory for the database exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Create main key-value table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value BLOB,
                    value_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create FTS table if enabled
            if self.enable_fts:
                conn.execute('''
                    CREATE VIRTUAL TABLE IF NOT EXISTS kv_fts USING fts5(
                        key, value_text, content='kv_store', content_rowid='rowid'
                    )
                ''')
                
                # Create triggers to maintain FTS index
                conn.execute('''
                    CREATE TRIGGER IF NOT EXISTS kv_store_ai AFTER INSERT ON kv_store BEGIN
                        INSERT INTO kv_fts(rowid, key, value_text) 
                        VALUES (new.rowid, new.key, CASE 
                            WHEN new.value_type = 'text' THEN new.value
                            ELSE ''
                        END);
                    END
                ''')
                
                conn.execute('''
                    CREATE TRIGGER IF NOT EXISTS kv_store_ad AFTER DELETE ON kv_store BEGIN
                        INSERT INTO kv_fts(kv_fts, rowid, key, value_text) 
                        VALUES ('delete', old.rowid, old.key, CASE 
                            WHEN old.value_type = 'text' THEN old.value
                            ELSE ''
                        END);
                    END
                ''')
                
                conn.execute('''
                    CREATE TRIGGER IF NOT EXISTS kv_store_au AFTER UPDATE ON kv_store BEGIN
                        INSERT INTO kv_fts(kv_fts, rowid, key, value_text) 
                        VALUES ('delete', old.rowid, old.key, CASE 
                            WHEN old.value_type = 'text' THEN old.value
                            ELSE ''
                        END);
                        INSERT INTO kv_fts(rowid, key, value_text) 
                        VALUES (new.rowid, new.key, CASE 
                            WHEN new.value_type = 'text' THEN new.value
                            ELSE ''
                        END);
                    END
                ''')
            
            # Create file_versions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS file_versions (
                    version_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    content BLOB NOT NULL,
                    hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    size INTEGER NOT NULL
                )
            ''')

            # Create file_diffs table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS file_diffs (
                    diff_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    previous_version_id TEXT,
                    current_version_id TEXT NOT NULL,
                    diff_content BLOB NOT NULL,
                    diff_type TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    operation_details TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (previous_version_id) REFERENCES file_versions(version_id),
                    FOREIGN KEY (current_version_id) REFERENCES file_versions(version_id)
                )
            ''')

            conn.commit()
    
    def put(self, key: str, value: Any) -> bool:
        """Store a key-value pair."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if isinstance(value, str):
                    value_blob = value.encode('utf-8')
                    value_type = 'text'
                else:
                    value_blob = json.dumps(value).encode('utf-8')
                    value_type = 'json'
                
                conn.execute('''
                    INSERT OR REPLACE INTO kv_store (key, value, value_type, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (key, value_blob, value_type))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Error storing key {key}: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value by key."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT value, value_type FROM kv_store WHERE key = ?',
                    (key,)
                )
                row = cursor.fetchone()
                
                if row is None:
                    return None
                
                value_blob, value_type = row
                if value_type == 'text':
                    return value_blob.decode('utf-8')
                else:
                    return json.loads(value_blob.decode('utf-8'))
                    
        except Exception as e:
            print(f"Error retrieving key {key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete a key-value pair."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('DELETE FROM kv_store WHERE key = ?', (key,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT 1 FROM kv_store WHERE key = ? LIMIT 1',
                    (key,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"Error checking key existence {key}: {e}")
            return False
    
    def keys(self, pattern: Optional[str] = None) -> Iterator[str]:
        """Iterate over keys, optionally filtered by pattern."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if pattern:
                    cursor = conn.execute('SELECT key FROM kv_store ORDER BY key')
                    for row in cursor:
                        key = row[0]
                        if fnmatch.fnmatch(key, pattern):
                            yield key
                else:
                    cursor = conn.execute('SELECT key FROM kv_store ORDER BY key')
                    for row in cursor:
                        yield row[0]
        except Exception as e:
            print(f"Error iterating keys: {e}")
    
    def items(self, pattern: Optional[str] = None) -> Iterator[Tuple[str, Any]]:
        """Iterate over key-value pairs, optionally filtered by pattern."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT key, value, value_type FROM kv_store ORDER BY key')
                for row in cursor:
                    key, value_blob, value_type = row
                    if pattern and not fnmatch.fnmatch(key, pattern):
                        continue
                    
                    if value_type == 'text':
                        value = value_blob.decode('utf-8')
                    else:
                        value = json.loads(value_blob.decode('utf-8'))
                    
                    yield key, value
        except Exception as e:
            print(f"Error iterating items: {e}")
    
    def clear(self) -> bool:
        """Clear all data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM kv_store')
                if self.enable_fts:
                    conn.execute('DELETE FROM kv_fts')
                conn.commit()
                # Ensure tables are properly initialized after clearing
                self._init_db()
                return True
        except Exception as e:
            print(f"Error clearing data: {e}")
            # Try to reinitialize the database in case of schema issues
            try:
                self._init_db()
                return True
            except Exception as init_e:
                print(f"Error reinitializing database after clear: {init_e}")
                return False
    
    def size(self) -> int:
        """Get the number of stored items."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM kv_store')
                return cursor.fetchone()[0]
        except Exception as e:
            print(f"Error getting size: {e}")
            return 0
    
    def close(self) -> None:
        """Close the storage backend."""
        # SQLite connections are managed per-operation, so no persistent connection to close
        pass

    def insert_file_version(self, version_id: str, file_path: str, content: str, hash: str, timestamp: str, size: int) -> bool:
        """Inserts a new file version into the file_versions table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO file_versions (version_id, file_path, content, hash, timestamp, size)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (version_id, file_path, content.encode('utf-8'), hash, timestamp, size))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error inserting file version {version_id} for {file_path}: {e}")
            return False

    def insert_file_diff(self, diff_id: str, file_path: str, previous_version_id: Optional[str], current_version_id: str, diff_content: str, diff_type: str, operation_type: str, operation_details: Optional[str], timestamp: str) -> bool:
        """Inserts a new file diff into the file_diffs table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO file_diffs (diff_id, file_path, previous_version_id, current_version_id, diff_content, diff_type, operation_type, operation_details, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (diff_id, file_path, previous_version_id, current_version_id, diff_content.encode('utf-8'), diff_type, operation_type, operation_details, timestamp))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error inserting file diff {diff_id} for {file_path}: {e}")
            return False

    def get_file_version(self, version_id: str) -> Optional[Dict]:
        """Retrieves a file version by its ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('SELECT * FROM file_versions WHERE version_id = ?', (version_id,))
                row = cursor.fetchone()
                if row:
                    version_data = dict(row)
                    version_data['content'] = version_data['content'].decode('utf-8')
                    return version_data
                return None
        except Exception as e:
            print(f"Error retrieving file version {version_id}: {e}")
            return None

    def get_file_diffs_for_path(self, file_path: str) -> List[Dict]:
        """Retrieves all diffs for a given file path."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('SELECT * FROM file_diffs WHERE file_path = ? ORDER BY timestamp ASC', (file_path,))
                diffs = []
                for row in cursor.fetchall():
                    diff_data = dict(row)
                    diff_data['diff_content'] = diff_data['diff_content'].decode('utf-8')
                    diffs.append(diff_data)
                return diffs
        except Exception as e:
            print(f"Error retrieving file diffs for {file_path}: {e}")
            return []

    def get_file_versions_for_path(self, file_path: str) -> List[Dict]:
        """Retrieves all versions for a given file path, ordered by timestamp."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('SELECT * FROM file_versions WHERE file_path = ? ORDER BY timestamp ASC', (file_path,))
                versions = []
                for row in cursor.fetchall():
                    version_data = dict(row)
                    version_data['content'] = version_data['content'].decode('utf-8')
                    versions.append(version_data)
                return versions
        except Exception as e:
            print(f"Error retrieving file versions for {file_path}: {e}")
            return []
    
    def flush(self) -> bool:
        """Flush any pending operations."""
        # SQLite operations are immediately committed, so no buffering to flush
        return True
    
    def search(self, query: str) -> List[Tuple[str, Any]]:
        """Search using Full-Text Search (if enabled).
        
        Args:
            query: Search query
            
        Returns:
            List of (key, value) tuples matching the query
        """
        if not self.enable_fts:
            raise NotImplementedError("FTS not enabled for this storage instance")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT kv_store.key, kv_store.value, kv_store.value_type
                    FROM kv_fts
                    JOIN kv_store ON kv_fts.rowid = kv_store.rowid
                    WHERE kv_fts MATCH ?
                    ORDER BY rank
                ''', (query,))
                
                results = []
                for row in cursor:
                    key, value_blob, value_type = row
                    if value_type == 'text':
                        value = value_blob.decode('utf-8')
                    else:
                        value = json.loads(value_blob.decode('utf-8'))
                    results.append((key, value))
                
                return results
        except Exception as e:
            print(f"Error searching: {e}")
            return []


class SQLiteFileIndex(FileIndexInterface):
    """SQLite-based file index with advanced query capabilities."""
    
    def __init__(self, db_path: str):
        """Initialize SQLite file index.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_db()
    
    def _ensure_db_directory(self):
        """Ensure the directory for the database exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Create files table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_type TEXT NOT NULL,
                    extension TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for efficient lookups
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_files_path ON files(file_path)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_files_type ON files(file_type)
            ''')
            
            # Create FTS table for file paths
            conn.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                    file_path, content='files', content_rowid='id'
                )
            ''')
            
            # Create triggers to maintain FTS index
            conn.execute('''
                CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
                    INSERT INTO files_fts(rowid, file_path) VALUES (new.id, new.file_path);
                END
            ''')
            
            conn.execute('''
                CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
                    INSERT INTO files_fts(files_fts, rowid, file_path) 
                    VALUES ('delete', old.id, old.file_path);
                END
            ''')
            
            conn.execute('''
                CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE ON files BEGIN
                    INSERT INTO files_fts(files_fts, rowid, file_path) 
                    VALUES ('delete', old.id, old.file_path);
                    INSERT INTO files_fts(rowid, file_path) VALUES (new.id, new.file_path);
                END
            ''')
            
            conn.commit()
    
    def add_file(self, file_path: str, file_type: str, extension: str, 
                 metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add a file to the index."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                metadata_json = json.dumps(metadata) if metadata else None
                conn.execute('''
                    INSERT OR REPLACE INTO files (file_path, file_type, extension, metadata, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (file_path, file_type, extension, metadata_json))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding file {file_path}: {e}")
            return False
    
    def remove_file(self, file_path: str) -> bool:
        """Remove a file from the index."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('DELETE FROM files WHERE file_path = ?', (file_path,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error removing file {file_path}: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get information about a file."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT file_type, extension, metadata 
                    FROM files WHERE file_path = ?
                ''', (file_path,))
                row = cursor.fetchone()
                
                if row is None:
                    return None
                
                file_type, extension, metadata_json = row
                metadata = json.loads(metadata_json) if metadata_json else {}
                
                return {
                    'type': file_type,
                    'extension': extension,
                    'path': file_path,
                    **metadata
                }
        except Exception as e:
            print(f"Error getting file info for {file_path}: {e}")
            return None
    
    def find_files_by_pattern(self, pattern: str) -> List[str]:
        """Find files matching a pattern using FTS."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT files.file_path 
                    FROM files_fts
                    JOIN files ON files_fts.rowid = files.id
                    WHERE files_fts MATCH ?
                ''', (pattern,))
                
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error finding files by pattern {pattern}: {e}")
            return []
    
    def find_files_by_extension(self, extension: str) -> List[str]:
        """Find files with a specific extension."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT file_path FROM files WHERE extension = ?',
                    (extension,)
                )
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error finding files by extension {extension}: {e}")
            return []
    
    def get_directory_structure(self, directory_path: str = "") -> Dict[str, Any]:
        """Get the directory structure."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if directory_path:
                    cursor = conn.execute('''
                        SELECT file_path, file_type, extension, metadata
                        FROM files 
                        WHERE file_path LIKE ?
                        ORDER BY file_path
                    ''', (f"{directory_path}%",))
                else:
                    cursor = conn.execute('''
                        SELECT file_path, file_type, extension, metadata
                        FROM files 
                        ORDER BY file_path
                    ''')
                
                structure = {}
                for row in cursor.fetchall():
                    file_path, file_type, extension, metadata_json = row
                    metadata = json.loads(metadata_json) if metadata_json else {}
                    
                    # Build nested structure
                    current = structure
                    parts = file_path.split('/')
                    
                    for i, part in enumerate(parts):
                        if i == len(parts) - 1:  # Last part (file or directory)
                            if file_type == 'file':
                                current[part] = {
                                    'type': file_type,
                                    'path': file_path,
                                    'ext': extension,
                                    **metadata
                                }
                            else:
                                if part not in current:
                                    current[part] = {'type': 'directory', 'children': {}}
                                current = current[part]['children']
                        else:  # Directory part
                            if part not in current:
                                current[part] = {'type': 'directory', 'children': {}}
                            current = current[part]['children']
                
                return structure
        except Exception as e:
            print(f"Error getting directory structure: {e}")
            return {}
    
    def get_all_files(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Get all files in the index."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT file_path, file_type, extension, metadata
                    FROM files
                    ORDER BY file_path
                ''')
                
                files = []
                for row in cursor.fetchall():
                    file_path, file_type, extension, metadata_json = row
                    metadata = json.loads(metadata_json) if metadata_json else {}
                    
                    file_info = {
                        'type': file_type,
                        'extension': extension,
                        'path': file_path,
                        **metadata
                    }
                    files.append((file_path, file_info))
                
                return files
        except Exception as e:
            print(f"Error getting all files: {e}")
            return []
    
    def clear(self) -> bool:
        """Clear all files from the index."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM files')
                conn.execute('DELETE FROM files_fts')
                conn.commit()
                # Ensure tables are properly initialized after clearing
                self._init_db()
                return True
        except Exception as e:
            print(f"Error clearing file index: {e}")
            # Try to reinitialize the database in case of schema issues
            try:
                self._init_db()
                return True
            except Exception as init_e:
                print(f"Error reinitializing file index after clear: {init_e}")
                return False
    
    def size(self) -> int:
        """Get the number of files in the index."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM files')
                return cursor.fetchone()[0]
        except Exception as e:
            print(f"Error getting file index size: {e}")
            return 0
    
    def close(self) -> None:
        """Close the storage backend."""
        # SQLite connections are managed per-operation, so no persistent connection to close
        pass
