"""用原始 col.get() 直接测试，不经过 _batch_get。"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import my_load_config
from nbrag.config import load_config
from nbrag.storage import _get_existing_collection

load_config()

col = _get_existing_collection("langchain_ai_codes_and_docs")
if col is None:
    print("collection 不存在")
    sys.exit(1)

count = col.count()
print(f"collection 文档数: {count}")

# 直接调用原始 col.get()
print("\n直接调用 col.get(include=['metadatas'])...")
try:
    result = col.get(include=["metadatas"])
    print(f"成功: {len(result['metadatas'])} 条")
except Exception as e:
    print(f"失败: {type(e).__name__}: {e}")

print("\n直接调用 col.get(include=['documents', 'metadatas'])...")
try:
    result = col.get(include=["documents", "metadatas"])
    print(f"成功: {len(result['ids'])} 条")
except Exception as e:
    print(f"失败: {type(e).__name__}: {e}")
