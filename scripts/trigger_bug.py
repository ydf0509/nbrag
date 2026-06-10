"""直接调用 nbrag 核心函数触发 too many SQL variables bug。"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import my_load_config
from nbrag.config import load_config
from nbrag.core import find_symbol_definition, _get_doc_id_map, list_documents, get_stats

load_config()

# 先测试 _get_doc_id_map（全量查询，最容易触发）
print("=" * 60)
print("测试 1: _get_doc_id_map (全量 metadatas 查询)")
print("=" * 60)
try:
    result = _get_doc_id_map("langchain_ai_codes_and_docs")
    print(f"成功: {len(result)} 个文档")
except Exception as e:
    print(f"失败: {type(e).__name__}: {e}")

# 测试 list_documents
print("\n" + "=" * 60)
print("测试 2: list_documents (全量 metadatas 查询)")
print("=" * 60)
try:
    result = list_documents("langchain_ai_codes_and_docs")
    print(f"成功: {len(result)} 个文档")
except Exception as e:
    print(f"失败: {type(e).__name__}: {e}")

# 测试 get_stats
print("\n" + "=" * 60)
print("测试 3: get_stats (全量 metadatas 查询)")
print("=" * 60)
try:
    result = get_stats()
    print(f"成功: {len(result.get('collections', {}))} 个知识库")
except Exception as e:
    print(f"失败: {type(e).__name__}: {e}")

# 测试 find_symbol_definition
print("\n" + "=" * 60)
print("测试 4: find_symbol_definition (调用 _get_doc_id_map)")
print("=" * 60)
try:
    result = find_symbol_definition("create_deep_agent", "langchain_ai_codes_and_docs", max_results=1)
    print(f"成功: {len(result)} 个结果")
except Exception as e:
    print(f"失败: {type(e).__name__}: {e}")

print("\n全部测试完成")
