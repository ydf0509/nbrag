"""通过 nbrag 查询 create_deep_agent 用法。"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import my_load_config
from nbrag.config import load_config
from nbrag import search, find_symbol_definition, get_raw_file

load_config()

COL = "langchain_ai_codes_and_docs"

# 步骤 1: 语义搜索
print("=" * 60)
print("步骤 1: 语义搜索 'create_deep_agent 用法'")
print("=" * 60)
results = search("create_deep_agent 用法 参数 示例", collection_name=COL, top_k=5)
for i, r in enumerate(results.get("results", []), 1):
    meta = r.get("metadata", {})
    print(f"\n[{i}] {meta.get('filename', '?')} chunk:{meta.get('chunk_index', '?')}/{meta.get('total_chunks', '?')}")
    print(f"    scope: {meta.get('scope', '?')}  lines: {meta.get('line_start', '?')}-{meta.get('line_end', '?')}")
    print(f"    doc_id: {meta.get('doc_id', '?')}")
    doc = r.get("document", "")
    print(f"    内容预览: {doc[:200]}...")

# 步骤 2: 查找符号定义
print("\n" + "=" * 60)
print("步骤 2: 查找 create_deep_agent 完整定义")
print("=" * 60)
defs = find_symbol_definition("create_deep_agent", collection_name=COL, max_results=1)
for d in defs:
    print(f"\n文件: {d.get('filename')}")
    print(f"符号: {d.get('qualified_name')} ({d.get('symbol_type')})")
    print(f"行号: {d.get('line_start')}-{d.get('line_end')}")
    print(f"定义:\n{d.get('definition', '')[:500]}...")

# 步骤 3: 获取完整源码
if defs:
    d = defs[0]
    print("\n" + "=" * 60)
    print(f"步骤 3: 获取 {d.get('filename')} 完整源码 (行 {d.get('line_start')}-{d.get('line_end')})")
    print("=" * 60)
    raw = get_raw_file(d["doc_id"], collection_name=COL, line_start=d["line_start"], line_end=d["line_end"])
    if raw.get("found"):
        print(raw.get("content", "")[:800])
    else:
        print(f"  未找到: {raw.get('error')}")
