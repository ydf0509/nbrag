# """
# 启动 nbrag STDIO MCP Server（用于 Claude Code 等 stdio MCP 客户端）。

# 完全自包含脚本，不依赖环境变量传递。
# """

# import os
# import sys

# # nb_log banner 会直接 print 到 stdout，污染 MCP stdio 协议。
# # 在导入任何可能触发 nb_log 的模块前，将 stdout 重定向到 stderr
# _clean_stdout = sys.stdout
# sys.stdout = sys.stderr

# # 确保 PYTHONPATH 包含项目根目录
# _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# sys.path.insert(0, _project_root)
# os.environ.setdefault("PYTHONPATH", _project_root)

# # 确保 nltk 能找到数据目录
# _nltk_data = os.path.expanduser("~/nltk_data")
# if os.path.isdir(_nltk_data):
#     os.environ.setdefault("NLTK_DATA", _nltk_data)

# import my_load_config
# from nbrag.config import load_config
# from nbrag.server import mcp

# # nbrag 已完成导入，恢复 stdout 用于 MCP JSON-RPC 通信
# sys.stdout = _clean_stdout

# load_config()

# print("[nbrag] STDIO MCP server started", file=sys.stderr)

# mcp.run(transport="stdio")
