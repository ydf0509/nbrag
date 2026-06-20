"""
BM25 单独检索效果测试脚本（不依赖向量搜索和 reranker）。

用途定位：
  - 这个脚本的目标是隔离向量检索影响，单独观察 BM25 多通道召回 + Weighted RRF 融合的贡献。
  - 它适合回答“这次命中是不是 BM25 的功劳”，不适合代表最终 MCP hybrid search 的端到端质量。
  - 如果某个 query 在这里能命中，说明词法检索本身有效；如果最终 MCP 搜索命中更好，则可能是向量 / rerank 的额外贡献。

测试方式：
  1. 直接调用 nbrag.bm25_index 中的 BM25 检索函数
  2. 从 ChromaDB 取回 chunk 内容展示结果
  3. 显示每个通道的命中情况和 RRF 融合后的排序

用法：
  D:/ProgramData/miniconda3/envs/py312/python.exe tests/test_bm25_only.py
"""

import sys
import os
from collections import Counter

# 确保能从项目根目录导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nbrag.bm25_index import (
    _bm25_search_channels,
    _weighted_rrf_fusion,
    _BM25_CHANNEL_WEIGHTS,
)
from nbrag.storage import _get_existing_collection, _batch_get
from nbrag.config import get_config

# ============================================================
# 测试查询集（覆盖劳动法的典型场景）
# ============================================================
TEST_QUERIES = [
    # --- 自然语言问法 ---
    ("试用期被辞退有赔偿吗", "自然语言: 试用期辞退赔偿"),
    ("加班费怎么算 加班工资标准", "自然语言: 加班费计算"),
    ("公司不交社保怎么办", "自然语言: 不交社保"),
    ("孕妇可以辞退吗", "自然语言: 孕妇辞退"),
    ("离职后年终奖不发合法吗", "自然语言: 年终奖"),

    # --- 精确条文号 ---
    ("第四十七条", "条文号: 第47条"),
    ("第三十九条 单位解除", "条文号+关键词: 第39条解除"),
    ("第十四条 工伤认定", "条文号+关键词: 第14条工伤"),
    ("第四十四条 加班费", "条文号+关键词: 第44条加班"),

    # --- 专业术语 ---
    ("竞业限制 经济补偿 30%", "专业术语: 竞业限制"),
    ("N+1 赔偿", "口语化: N+1赔偿"),
    ("停工留薪期", "专业术语: 停工留薪期"),
    ("非本人主要责任 交通事故", "复合条件: 工伤交通事故"),
]


def _get_chroma_data(collection_name, chunk_ids):
    """从 ChromaDB 批量获取 chunk 的文本和 metadata。"""
    col = _get_existing_collection(collection_name)
    if col is None:
        return {}
    try:
        data = _batch_get(col, ids=list(chunk_ids), include=["documents", "metadatas"])
        result = {}
        for i, cid in enumerate(data["ids"]):
            if cid in chunk_ids:
                result[cid] = {
                    "doc": data["documents"][i] if data["documents"] else "",
                    "meta": data["metadatas"][i] if data["metadatas"] else {},
                }
        return result
    except Exception as e:
        print(f"  [WARN] Chroma batch get failed: {e}")
        return {}


def truncate(text, max_len=120):
    """截断长文本用于预览。"""
    text = text.strip().replace("\n", " ").replace("\r", "")
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def get_source_file(meta):
    """从 metadata 中提取可读的文件名。"""
    raw = meta.get("source", "") or meta.get("filename", "?")
    return os.path.basename(raw)


def run_test(collection_name):
    """对每个测试查询运行 BM25 检索并展示结果。"""
    print(f"\n{'='*70}")
    print(f"  知识库: {collection_name}")
    print(f"{'='*70}")

    for query, description in TEST_QUERIES:
        print(f"\n{'─'*70}")
        print(f"  [{description}]")
        print(f"  查询词: \"{query}\"")
        print(f"{'─'*70}")

        # 1) BM25 多通道检索
        top_k = 10
        channel_results = _bm25_search_channels(query, collection_name, top_k)

        if not channel_results:
            print("  ❌ BM25 未命中任何结果")
            continue

        # 2) 按通道展示
        all_ids = []
        channel_detail = []
        for channel in ["word", "ngram", "code"]:
            ids = channel_results.get(channel, [])
            all_ids.extend(ids)
            weight = _BM25_CHANNEL_WEIGHTS.get(channel, 1.0)
            hit_desc = f"{len(ids):>2} hits" if ids else "   no hit"
            channel_detail.append((channel, ids, weight))
            print(f"  📡 channel [{channel}](w={weight}): {hit_desc}")

        # 3) 加权 RRF 融合
        ranked_sources = [
            (channel, ids, weight)
            for channel, ids, weight in channel_detail
            if ids
        ]
        if not ranked_sources:
            print("  ❌ 融合后无结果")
            continue

        fused = _weighted_rrf_fusion(ranked_sources)[:top_k]

        # 4) 从 Chroma 取内容
        unique_ids = list(dict.fromkeys(all_ids))
        chroma_data = _get_chroma_data(collection_name, unique_ids)

        # 5) 展示融合结果
        print(f"\n  🔀 RRF 融合结果 (前{min(5, len(fused))}):")
        for rank, cid in enumerate(fused[:5], 1):
            info = chroma_data.get(cid, {})
            meta = info.get("meta", {})
            doc_text = info.get("doc", "")

            filename = get_source_file(meta)
            line_start = meta.get("line_start", "?")
            line_end = meta.get("line_end", "?")
            scope = meta.get("scope", "")

            # 显示每个结果被哪些通道命中
            channel_sources = []
            for ch_name, ch_ids, _ in channel_detail:
                if cid in ch_ids:
                    channel_sources.append(ch_name)
            src_str = "+".join(channel_sources)

            print(f"    #{rank} [{src_str}] {filename} L{line_start}-{line_end}")
            if scope:
                print(f"         scope: {scope}")
            print(f"         {truncate(doc_text, 150)}")

        # 6) 统计：各通道的独立命中、重叠情况
        all_id_set = set(all_ids)
        word_set = set(channel_results.get("word", []))
        ngram_set = set(channel_results.get("ngram", []))
        code_set = set(channel_results.get("code", []))

        overlap_count = 0
        for cid in all_id_set:
            present_in = sum([cid in word_set, cid in ngram_set, cid in code_set])
            if present_in >= 2:
                overlap_count += 1

        print(f"\n  📊 统计: 独立chunk数={len(all_id_set)}, "
              f"多通道重叠={overlap_count}, "
              f"融合后前top_k={len(set(fused))}")

        # 7) 展示融合后的前10个来源文件分布
        file_counter = Counter()
        for cid in fused:
            info = chroma_data.get(cid, {})
            meta = info.get("meta", {})
            file_counter[get_source_file(meta)] += 1
        if file_counter:
            file_dist = " | ".join(f"{f}({c})" for f, c in file_counter.most_common(5))
            print(f"  📂 文件分布(top5): {file_dist}")


def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       BM25 单独检索效果测试（无向量 / 无 Reranker）      ║")
    print("╚══════════════════════════════════════════════════════════╝")

    config = get_config()
    print(f"\n  数据目录: {config.storage.db_path}")
    print(f"  BM25 权重: word=1.10, ngram=0.75, code=1.20\n")

    # 测试劳动者权益知识库
    run_test("worker_rights")


if __name__ == "__main__":
    main()
