"""Combo workflow end-to-end test: verify XML returns let an LLM-like agent
chain nbrag tools by extracting follow-up handles from each XML response.

Chain: nbrag_help -> nbrag_stats -> nbrag_search -> nbrag_get_adjacent_chunks
       -> nbrag_read_more_original_text -> nbrag_get_chunks_by_lines
"""

import re
import sys

sys.path.insert(0, ".")
from _mcp_request import call_mcp_tool  # noqa: E402


def extract_fields(xml: str, tag: str, idx: int = 0) -> dict:
    """Extract key = value fields from the idx-th <tag> entity."""
    entities = re.findall(rf"<{tag}>\n(.*?)\n</{tag}>", xml, re.DOTALL)
    if idx >= len(entities):
        return {}
    return dict(
        line.split(" = ", 1)
        for line in entities[idx].splitlines()
        if " = " in line
    )


def step(title: str, xml: str) -> None:
    print(f"\n{'='*70}\n{title}\n{'='*70}")
    print(xml[:1200])
    if len(xml) > 1200:
        print(f"\n... [truncated, total {len(xml)} chars]")


# Step 1: help
xml_help = call_mcp_tool("nbrag_help", {})
step("STEP 1: nbrag_help()", xml_help)

# Step 2: stats -> pick collection_name from first <nbrag_collection>
xml_stats = call_mcp_tool("nbrag_stats", {})
step("STEP 2: nbrag_stats()", xml_stats)
collection = extract_fields(xml_stats, "nbrag_collection")
collection_name = collection.get("collection_name", "")
assert collection_name, "FAILED: cannot extract collection_name from <nbrag_collection>"
print(f"\n[extracted] collection_name = {collection_name!r}")

# Step 3: search -> pick file_path, doc_id, chunk_index, line_start, line_end from top <nbrag_ranked_hit>
xml_search = call_mcp_tool("nbrag_search", {
    "query": "试用期 最长不能超过多久",
    "bm25_query": "试用期 期限 一年 劳动合同",
    "collection_name": collection_name,
    "top_k": 3,
    "include_content": False,
})
step("STEP 3: nbrag_search()", xml_search)
hit = extract_fields(xml_search, "nbrag_ranked_hit")
print(f"\n[<nbrag_ranked_hit>] doc_id={hit.get('doc_id')!r} chunk_index={hit.get('chunk_index')!r}")
doc_id = hit.get("doc_id", "")
chunk_index = hit.get("chunk_index", "")
file_path = hit.get("file_path", "")
line_start = hit.get("line_start", "")
line_end = hit.get("line_end", "")
print(f"[extracted] doc_id={doc_id!r} chunk_index={chunk_index!r} file_path={file_path!r} line_start={line_start!r} line_end={line_end!r}")
assert doc_id and chunk_index and file_path, "FAILED: missing core handles"

# Step 4: get_adjacent_chunks(doc_id, chunk_index) -> verify follow-up works
xml_adj = call_mcp_tool("nbrag_get_adjacent_chunks", {
    "doc_id": doc_id,
    "chunk_index": int(chunk_index),
    "collection_name": collection_name,
    "window": 2,
})
step("STEP 4: nbrag_get_adjacent_chunks()", xml_adj)
adj_chunk = extract_fields(xml_adj, "nbrag_chunk")
assert adj_chunk, "FAILED: cannot extract fields from adjacent <nbrag_chunk>"
print(f"[extracted] adjacent chunk_index={adj_chunk.get('chunk_index')!r} line_start={adj_chunk.get('line_start')!r} line_end={adj_chunk.get('line_end')!r}")

# Step 5: read_more_original_text(file_path, line_start, line_end) -> verify original-text retrieval
xml_raw = call_mcp_tool("nbrag_read_more_original_text", {
    "file_path": file_path,
    "collection_name": collection_name,
    "line_start": int(line_start),
    "line_end": int(line_end),
})
step("STEP 5: nbrag_read_more_original_text()", xml_raw)
assert "<error" not in xml_raw, "FAILED: nbrag_read_more_original_text returned error"

# Step 6: get_chunks_by_lines(doc_id, line_start, line_end) -> reverse-locate chunks
xml_cbl = call_mcp_tool("nbrag_get_chunks_by_lines", {
    "doc_id": doc_id,
    "line_start": int(line_start),
    "line_end": int(line_end),
    "collection_name": collection_name,
})
step("STEP 6: nbrag_get_chunks_by_lines()", xml_cbl)
assert "<error" not in xml_cbl, "FAILED: get_chunks_by_lines returned error"

print("\n" + "=" * 70)
print("COMBO WORKFLOW PASSED: all 6 steps chained via XML handle extraction.")
print("=" * 70)
