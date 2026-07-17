# Task 4: 重构 `nbrag_search_and_fetch`（含 `<fetched_raw>` section）

**Files:**
- Modify: `nbrag/mcp_tools.py:427-545`（`nbrag_search_and_fetch`）+ 抽 `_format_hit_xml` helper + 回改 `_format_search_results` 用它

**Interfaces:**
- Consumes: Task 2 的 `_meta_file_path(meta)` / `_meta_chunk_index(meta)` helper；Task 3 的 `_format_search_results` XML 格式
- Produces: `nbrag_search_and_fetch` 返回 `<nbrag_search_and_fetch>` XML，含 `<ranked_hits>` + `<fetched_raw>` 两个 section

## 当前代码结构（必读）

`nbrag_search_and_fetch` 在 L427-545，**不委托** `_format_search_results`，而是自己 inline 构建 ranked hits（L483-514，和 `_format_search_results` 里的逻辑重复）+ fetched_raw（L516-543）。

当前 ranked hits 部分（L483-514）用废弃字段名：`chunk:X/Y` / `chunk_index:X` / `total_chunks:Y` / `line:N-M` / `doc_id:X` / `dist:X` / `score:X`。

当前 fetched_raw 部分（L516-543）：
- 收集 `fetch_targets: dict[doc_id, {src, ranges}]`（L482-514 循环里填充）
- 对每个 doc_id 调 `get_file_chunks(src, collection_name, 0, 0, raw=True)` 拿原文
- 用 `_line_window_from_context_chars` 扩展 range，`_merge_line_ranges` 合并
- 输出 `original_file: ... | file_path: ... | doc_id: ... | range: line:N-M` + excerpt

## 目标

1. 抽 `_format_hit_xml` helper，让 `_format_search_results`（Task 3）和 `nbrag_search_and_fetch`（本 Task）共用，避免重复
2. `nbrag_search_and_fetch` 的 ranked hits 部分改用 `_format_hit_xml`
3. fetched_raw 部分改成 `<fetched_raw><raw ...><content>...</content></raw></fetched_raw>` XML

## 目标 XML 格式

```xml
<nbrag_search_and_fetch collection_name="my_kb" total_chunks="1234" bm25="on" rerank="...">
Follow-up handles in <hit>: file_path, doc_id, chunk_index, line_start, line_end.

<ranked_hits>
<hit rank="1" file_path="..." doc_id="..." chunk_index="..." total_chunks="..." line_start="..." line_end="..." scope="..." dist="..." score="...">
<content>...</content>
</hit>
</ranked_hits>

<fetched_raw>
<raw file_path="..." doc_id="..." line_start="8" line_end="35">
<content>
... 原始文件内容，原样无转义 ...
</content>
</raw>
</fetched_raw>

</nbrag_search_and_fetch>
```

关键规则：
- ranked hits 部分：和 Task 3 的 `<hit>` 格式完全一致（always include_content=True，因为 search_and_fetch 总是返回正文）
- fetched_raw 部分：同一文件多个不连续 range → 平铺多个 `<raw>`，每个都带 `file_path` / `doc_id` / `line_start` / `line_end`
- `<raw>` 的 `line_start` / `line_end` 是 **扩展+合并后** 的 range（不是原始 hit 的 range）
- 删除所有 header 散文（"This tool returns both..." / "query is the main..." / "fetch_context_chars is per..." / "Behavior note..." / "Ranked search results:" / "Auto-fetched original content..." / "Returned raw snippets come from..."）

## Steps

- [ ] **Step 1: 读当前 `nbrag_search_and_fetch`（L427-545）确认理解**

重点理解：
- `search()` 返回 `(documents, metadatas, distances, rerank_used, total, rerank_scores)`
- `fetch_targets` dict 的构建（L511-514：`i < fetch_top_n_raw` 时填充）
- fetched_raw 的 range 扩展+合并逻辑（L533-537）
- `get_file_chunks(src, collection_name, 0, 0, raw=True)` 的调用

- [ ] **Step 2: 抽 `_format_hit_xml` helper**

在 `_format_search_results` 之前（约 L272 附近）加：

```python
def _format_hit_xml(meta: dict, rank: int, dist: float, rerank_score: float | None, include_content: bool, doc: str = "") -> str:
    """Format one ranked hit as <hit> XML. Shared by _format_search_results and nbrag_search_and_fetch."""
    file_path = _meta_file_path(meta)
    chunk_index = _meta_chunk_index(meta)
    total_chunks = str(meta.get("total_chunks", "?"))
    line_start = str(meta.get("line_start", "?"))
    line_end = str(meta.get("line_end", "?"))
    scope = str(meta.get("scope", ""))
    doc_id = str(meta.get("doc_id", "?"))

    hit_attrs = [
        f'rank="{rank}"',
        f'file_path="{file_path}"',
        f'doc_id="{doc_id}"',
        f'chunk_index="{chunk_index}"',
        f'total_chunks="{total_chunks}"',
        f'line_start="{line_start}"',
        f'line_end="{line_end}"',
    ]
    if scope:
        hit_attrs.append(f'scope="{scope}"')
    hit_attrs.append(f'dist="{dist:.4f}"')
    if rerank_score is not None:
        hit_attrs.append(f'score="{rerank_score:.4f}"')

    if include_content:
        return f'<hit {" ".join(hit_attrs)}>\n<content>\n{doc}\n</content>\n</hit>'
    return f'<hit {" ".join(hit_attrs)} />'
```

