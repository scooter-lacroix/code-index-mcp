import uuid
import datetime
import hashlib
import difflib
import os
from typing import Optional, List, Dict

from src.code_index_mcp.incremental_indexer import IncrementalIndexer
from src.code_index_mcp.storage.sqlite_storage import SQLiteStorage

class FileChangeTracker:
    def __init__(self, sqlite_storage: SQLiteStorage, incremental_indexer: IncrementalIndexer):
        self.sqlite_storage = sqlite_storage
        self.incremental_indexer = incremental_indexer

    def _capture_pre_edit_state(self, file_path: str) -> Optional[str]:
        """
        Reads the content of file_path, stores its current state as a version, and returns the content.
        """
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            version_id = self._generate_version_id()
            self._store_file_version(file_path, content, version_id)
            
            # Update the incremental indexer's metadata with the current version ID
            # We need the full path for update_file_metadata
            full_path = os.path.abspath(file_path)
            file_metadata = self.incremental_indexer.file_metadata.get(file_path, {})
            file_metadata['current_version_id'] = version_id
            self.incremental_indexer.file_metadata[file_path] = file_metadata
            self.incremental_indexer.save_metadata() # Persist the metadata change
            
            return content
        return None

    def _record_post_edit_state(self, file_path: str, old_content: Optional[str], new_content: str):
        """
        Calculates the new content's hash, stores it as a new version, generates a diff if content changed,
        and updates the file index.
        """
        current_version_id = self._generate_version_id()
        self._store_file_version(file_path, new_content, current_version_id)

        operation_type = "edit"
        previous_version_id = None

        # Get previous version ID from incremental indexer's metadata
        file_metadata = self.incremental_indexer.file_metadata.get(file_path, {})
        previous_version_id = file_metadata.get('current_version_id')

        if old_content is None:
            operation_type = "create"
        elif not os.path.exists(file_path): # File was deleted
            operation_type = "delete"
            new_content = "" # Ensure new_content is empty for diffing a deletion

        if old_content is not None and old_content != new_content:
            diff_id = self._generate_version_id()
            self._store_file_diff(diff_id, file_path, previous_version_id, current_version_id, old_content, new_content, operation_type)
        elif old_content is None and new_content: # File created
            diff_id = self._generate_version_id()
            self._store_file_diff(diff_id, file_path, None, current_version_id, "", new_content, "create")
        elif old_content and not new_content and operation_type == "delete": # File deleted
            diff_id = self._generate_version_id()
            self._store_file_diff(diff_id, file_path, previous_version_id, current_version_id, old_content, "", "delete")

        # Update the incremental indexer's metadata for file_path to include the current_version_id
        file_metadata = self.incremental_indexer.file_metadata.get(file_path, {})
        file_metadata['current_version_id'] = current_version_id
        self.incremental_indexer.file_metadata[file_path] = file_metadata
        self.incremental_indexer.save_metadata() # Persist the metadata change

        # Also update the file's general metadata (mtime, size, hash) in the incremental indexer
        full_path = os.path.abspath(file_path)
        self.incremental_indexer.update_file_metadata(file_path, full_path)

    def _generate_version_id(self) -> str:
        """Generates a unique ID for versions."""
        return uuid.uuid4().hex

    def _calculate_hash(self, content: str) -> str:
        """Calculates SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _store_file_version(self, file_path: str, content: str, version_id: str) -> None:
        """Stores a file version in file_versions table."""
        file_hash = self._calculate_hash(content)
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        size = len(content.encode('utf-8'))
        self.sqlite_storage.insert_file_version(version_id, file_path, content, file_hash, timestamp, size)

    def _store_file_diff(self, diff_id: str, file_path: str, previous_version_id: Optional[str], current_version_id: str, old_content: str, new_content: str, operation_type: str, operation_details: Optional[str] = None) -> None:
        """Stores a diff in file_diffs table."""
        diff_content = "\n".join(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=file_path + "_old",
            tofile=file_path + "_new",
            lineterm='' # Avoid extra newlines
        ))
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.sqlite_storage.insert_file_diff(diff_id, file_path, previous_version_id, current_version_id, diff_content, "unified_diff", operation_type, operation_details, timestamp)

    def get_file_version_by_id(self, version_id: str) -> Optional[str]:
        """Retrieves a file version by its ID."""
        version_data = self.sqlite_storage.get_file_version(version_id)
        if version_data:
            return version_data.get('content')
        return None

    def get_file_history(self, file_path: str) -> List[Dict]:
        """Retrieves the history of changes for a given file path."""
        versions = self.sqlite_storage.get_file_versions_for_path(file_path)
        diffs = self.sqlite_storage.get_file_diffs_for_path(file_path)

        history = []
        for v in versions:
            v['type'] = 'version'
            history.append(v)
        for d in diffs:
            d['type'] = 'diff'
            history.append(d)

        # Sort by timestamp
        history.sort(key=lambda x: x['timestamp'])
        return history

    def reconstruct_file_version(self, file_path: str, version_id: str) -> Optional[str]:
        """
        Reconstructs a specific file version by applying diffs if necessary.
        """
        # 1. Try to retrieve the version directly
        target_version_data = self.sqlite_storage.get_file_version(version_id)
        if target_version_data:
            return target_version_data.get('content')

        # 2. If not a full version, we need to reconstruct from history
        # Get all versions and diffs for the file path, sorted by timestamp
        history = self.get_file_history(file_path)

        # Find the latest full version before or at the target version_id's timestamp
        base_content = None
        base_timestamp = None
        base_version_id = None

        # Find the target version's timestamp first
        target_timestamp = None
        for item in history:
            if item.get('version_id') == version_id or item.get('current_version_id') == version_id:
                target_timestamp = item['timestamp']
                break
        
        if not target_timestamp:
            # If the target version_id is not found in history at all, return None
            return None

        # Find the latest full version before or at the target timestamp
        for item in history:
            if item['type'] == 'version' and item['timestamp'] <= target_timestamp:
                if base_timestamp is None or item['timestamp'] > base_timestamp:
                    base_content = item['content']
                    base_timestamp = item['timestamp']
                    base_version_id = item['version_id']
        
        if base_content is None:
            # No full version found before the target, cannot reconstruct
            return None

        current_content = base_content
        # Apply subsequent diffs up to the target version
        for item in history:
            if item['type'] == 'diff' and item['timestamp'] > base_timestamp and item['timestamp'] <= target_timestamp:
                diff_content = item['diff_content']
                
                # Apply the diff
                # difflib.apply_patch expects a list of lines
                old_lines = current_content.splitlines(keepends=True)
                
                # difflib.parse_unidiff returns an iterator of (filename1, filename2, date1, date2, hunks)
                # Each hunk is (old_start, old_len, new_start, new_len, lines)
                # lines are the diff lines with '+', '-', ' ' prefixes
                
                # A simpler approach for applying unified diffs is to use a library or manual parsing.
                # For this implementation, we'll assume a direct application of unified diff format.
                # This is a simplified application and might need more robust error handling for malformed diffs.
                
                # Reconstruct by applying diff lines
                new_lines = []
                diff_lines = diff_content.splitlines(keepends=True)
                
                # This is a very basic diff application. A real-world scenario might need
                # a more sophisticated diff parsing and application library.
                # For unified diff, lines starting with '-' are removed, '+' are added.
                # Lines starting with ' ' are context.
                
                old_idx = 0
                for line in diff_lines:
                    if line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
                        continue
                    elif line.startswith('-'):
                        # Skip line from old_lines, effectively removing it
                        old_idx += 1
                    elif line.startswith('+'):
                        new_lines.append(line[1:]) # Add new line
                    else: # Context line or unchanged line
                        new_lines.append(old_lines[old_idx])
                        old_idx += 1
                
                current_content = "".join(new_lines)
            
            # If we reached the target version_id, return the current content
            if item.get('version_id') == version_id or item.get('current_version_id') == version_id:
                return current_content

        return None # Should not reach here if target_timestamp was found and base_content was set