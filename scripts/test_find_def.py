"""测试 find_symbol_definition 在当前代码下是否还会报错。"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import my_load_config
from nbrag.config import load_config
from nbrag import find_symbol_definition

load_config()

print("调用 find_symbol_definition('create_deep_agent', 'langchain_ai_codes_and_docs', max_results=1)...")
try:
    result = find_symbol_definition("create_deep_agent", "langchain_ai_codes_and_docs", max_results=1)
    print(f"成功: {len(result)} 个结果")
    if result:
        r = result[0]
        print(f"  filename: {r.get('filename')}")
        print(f"  symbol_type: {r.get('symbol_type')}")
        print(f"  qualified_name: {r.get('qualified_name')}")
        print(f"  line_start: {r.get('line_start')}")
        print(f"  definition (前100字): {r.get('definition', '')[:100]}")
except Exception as e:
    print(f"失败: {type(e).__name__}: {e}")
