"""Combo workflow end-to-end test: verify XML returns let an LLM-like agent
chain nbrag tools by extracting follow-up handles from each XML response.

Chain: nbrag_help -> nbrag_stats -> nbrag_search -> nbrag_get_adjacent_chunks
       -> nbrag_get_raw_file -> nbrag_get_chunks_by_lines
"""

import re
import sys

sys.path.insert(0, ".")
from _mcp_request import call_mcp_tool  # noqa: E402


def extract_attrs(xml: str, tag: str, idx: int = 0) -> dict:
    """Extract attributes from the idx-th non-empty <tag ...> match in xml."""
    pattern = re.compile(rf"<{tag}\b([^>]*)>")
    non_empty = []
    for raw in pattern.findall(xml):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', raw))
        if attrs:
            non_empty.append(attrs)
    if idx >= len(non_empty):
        return {}
    return non_empty[idx]


def extract_surfacing(xml: str) -> dict:
    """Extract top-result handles from the new AI-facing surfacing block.

    Reads lines like '  file_path = D:/codes/...' (spaced equals) which are
    visually distinct from XML attributes and carry no <tag> ambiguity.
    """
    handles = {}
    for key in ("file_path", "doc_id", "chunk_index", "line_start", "line_end", "total_chunks"):
        m = re.search(rf"^\s+{key}\s+=\s+(.+)$", xml, re.MULTILINE)
        if m:
            handles[key] = m.group(1).strip()
    return handles


def step(title: str, xml: str) -> None:
    print(f"\n{'='*70}\n{title}\n{'='*70}")
    print(xml[:1200])
    if len(xml) > 1200:
        print(f"\n... [truncated, total {len(xml)} chars]")


# Step 1: help
xml_help = call_mcp_tool("nbrag_help", {})
step("STEP 1: nbrag_help()", xml_help)

# Step 2: stats -> pick collection_name from <collection collection_name="...">
xml_stats = call_mcp_tool("nbrag_stats", {})
step("STEP 2: nbrag_stats()", xml_stats)
coll_attrs = extract_attrs(xml_stats, "collection", 0)
collection_name = coll_attrs.get("collection_name", "")
assert collection_name, "FAILED: cannot extract collection_name from <collection>"
print(f"\n[extracted] collection_name = {collection_name!r}")

# Step 3: search -> pick file_path, doc_id, chunk_index, line_start, line_end from top <hit>
xml_search = call_mcp_tool("nbrag_search", {
    "query": "试用期 最长不能超过多久",
    "bm25_query": "试用期 期限 一年 劳动合同",
    "collection_name": collection_name,
    "top_k": 3,
    "include_content": False,
})
step("STEP 3: nbrag_search()", xml_search)
surfaced = extract_surfacing(xml_search)
hit = extract_attrs(xml_search, "hit", 0)
print(f"\n[surfacing block] {surfaced}")
print(f"[<hit> fallback ] doc_id={hit.get('doc_id')!r} chunk_index={hit.get('chunk_index')!r}")
src = surfaced if surfaced else hit
doc_id = src.get("doc_id", "")
chunk_index = src.get("chunk_index", "")
file_path = src.get("file_path", "")
line_start = src.get("line_start", "")
line_end = src.get("line_end", "")
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
adj_chunk = extract_attrs(xml_adj, "chunk", 0)
assert adj_chunk, "FAILED: cannot extract attrs from adjacent <chunk>"
print(f"[extracted] adjacent chunk_index={adj_chunk.get('chunk_index')!r} line_start={adj_chunk.get('line_start')!r} line_end={adj_chunk.get('line_end')!r}")

# Step 5: get_raw_file(file_path, line_start, line_end) -> verify raw text retrieval
xml_raw = call_mcp_tool("nbrag_get_raw_file", {
    "file_path": file_path,
    "collection_name": collection_name,
    "line_start": int(line_start),
    "line_end": int(line_end),
})
step("STEP 5: nbrag_get_raw_file()", xml_raw)
assert "<error" not in xml_raw, "FAILED: get_raw_file returned error"

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
