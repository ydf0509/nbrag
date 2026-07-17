"""批量调用 nbrag MCP 14 个工具的端到端测试。

通过 HTTP streamable-http 端点 (http://localhost:9101/mcp) 依次调用全部 14 个 tool，
打印每个调用的状态码 + 返回文本摘要，用于人工核对。

调用链顺序遵循 nbrag workflow：
  1.  nbrag_help                       (无参)
  2.  nbrag_stats                      (无参) → 拿到 collection_name
  3.  nbrag_list                       (collection_name) → 拿到 doc_id / file_path
  4.  nbrag_find_files                 (pattern, collection_name) → 拿到 file_path
  5.  nbrag_search                     (query, bm25_query, collection_name) → 拿到 chunk_index/line
  6.  nbrag_search_only_bm25           (bm25_query, collection_name)
  7.  nbrag_search_only_vector         (query, collection_name)
  8.  nbrag_search_and_fetch           (query, bm25_query, collection_name)
  9.  nbrag_grep                        (keyword, collection_name) → 拿到 doc_id/line
  10. nbrag_find_definition            (symbol, collection_name) — 非 py 源时返回 fallback 提示
  11. nbrag_get_file_chunks            (file_path, collection_name)
  12. nbrag_get_raw_file               (file_path, collection_name, line_start, line_end)
  13. nbrag_get_adjacent_chunks        (doc_id, chunk_index, collection_name)
  14. nbrag_get_chunks_by_lines        (doc_id, line_start, line_end, collection_name)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import my_load_config  # noqa: F401  加载环境变量

import requests

URL = "http://localhost:9101/mcp"
HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
session = requests.Session()
_id = 0


def post(method, params=None):
    global _id
    _id += 1
    payload = {"jsonrpc": "2.0", "id": _id, "method": method, "params": params or {}}
    r = session.post(URL, headers=HEADERS, json=payload, timeout=60)
    sid = r.headers.get("Mcp-Session-Id")
    if sid:
        session.headers["Mcp-Session-Id"] = sid
    # 强制 UTF-8 解码（requests 默认对 text/event-stream 用 ISO-8859-1 会把中文搞乱）
    r.encoding = "utf-8"
    body = r.text
    ct = r.headers.get("content-type") or ""
    parsed = None
    if "event-stream" in ct:
        # SSE: 合并所有 data: 行（用 \n 连接），然后 json.loads
        data_lines = []
        for line in body.splitlines():
            if line.startswith("data: "):
                data_lines.append(line[6:])
        if data_lines:
            data_str = "\n".join(data_lines)
            try:
                parsed = json.loads(data_str)
            except Exception:
                parsed = data_str  # fallback 返回拼接后的字符串
        else:
            parsed = f"[SSE but no data line] body_head={body[:300]!r}"
    else:
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
    return r.status_code, parsed


def call_tool(name, args):
    code, resp = post("tools/call", {"name": name, "arguments": args})
    text = ""
    if isinstance(resp, dict):
        if "error" in resp:
            text = f"[JSON-RPC error] {json.dumps(resp['error'], ensure_ascii=False)}"
        else:
            content = resp.get("result", {}).get("content", [])
            for c in content:
                if c.get("type") == "text":
                    text += c.get("text", "")
    else:
        text = str(resp)
    return code, text


def show(title, code, text, limit=1200):
    print("\n" + "=" * 80)
    print(f"[{title}]  HTTP={code}")
    print("-" * 80)
    print(text[:limit])
    if len(text) > limit:
        print(f"... (+{len(text) - limit} chars truncated)")


# ---------- 结果汇总表 ----------
_results = []  # [(name, http, status, note)]


def record(name, code, text):
    """汇总每个工具的状态：PASS / FAIL / ERROR，附简短 note。"""
    status = "PASS"
    note = ""
    if code != 200:
        status = "FAIL"
        note = f"HTTP {code}"
    elif "Error executing tool" in text:
        status = "FAIL"
        note = text.split("Error executing tool")[1].split("\n")[0][:80]
    elif '"error"' in text and "type=" in text:
        # 业务级 <error type="...">
        status = "ERROR"
        m = re.search(r'type="([^"]+)"', text)
        note = f"error tag: {m.group(1) if m else '?'}"
    elif not text.strip():
        status = "FAIL"
        note = "empty response"
    else:
        # 提取根标签第一行做 note
        first_xml = ""
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("<") and not line.startswith("<content"):
                first_xml = line[:80]
                break
        note = first_xml or text[:80].replace("\n", " ")
    _results.append((name, code, status, note))
    print(f">>> [{name}] status={status}  note={note}")


# ---------- 握手 ----------
post("initialize", {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "test-all-tools", "version": "1.0"},
})
post("notifications/initialized")

# 14 个工具的 collection_name 统一用 marriage_law（前面 stats 已确认存在）
COLL = "marriage_law"

# ---------- 1. nbrag_help ----------
code, t = call_tool("nbrag_help", {})
show("1. nbrag_help", code, t)
record("nbrag_help", code, t)

# ---------- 2. nbrag_stats ----------
code, t = call_tool("nbrag_stats", {})
show("2. nbrag_stats", code, t)
record("nbrag_stats", code, t)

# ---------- 3. nbrag_list ----------
code, t = call_tool("nbrag_list", {"collection_name": COLL, "limit": 5})
show("3. nbrag_list", code, t)
record("nbrag_list", code, t)

# 从 list 输出中提取第一个 doc_id 和 file_path
doc_id = ""
file_path = ""
m = re.search(r'doc_id="([^"]+)"', t) or re.search(r'doc_id:\s*([^\s,\n]+)', t)
if m:
    doc_id = m.group(1)
m = re.search(r'file_path="([^"]+)"', t) or re.search(r'file_path:\s*([^\s,\n]+)', t)
if m:
    file_path = m.group(1)
print(f"\n[parse] doc_id={doc_id!r}  file_path={file_path!r}")

# ---------- 4. nbrag_find_files ----------
# 用 file_path 的 basename 当 pattern
pattern = os.path.basename(file_path) if file_path else "婚姻"
code, t = call_tool("nbrag_find_files", {"pattern": pattern, "collection_name": COLL})
show("4. nbrag_find_files", code, t)
record("nbrag_find_files", code, t)
if not file_path:
    m = re.search(r'file_path="([^"]+)"', t)
    if m:
        file_path = m.group(1)
    print(f"[parse] updated file_path={file_path!r}")

# ---------- 5. nbrag_search ----------
code, t = call_tool("nbrag_search", {
    "query": "离婚时夫妻共同财产如何分割",
    "bm25_query": "离婚 共同财产 分割",
    "collection_name": COLL,
    "top_k": 3,
})
show("5. nbrag_search", code, t)
record("nbrag_search", code, t)
# 提取 chunk_index / line_start / line_end / doc_id
chunk_index = None
line_start = line_end = None
m = re.search(r'chunk_index="(\d+)"', t) or re.search(r'chunk_index:(\d+)', t)
if m:
    chunk_index = int(m.group(1))
m = re.search(r'line_start="(\d+)"', t) or re.search(r'line_start:(\d+)', t)
if m:
    line_start = int(m.group(1))
m = re.search(r'line_end="(\d+)"', t) or re.search(r'line_end:(\d+)', t)
if m:
    line_end = int(m.group(1))
if not doc_id:
    m = re.search(r'doc_id="([^"]+)"', t) or re.search(r'doc_id:([^\s,]+)', t)
    if m:
        doc_id = m.group(1)
print(f"[parse] chunk_index={chunk_index} line={line_start}-{line_end} doc_id={doc_id!r}")

# ---------- 6. nbrag_search_only_bm25 ----------
code, t = call_tool("nbrag_search_only_bm25", {
    "bm25_query": "夫妻共同财产 离婚",
    "collection_name": COLL,
    "top_k": 3,
})
show("6. nbrag_search_only_bm25", code, t)
record("nbrag_search_only_bm25", code, t)

# ---------- 7. nbrag_search_only_vector ----------
code, t = call_tool("nbrag_search_only_vector", {
    "query": "离婚财产分割的法律规定",
    "collection_name": COLL,
    "top_k": 3,
})
show("7. nbrag_search_only_vector", code, t)
record("nbrag_search_only_vector", code, t)

# ---------- 8. nbrag_search_and_fetch ----------
code, t = call_tool("nbrag_search_and_fetch", {
    "query": "什么情形下法院判决离婚",
    "bm25_query": "法院 判决 离婚 情形",
    "collection_name": COLL,
    "top_k": 3,
    "fetch_top_n_raw": 1,
    "fetch_context_chars": 800,
})
show("8. nbrag_search_and_fetch", code, t, limit=1500)
record("nbrag_search_and_fetch", code, t)

# ---------- 9. nbrag_grep ----------
code, t = call_tool("nbrag_grep", {
    "keyword": "共同财产",
    "collection_name": COLL,
    "max_results": 3,
})
show("9. nbrag_grep", code, t)
record("nbrag_grep", code, t)
# 补 doc_id / line
if not doc_id:
    m = re.search(r'doc_id="([^"]+)"', t) or re.search(r'doc_id:([^\s,]+)', t)
    if m:
        doc_id = m.group(1)
if line_start is None:
    m = re.search(r'line_start="(\d+)"', t) or re.search(r'line:(\d+)-(\d+)', t)
    if m:
        line_start = int(m.group(1))
        line_end = int(m.group(2)) if m.lastindex and m.lastindex >= 2 else line_start
print(f"[parse] after grep: doc_id={doc_id!r} line={line_start}-{line_end}")

# ---------- 10. nbrag_find_definition ----------
# 非 .py 集合，预期返回 fallback 或 not_found
code, t = call_tool("nbrag_find_definition", {
    "symbol": "离婚",
    "collection_name": COLL,
})
show("10. nbrag_find_definition", code, t)
record("nbrag_find_definition", code, t)

# ---------- 11. nbrag_get_file_chunks ----------
if file_path:
    code, t = call_tool("nbrag_get_file_chunks", {
        "file_path": file_path,
        "collection_name": COLL,
        "start_chunk": 0,
        "max_chunks": 2,
    })
    show("11. nbrag_get_file_chunks", code, t, limit=300)
    record("nbrag_get_file_chunks", code, t)
    # 提取 total_chunks
    m = re.search(r'total_chunks="(\d+)"', t) or re.search(r'total_chunks:(\d+)', t)
    if m:
        print(f"[parse] total_chunks={m.group(1)}")
    # 显示 Next page 行（这是之前 bug 点）
    np_m = re.search(r'Next page:.*', t)
    if np_m:
        print(f"[Next page hint] {np_m.group(0)}")
    else:
        print("[Next page hint] (none — has_more 可能是 false)")
else:
    print("\n[11. nbrag_get_file_chunks] SKIP — 无 file_path")

# ---------- 12. nbrag_get_raw_file ----------
if file_path:
    code, t = call_tool("nbrag_get_raw_file", {
        "file_path": file_path,
        "collection_name": COLL,
        "line_start": 1,
        "line_end": 20,
    })
    show("12. nbrag_get_raw_file", code, t)
    record("nbrag_get_raw_file", code, t)
else:
    print("\n[12. nbrag_get_raw_file] SKIP — 无 file_path")

# ---------- 13. nbrag_get_adjacent_chunks ----------
if doc_id and chunk_index is not None:
    code, t = call_tool("nbrag_get_adjacent_chunks", {
        "doc_id": doc_id,
        "chunk_index": chunk_index,
        "collection_name": COLL,
        "window": 1,
    })
    show("13. nbrag_get_adjacent_chunks", code, t)
    record("nbrag_get_adjacent_chunks", code, t)
else:
    print(f"\n[13. nbrag_get_adjacent_chunks] SKIP — doc_id={doc_id!r} chunk_index={chunk_index}")

# ---------- 14. nbrag_get_chunks_by_lines ----------
if doc_id and line_start is not None and line_end is not None:
    code, t = call_tool("nbrag_get_chunks_by_lines", {
        "doc_id": doc_id,
        "line_start": line_start,
        "line_end": line_end,
        "collection_name": COLL,
    })
    show("14. nbrag_get_chunks_by_lines", code, t)
    record("nbrag_get_chunks_by_lines", code, t)
else:
    print(f"\n[14. nbrag_get_chunks_by_lines] SKIP — doc_id={doc_id!r} line={line_start}-{line_end}")

print("\n" + "=" * 80)
print("done.")

# ---------- 汇总表 ----------
print("\n" + "#" * 80)
print("# SUMMARY — 14 tools")
print("#" * 80)
pass_n = fail_n = err_n = 0
for name, code, status, note in _results:
    if status == "PASS":
        pass_n += 1
    elif status == "FAIL":
        fail_n += 1
    else:
        err_n += 1
    print(f"  [{status:5}] {name:30}  {note}")
print("-" * 80)
print(f"TOTAL {len(_results)}  PASS {pass_n}  FAIL {fail_n}  ERROR {err_n}")
exit(0 if fail_n == 0 else 1)
