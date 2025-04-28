# Code Index MCP

Code Index MCP 是一個基於 Model Context Protocol 的服務器，允許大型語言模型 (LLMs) 索引、搜索和分析專案目錄中的程式碼。

## 功能特點

- 索引並導航專案文件結構
- 搜索特定模式的程式碼
- 獲取文件的詳細摘要
- 分析程式碼結構和複雜性
- 支持多種程式語言
- 專案設定持久化存儲

## 安裝

本專案使用 uv 進行環境管理和依賴安裝。

1. 確保您已安裝 Python 3.10 或更高版本
2. 安裝 uv (推薦):

   ```bash
   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
3. 獲取代碼:

   ```bash
   # clone 儲存庫
   git clone https://github.com/your-username/code-index-mcp.git
   ```

## 使用方法

### 直接運行服務器

```bash
# 使用 uv 直接運行 - 無需額外安裝依賴
uv run run.py
```

UV 將根據項目配置自動處理所有依賴安裝。

### 使用 Docker

您也可以將 Code Index MCP 作為容器化工具使用：

```bash
# 構建 Docker 映像
docker build -t code-index-mcp .

# 使用容器作為工具來分析您的代碼
docker run --rm -i code-index-mcp
```

這種容器化方法非常適合 Claude Desktop，因為 Claude Desktop 將 MCP 伺服器視為按需啟動的進程，而非持久運行的伺服器。Claude Desktop 會在需要時啟動容器，並通過標準輸入輸出（stdio）與之通訊，僅在會話期間保持容器運行。

使用容器化版本時，您需要使用 `set_project_path` 工具顯式設置項目路徑，就像在非容器化版本中一樣。

### 與 Claude Desktop 整合

您可以輕鬆地將 Code Index MCP 與 Claude Desktop 整合:

#### 選項 1: 使用 UV (直接安裝)

1. 確保已安裝 UV (參見上方安裝部分)
2. 找到或創建 Claude Desktop 配置文件:

   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS/Linux: `~/Library/Application Support/Claude/claude_desktop_config.json`
3. 添加以下配置 (請替換為您的實際路徑):

   **適用於 Windows**:

   ```json
   {
     "mcpServers": {
       "code-indexer": {
         "command": "uv",
         "args": [
            "--directory",
            "C:\\Users\\username\\path\\to\\code-index-mcp",
            "run",
            "run.py"
          ]
       }
     }
   }
   ```

   **適用於 macOS/Linux**:

   ```json
   {
     "mcpServers": {
       "code-indexer": {
         "command": "uv",
         "args": [
            "--directory",
            "/home/username/path/to/code-index-mcp",
            "run",
            "run.py"
          ]
       }
     }
   }
   ```

   **注意**: `--directory` 選項非常重要，它確保 uv 在正確的項目目錄中運行，並可以正確載入所有依賴項。

#### 選項 2: 使用 Docker (容器化)

1. 按照上方 Docker 部分的說明構建 Docker 映像
2. 找到或創建 Claude Desktop 配置文件 (位置同上)
3. 添加以下配置:

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

   **注意**: 此配置允許 Claude Desktop 按需啟動容器化的 MCP 工具。

4. 重啟 Claude Desktop，就可以使用 Code Indexer 來分析代碼專案

Claude Desktop 會在需要時將 MCP 伺服器作為按需進程啟動，通過標準輸入輸出（stdio）與之通訊，並僅在您的會話期間保持其運行。

### 基本使用流程

1. **設定專案路徑** (必要第一步):

   - 首次使用時，必須先設定要分析的專案路徑
   - 透過 Claude 指令: "我需要分析一個專案，幫我設定專案路徑"
   - 提供完整的專案目錄路徑
2. **代碼搜索**:

   - 搜索特定關鍵字或模式: "在專案中搜索 'function name'"
   - 支援按文件類型過濾: "搜索所有 .py 文件中的 'import'"
3. **文件分析**:

   - 分析特定文件: "分析 src/main.py 這個文件"
   - 獲取文件摘要: "給我 utils/helpers.js 的函數列表"
4. **專案導航**:

   - 查看專案結構: "顯示這個專案的結構"
   - 查找特定模式的文件: "找出所有的 test_*.py 文件"

## 技術細節

### 持久化存儲

所有索引和設定數據存儲在系統臨時目錄中，每個專案有專屬的子資料夾：

- Windows: `%TEMP%\code_indexer\[project_hash]\`
- Linux/macOS: `/tmp/code_indexer/[project_hash]/`

每個專案的數據包括：
- `config.json`: 專案配置資訊
- `file_index.pickle`: 檔案索引數據
- `content_cache.pickle`: 檔案內容緩存

這種方法確保：
1. 不同專案的數據分開存儲
2. 數據在不再需要時由操作系統自動清理
3. 在容器化環境中，數據存儲在容器的臨時目錄中

### 使用 UV 進行依賴管理

Code Index MCP 使用 UV 進行依賴管理，這提供了多項優勢：

- 根據專案需求自動解析依賴關係
- 更快的套件安裝和環境設置
- 通過鎖定文件確保依賴版本的一致性

### 支持的文件類型

目前支持以下文件類型的索引和分析:

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

## 安全考量

- 檔案路徑驗證防止目錄遍歷攻擊
- 不允許透過絕對路徑存取文件
- 專案路徑必須明確設定，無預設值
- 索引數據存儲在系統臨時目錄中，而非專案目錄
- 每個專案的數據存儲在基於專案路徑哈希值的獨立目錄中

## 貢獻

歡迎提交問題或拉取請求，以添加新功能或修復錯誤。