- [ ] **Step 3: 回改 `_format_search_results`（Task 3 代码）用 `_format_hit_xml`**

把 Task 3 里 `_format_search_results` 的 hit 循环改成调用 `_format_hit_xml`，避免重复逻辑。注意 rerank_score 的传递：`rerank_scores[i] if rerank_scores and i < len(rerank_scores) else None`。

- [ ] **Step 4: 重写 `nbrag_search_and_fetch` 的 ranked hits 部分（L483-514）**

保留 `fetch_targets` 的构建逻辑（L511-514），但把 hit 格式化改成调 `_format_hit_xml`：

```python
    fetch_targets: dict[str, dict[str, Any]] = {}
    lines_hits = []
    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        if meta is None:
            meta = {}
        rerank_score = rerank_scores[i] if rerank_scores and i < len(rerank_scores) else None
        lines_hits.append(_format_hit_xml(meta, i + 1, dist, rerank_score, include_content=True, doc=doc))

        # fetch_targets 构建（保留原逻辑）
        src = _meta_file_path(meta)
        doc_id = str(meta.get("doc_id", "?"))
        _ls = meta.get("line_start", 0)
        _le = meta.get("line_end", 0)
        ls = int(_ls) if isinstance(_ls, (int, float)) else 0
        le = int(_le) if isinstance(_le, (int, float)) else 0
        if i < fetch_top_n_raw and doc_id != "?" and src != "?":
            if doc_id not in fetch_targets:
                fetch_targets[doc_id] = {"src": str(src), "ranges": []}
            fetch_targets[doc_id]["ranges"].append((ls, le))
```

- [ ] **Step 5: 重写 fetched_raw 部分（L516-543）为 `<fetched_raw>` XML**

保留 range 扩展+合并逻辑，改输出格式：

```python
    lines_fetched = []
    if fetch_top_n_raw > 0 and fetch_targets:
        for doc_id, info in fetch_targets.items():
            src = str(info["src"])
            ranges = info["ranges"]
            if not ranges:
                continue

            raw_data = get_file_chunks(src, collection_name, 0, 0, raw=True)
            if not raw_data.get("found"):
                continue

            raw_content = str(raw_data.get("content", ""))
            raw_lines, offsets = _build_line_char_index(raw_content)
            expanded_ranges = [
                _line_window_from_context_chars(raw_lines, offsets, ls, le, fetch_context_chars)
                for ls, le in ranges
            ]
            merged_ranges = _merge_line_ranges(expanded_ranges)

            for start, end in merged_ranges:
                excerpt = "".join(raw_lines[start - 1:end]) if raw_lines else raw_content
                lines_fetched.append(
                    f'<raw file_path="{src}" doc_id="{doc_id}" line_start="{start}" line_end="{end}">\n'
                    f'<content>\n{excerpt}\n</content>\n</raw>'
                )
```

- [ ] **Step 6: 组装最终返回**

```python
    rerank_str = cfg.rerank.model if rerank_used else "off"
    bm25_str = "off" if path_filter else "on"
    root_attrs = [f'collection_name="{collection_name}"', f'total_chunks="{total}"', f'bm25="{bm25_str}"', f'rerank="{rerank_str}"']
    if path_filter:
        root_attrs.append(f'filter_file_path="{path_filter}"')

    lines = [f"<nbrag_search_and_fetch {' '.join(root_attrs)}>"]
    lines.append("Follow-up handles in <hit>: file_path, doc_id, chunk_index, line_start, line_end.")
    lines.append("")
    lines.append("<ranked_hits>")
    lines.extend(lines_hits)
    lines.append("</ranked_hits>")
    lines.append("")
    if lines_fetched:
        lines.append("<fetched_raw>")
        lines.extend(lines_fetched)
        lines.append("</fetched_raw>")
        lines.append("")
    lines.append("</nbrag_search_and_fetch>")
    return "\n".join(lines)
```

- [ ] **Step 7: grep 扫描确认 L427-L560 无废弃字段名**

Run Grep:
```
pattern: "chunk:\\d|chunk:[A-Z]|line:\\d|line:[A-Z]|matched_line|line_range|chunk_count|original_file"
path: nbrag/mcp_tools.py
```
重点看该区间无命中（`original_file` 是旧 fetched_raw 的字段名，应已废弃）。

- [ ] **Step 8: import 验证**

Run:
```powershell
$env:OPENBLAS_NUM_THREADS=1
D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import nbrag_search_and_fetch, _format_hit_xml, _format_search_results; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 9: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): XML format for nbrag_search_and_fetch with fetched_raw section"
```

## Global Constraints（适用于本 Task）

- **Python 解释器**：`D:/ProgramData/miniconda3/envs/py312/python.exe`
- **OpenBLAS 绕过**：`$env:OPENBLAS_NUM_THREADS=1`
- **不改函数签名**：`nbrag_search_and_fetch` 公开签名不变
- **DRY**：抽 `_format_hit_xml` helper，回改 `_format_search_results` 用它
- **canonical handle 字段集**：`file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`
- **禁止变体**：`chunk:X/Y` / `line:N-M` / `chunk_index:X` / `original_file` / `range: line:N-M`
- **正文零转义**：`<content>` 内纯文本
- **保留 range 扩展+合并逻辑**：`_line_window_from_context_chars` / `_merge_line_ranges` 不改
- **不写正式测试**
