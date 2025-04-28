"""
Project Settings Management

This module provides functionality for managing project settings and persistent data
for the Code Index MCP server.
"""
import os
import json
import shutil
import pickle
import tempfile
import hashlib
from datetime import datetime

class ProjectSettings:
    """管理專案設定和索引資料的類"""

    SETTINGS_DIR = "code_indexer"
    CONFIG_FILE = "config.json"
    INDEX_FILE = "file_index.pickle"
    CACHE_FILE = "content_cache.pickle"

    def __init__(self, base_path, skip_load=False):
        """初始化專案設定

        Args:
            base_path (str): 專案的基本路徑
            skip_load (bool): 是否跳過加載文件
        """
        self.base_path = base_path
        self.skip_load = skip_load

        # 確保臨時目錄的基本路徑存在
        try:
            # 獲取系統臨時目錄
            system_temp = tempfile.gettempdir()
            print(f"System temporary directory: {system_temp}")

            # 檢查系統臨時目錄是否存在且可寫
            if not os.path.exists(system_temp):
                print(f"Warning: System temporary directory does not exist: {system_temp}")
                # 嘗試使用當前目錄作為備用
                system_temp = os.getcwd()
                print(f"Using current directory as fallback: {system_temp}")

            if not os.access(system_temp, os.W_OK):
                print(f"Warning: No write access to system temporary directory: {system_temp}")
                # 嘗試使用當前目錄作為備用
                system_temp = os.getcwd()
                print(f"Using current directory as fallback: {system_temp}")

            # 創建 code_indexer 目錄
            temp_base_dir = os.path.join(system_temp, self.SETTINGS_DIR)
            print(f"Code indexer directory path: {temp_base_dir}")

            if not os.path.exists(temp_base_dir):
                print(f"Creating code indexer directory: {temp_base_dir}")
                os.makedirs(temp_base_dir, exist_ok=True)

                # 創建一個 README.md 文件，說明該目錄的用途
                readme_path = os.path.join(temp_base_dir, "README.md")
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write("# Code Indexer Cache Directory\n\nThis directory contains cached data for the Code Index MCP tool.\nEach subdirectory corresponds to a different project.\n")
                print(f"README file created: {readme_path}")
            else:
                print(f"Code indexer directory already exists: {temp_base_dir}")
        except Exception as e:
            print(f"Error setting up temporary directory: {e}")
            # 如果無法創建臨時目錄，使用當前目錄下的 .code_indexer 作為備用
            temp_base_dir = os.path.join(os.getcwd(), ".code_indexer")
            print(f"Using fallback directory: {temp_base_dir}")
            if not os.path.exists(temp_base_dir):
                os.makedirs(temp_base_dir, exist_ok=True)

        # 使用系統臨時目錄存儲索引數據
        try:
            if base_path:
                # 使用專案路徑的哈希值作為唯一標識符
                path_hash = hashlib.md5(base_path.encode()).hexdigest()
                self.settings_path = os.path.join(temp_base_dir, path_hash)
                print(f"Using project-specific directory: {self.settings_path}")
            else:
                # 如果沒有提供基本路徑，使用一個默認目錄
                self.settings_path = os.path.join(temp_base_dir, "default")
                print(f"Using default directory: {self.settings_path}")

            self.ensure_settings_dir()
        except Exception as e:
            print(f"Error setting up project settings: {e}")
            # 如果出現錯誤，使用當前目錄下的 .code_indexer 作為備用
            fallback_dir = os.path.join(os.getcwd(), ".code_indexer",
                                      "default" if not base_path else hashlib.md5(base_path.encode()).hexdigest())
            print(f"Using fallback directory: {fallback_dir}")
            self.settings_path = fallback_dir
            if not os.path.exists(fallback_dir):
                os.makedirs(fallback_dir, exist_ok=True)

    def ensure_settings_dir(self):
        """確保設定目錄存在"""
        print(f"Checking project settings directory: {self.settings_path}")

        try:
            if not os.path.exists(self.settings_path):
                print(f"Creating project settings directory: {self.settings_path}")
                # 創建目錄結構
                os.makedirs(self.settings_path, exist_ok=True)

                # 創建一個 README.md 文件，說明該目錄的用途
                readme_path = os.path.join(self.settings_path, "README.md")
                readme_content = (
                    f"# Code Indexer Cache Directory for {self.base_path}\n\n"
                    f"This directory contains cached data for the Code Index MCP tool:\n\n"
                    f"- `config.json`: Project configuration\n"
                    f"- `file_index.pickle`: Index of project files\n"
                    f"- `content_cache.pickle`: Cached file contents\n\n"
                    f"These files are automatically generated and stored in the system temporary directory.\n"
                )

                try:
                    with open(readme_path, 'w', encoding='utf-8') as f:
                        f.write(readme_content)
                    print(f"README file created: {readme_path}")
                except Exception as e:
                    print(f"Warning: Could not create README file: {e}")
            else:
                print(f"Project settings directory already exists: {self.settings_path}")

            # 確認目錄是否可寫
            if not os.access(self.settings_path, os.W_OK):
                print(f"Warning: No write access to project settings directory: {self.settings_path}")
                # 如果目錄不可寫，嘗試使用當前目錄下的 .code_indexer 作為備用
                fallback_dir = os.path.join(os.getcwd(), ".code_indexer",
                                          os.path.basename(self.settings_path))
                print(f"Using fallback directory: {fallback_dir}")
                self.settings_path = fallback_dir
                if not os.path.exists(fallback_dir):
                    os.makedirs(fallback_dir, exist_ok=True)
        except Exception as e:
            print(f"Error ensuring settings directory: {e}")
            # 如果無法創建設定目錄，使用當前目錄下的 .code_indexer 作為備用
            fallback_dir = os.path.join(os.getcwd(), ".code_indexer",
                                      "default" if not self.base_path else hashlib.md5(self.base_path.encode()).hexdigest())
            print(f"Using fallback directory: {fallback_dir}")
            self.settings_path = fallback_dir
            if not os.path.exists(fallback_dir):
                os.makedirs(fallback_dir, exist_ok=True)

    def get_config_path(self):
        """獲取配置文件的路徑"""
        try:
            path = os.path.join(self.settings_path, self.CONFIG_FILE)
            # 確保目錄存在
            os.makedirs(os.path.dirname(path), exist_ok=True)
            return path
        except Exception as e:
            print(f"Error getting config path: {e}")
            # 如果出現錯誤，使用當前目錄下的文件作為備用
            return os.path.join(os.getcwd(), self.CONFIG_FILE)

    def get_index_path(self):
        """獲取索引文件的路徑"""
        try:
            path = os.path.join(self.settings_path, self.INDEX_FILE)
            # 確保目錄存在
            os.makedirs(os.path.dirname(path), exist_ok=True)
            return path
        except Exception as e:
            print(f"Error getting index path: {e}")
            # 如果出現錯誤，使用當前目錄下的文件作為備用
            return os.path.join(os.getcwd(), self.INDEX_FILE)

    def get_cache_path(self):
        """獲取緩存文件的路徑"""
        try:
            path = os.path.join(self.settings_path, self.CACHE_FILE)
            # 確保目錄存在
            os.makedirs(os.path.dirname(path), exist_ok=True)
            return path
        except Exception as e:
            print(f"Error getting cache path: {e}")
            # 如果出現錯誤，使用當前目錄下的文件作為備用
            return os.path.join(os.getcwd(), self.CACHE_FILE)

    def _get_timestamp(self):
        """獲取當前時間戳"""
        return datetime.now().isoformat()

    def save_config(self, config):
        """保存配置數據

        Args:
            config (dict): 配置數據
        """
        try:
            config_path = self.get_config_path()
            # 添加時間戳
            config['last_updated'] = self._get_timestamp()

            # 確保目錄存在
            os.makedirs(os.path.dirname(config_path), exist_ok=True)

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            print(f"Config saved to: {config_path}")
            return config
        except Exception as e:
            print(f"Error saving config: {e}")
            return config

    def load_config(self):
        """加載配置數據

        Returns:
            dict: 配置數據，如果文件不存在則返回空字典
        """
        # 如果設置了跳過加載，直接返回空字典
        if self.skip_load:
            return {}

        try:
            config_path = self.get_config_path()
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    print(f"Config loaded from: {config_path}")
                    return config
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    print(f"Error parsing config file: {e}")
                    # 如果文件損壞，返回空字典
                    return {}
            else:
                print(f"Config file does not exist: {config_path}")
            return {}
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}

    def save_index(self, file_index):
        """保存文件索引

        Args:
            file_index (dict): 文件索引數據
        """
        try:
            index_path = self.get_index_path()
            print(f"Saving index to: {index_path}")

            # 確保目錄存在
            dir_path = os.path.dirname(index_path)
            if not os.path.exists(dir_path):
                print(f"Creating directory: {dir_path}")
                os.makedirs(dir_path, exist_ok=True)

            # 檢查目錄是否可寫
            if not os.access(dir_path, os.W_OK):
                print(f"Warning: Directory is not writable: {dir_path}")
                # 使用當前目錄作為備用
                index_path = os.path.join(os.getcwd(), self.INDEX_FILE)
                print(f"Using fallback path: {index_path}")

            with open(index_path, 'wb') as f:
                pickle.dump(file_index, f)

            print(f"Index saved successfully to: {index_path}")
        except Exception as e:
            print(f"Error saving index: {e}")
            # 嘗試保存到當前目錄
            try:
                fallback_path = os.path.join(os.getcwd(), self.INDEX_FILE)
                print(f"Trying fallback path: {fallback_path}")
                with open(fallback_path, 'wb') as f:
                    pickle.dump(file_index, f)
                print(f"Index saved to fallback path: {fallback_path}")
            except Exception as e2:
                print(f"Error saving index to fallback path: {e2}")

    def load_index(self):
        """加載文件索引

        Returns:
            dict: 文件索引數據，如果文件不存在則返回空字典
        """
        # 如果設置了跳過加載，直接返回空字典
        if self.skip_load:
            return {}

        try:
            index_path = self.get_index_path()

            if os.path.exists(index_path):
                try:
                    with open(index_path, 'rb') as f:
                        index = pickle.load(f)
                    print(f"Index loaded successfully from: {index_path}")
                    return index
                except (pickle.PickleError, EOFError) as e:
                    print(f"Error parsing index file: {e}")
                    # 如果文件損壞，返回空字典
                    return {}
                except Exception as e:
                    print(f"Unexpected error loading index: {e}")
                    return {}
            else:
                # 嘗試從當前目錄加載
                fallback_path = os.path.join(os.getcwd(), self.INDEX_FILE)
                if os.path.exists(fallback_path):
                    print(f"Trying fallback path: {fallback_path}")
                    try:
                        with open(fallback_path, 'rb') as f:
                            index = pickle.load(f)
                        print(f"Index loaded from fallback path: {fallback_path}")
                        return index
                    except Exception as e:
                        print(f"Error loading index from fallback path: {e}")

            return {}
        except Exception as e:
            print(f"Error in load_index: {e}")
            return {}

    def save_cache(self, content_cache):
        """保存內容緩存

        Args:
            content_cache (dict): 內容緩存數據
        """
        try:
            cache_path = self.get_cache_path()
            print(f"Saving cache to: {cache_path}")

            # 確保目錄存在
            dir_path = os.path.dirname(cache_path)
            if not os.path.exists(dir_path):
                print(f"Creating directory: {dir_path}")
                os.makedirs(dir_path, exist_ok=True)

            # 檢查目錄是否可寫
            if not os.access(dir_path, os.W_OK):
                print(f"Warning: Directory is not writable: {dir_path}")
                # 使用當前目錄作為備用
                cache_path = os.path.join(os.getcwd(), self.CACHE_FILE)
                print(f"Using fallback path: {cache_path}")

            with open(cache_path, 'wb') as f:
                pickle.dump(content_cache, f)

            print(f"Cache saved successfully to: {cache_path}")
        except Exception as e:
            print(f"Error saving cache: {e}")
            # 嘗試保存到當前目錄
            try:
                fallback_path = os.path.join(os.getcwd(), self.CACHE_FILE)
                print(f"Trying fallback path: {fallback_path}")
                with open(fallback_path, 'wb') as f:
                    pickle.dump(content_cache, f)
                print(f"Cache saved to fallback path: {fallback_path}")
            except Exception as e2:
                print(f"Error saving cache to fallback path: {e2}")

    def load_cache(self):
        """加載內容緩存

        Returns:
            dict: 內容緩存數據，如果文件不存在則返回空字典
        """
        # 如果設置了跳過加載，直接返回空字典
        if self.skip_load:
            return {}

        try:
            cache_path = self.get_cache_path()

            if os.path.exists(cache_path):
                try:
                    with open(cache_path, 'rb') as f:
                        cache = pickle.load(f)
                    print(f"Cache loaded successfully from: {cache_path}")
                    return cache
                except (pickle.PickleError, EOFError) as e:
                    print(f"Error parsing cache file: {e}")
                    # 如果文件損壞，返回空字典
                    return {}
                except Exception as e:
                    print(f"Unexpected error loading cache: {e}")
                    return {}
            else:
                # 嘗試從當前目錄加載
                fallback_path = os.path.join(os.getcwd(), self.CACHE_FILE)
                if os.path.exists(fallback_path):
                    print(f"Trying fallback path: {fallback_path}")
                    try:
                        with open(fallback_path, 'rb') as f:
                            cache = pickle.load(f)
                        print(f"Cache loaded from fallback path: {fallback_path}")
                        return cache
                    except Exception as e:
                        print(f"Error loading cache from fallback path: {e}")

            return {}
        except Exception as e:
            print(f"Error in load_cache: {e}")
            return {}

    def clear(self):
        """清除所有設定和緩存文件"""
        try:
            print(f"Clearing settings directory: {self.settings_path}")

            if os.path.exists(self.settings_path):
                # 檢查目錄是否可寫
                if not os.access(self.settings_path, os.W_OK):
                    print(f"Warning: Directory is not writable: {self.settings_path}")
                    return

                # 保留 .gitignore 文件
                gitignore_path = os.path.join(self.settings_path, ".gitignore")
                has_gitignore = os.path.exists(gitignore_path)
                gitignore_content = None

                if has_gitignore:
                    try:
                        with open(gitignore_path, 'r', encoding='utf-8') as f:
                            gitignore_content = f.read()
                        print(f"Preserved .gitignore content")
                    except Exception as e:
                        print(f"Error reading .gitignore: {e}")

                # 刪除資料夾中的所有文件
                try:
                    for filename in os.listdir(self.settings_path):
                        file_path = os.path.join(self.settings_path, filename)
                        try:
                            if os.path.isfile(file_path):
                                os.unlink(file_path)
                                print(f"Deleted file: {file_path}")
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                                print(f"Deleted directory: {file_path}")
                        except Exception as e:
                            print(f"Error deleting {file_path}: {e}")
                except Exception as e:
                    print(f"Error listing directory: {e}")

                # 恢復 .gitignore 文件
                if has_gitignore and gitignore_content:
                    try:
                        with open(gitignore_path, 'w', encoding='utf-8') as f:
                            f.write(gitignore_content)
                        print(f"Restored .gitignore file")
                    except Exception as e:
                        print(f"Error restoring .gitignore: {e}")

                print(f"Settings directory cleared successfully")
            else:
                print(f"Settings directory does not exist: {self.settings_path}")
        except Exception as e:
            print(f"Error clearing settings: {e}")

    def get_stats(self):
        """獲取設定目錄的統計信息

        Returns:
            dict: 包含文件大小和更新時間的字典
        """
        try:
            print(f"Getting stats for settings directory: {self.settings_path}")

            stats = {
                'settings_path': self.settings_path,
                'exists': os.path.exists(self.settings_path),
                'is_directory': os.path.isdir(self.settings_path) if os.path.exists(self.settings_path) else False,
                'writable': os.access(self.settings_path, os.W_OK) if os.path.exists(self.settings_path) else False,
                'files': {},
                'temp_dir': tempfile.gettempdir(),
                'current_dir': os.getcwd()
            }

            if stats['exists'] and stats['is_directory']:
                try:
                    # 獲取目錄中的所有文件
                    all_files = os.listdir(self.settings_path)
                    stats['all_files'] = all_files

                    # 獲取特定文件的詳細信息
                    for filename in [self.CONFIG_FILE, self.INDEX_FILE, self.CACHE_FILE]:
                        file_path = os.path.join(self.settings_path, filename)
                        if os.path.exists(file_path):
                            try:
                                file_stats = os.stat(file_path)
                                stats['files'][filename] = {
                                    'path': file_path,
                                    'size_bytes': file_stats.st_size,
                                    'last_modified': datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                                    'readable': os.access(file_path, os.R_OK),
                                    'writable': os.access(file_path, os.W_OK)
                                }
                            except Exception as e:
                                stats['files'][filename] = {
                                    'path': file_path,
                                    'error': str(e)
                                }
                except Exception as e:
                    stats['list_error'] = str(e)

            # 檢查備用路徑
            fallback_dir = os.path.join(os.getcwd(), ".code_indexer")
            stats['fallback_path'] = fallback_dir
            stats['fallback_exists'] = os.path.exists(fallback_dir)
            stats['fallback_is_directory'] = os.path.isdir(fallback_dir) if os.path.exists(fallback_dir) else False

            return stats
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {
                'error': str(e),
                'settings_path': self.settings_path,
                'temp_dir': tempfile.gettempdir(),
                'current_dir': os.getcwd()
            }
