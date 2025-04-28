# 使用輕量 Python 映像
FROM python:3.11-slim

# 安裝 git (用於代碼分析)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# 設置工作目錄
WORKDIR /app

# 複製依賴清單和安裝依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製程式碼
COPY . .

# 設置 Python 路徑
ENV PYTHONPATH="${PYTHONPATH}:/app:/app/src"

# 不需要預設的項目目錄掛載點，用戶將顯式設置項目路徑

# 運行 MCP 工具
ENTRYPOINT ["python", "-m", "code_index_mcp.server"]
