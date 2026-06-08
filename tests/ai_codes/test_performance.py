"""性能基准测试 —— 对比 Symbol 索引优化前后的 find_symbol_definition 耗时。"""

import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from my_load_config import *

from nbrag.core import (
    grep_knowledge, find_symbol_definition, search, get_stats,
    build_symbol_index, _load_symbol_index, invalidate_symbol_cache,
    _find_definition_full_scan, _find_definition_via_index,
    _raw_files_dir,
)


def time_it(fn, *args, **kwargs):
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - t0
    return elapsed, result


def main():
    stats = get_stats()
    print("=" * 70)
    print("nbrag 性能基准测试 —— Symbol 索引 vs 全量 AST 扫描")
    print("=" * 70)

    for name, info in stats["collections"].items():
        print(f"  [{name}] {info.get('doc_count', '?')} docs, {info.get('chunk_count', '?')} chunks")

    collections_to_test = []
    for name, info in stats["collections"].items():
        if info.get("chunk_count", 0) > 100:
            collections_to_test.append((name, info))

    test_symbols = [
        ("search", "常见函数名"),
        ("BrokerEnum", "精确类名"),
        ("embed", "常见函数名"),
        ("FastMCP", "三方库类名"),
        ("NONEXISTENT_XYZ", "不存在的符号（最差情况）"),
    ]

    for col_name, info in collections_to_test:
        raw_dir = os.path.join(_raw_files_dir(), col_name)
        if not os.path.isdir(raw_dir):
            continue

        file_count = len(os.listdir(raw_dir))
        py_count = len([f for f in os.listdir(raw_dir) if f.endswith(".py")])

        print(f"\n{'=' * 70}")
        print(f"Collection: {col_name} ({info.get('doc_count', '?')} docs, {file_count} files, {py_count} .py)")
        print(f"{'=' * 70}")

        # --- 阶段 1: 全量 AST 扫描（旧方式）---
        invalidate_symbol_cache(col_name)

        print(f"\n--- [旧] 全量 AST 扫描 ---")
        for sym, desc in test_symbols:
            elapsed, results = time_it(
                _find_definition_full_scan, sym, col_name, raw_dir, 5
            )
            print(f"  find_def('{sym}') [{desc}] → {len(results)} results, {elapsed:.4f}s")

        # --- 阶段 2: 构建 Symbol 索引 ---
        print(f"\n--- 构建 Symbol 索引 ---")
        t0 = time.perf_counter()
        sym_index = build_symbol_index(col_name)
        build_time = time.perf_counter() - t0
        sym_count = sum(len(v) for v in (sym_index or {}).values())
        print(f"  构建耗时: {build_time:.4f}s | {sym_count} symbols")

        # --- 阶段 3: Symbol 索引查找（新方式）---
        index = _load_symbol_index(col_name)
        print(f"\n--- [新] Symbol 索引查找 ---")
        for sym, desc in test_symbols:
            elapsed, results = time_it(
                _find_definition_via_index, sym, col_name, index, raw_dir, 5
            )
            print(f"  find_def('{sym}') [{desc}] → {len(results)} results, {elapsed:.4f}s")

        # --- 阶段 4: 通过公共 API 测试（自动选择路径）---
        print(f"\n--- [公共 API] find_symbol_definition ---")
        for sym, desc in test_symbols:
            elapsed, results = time_it(find_symbol_definition, sym, col_name, 5)
            print(f"  find_def('{sym}') [{desc}] → {len(results)} results, {elapsed:.4f}s")

    print(f"\n{'=' * 70}")
    print("测试完成")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
