"""
启动 nbrag HTTP MCP Server。

    set NBRAG_API_KEY=sk-xxx
    python scripts/start_http_rag_mcp.py

    或者 python -m nbrag --transport streamable-http --port 9101
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import my_load_config

from nbrag.config import load_config
from nbrag.server import mcp

load_config()

PORT = 9101
mcp.settings.port = PORT

print(f"[nbrag] HTTP MCP server on http://localhost:{PORT}/mcp")

mcp.run(transport="streamable-http")

"""
 D:/ProgramData/Miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/start_http_rag_mcp.py

"""