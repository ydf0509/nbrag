#coding=utf-8
"""直接调用 nbrag.mcp_tools.nbrag_search 复现 sanguo collection 的 HNSW 读取异常。"""

from __future__ import annotations

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import my_load_config  # noqa: F401

from nbrag.mcp_tools import nbrag_search


def main() -> int:
    kwargs = {
        "query": "赤壁之战中曹操为什么失败，周瑜和诸葛亮用了什么计策",
        "collection_name": "sanguo",
        "top_k": 5,
        "use_rerank": True,
        "use_bm25": True,
        "filter_file_path": "",
        "include_content": True,
        "preview_chars": 500,
    }
    print("calling nbrag.mcp_tools.nbrag_search")
    print(f"collection_name={kwargs['collection_name']}")
    print(f"query={kwargs['query']}")
    print(f"kwargs={kwargs}")
    print("-" * 80)
    try:
        result = nbrag_search(**kwargs)
    except Exception:
        traceback.print_exc()
        return 1
    print(result)
    if "Error creating hnsw segment reader: Nothing found on disk" in result:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
