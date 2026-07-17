# Task 4 Review: `nbrag_search_and_fetch` XML refactor

**Reviewed file:** `d:\codes\nbrag\nbrag\mcp_tools.py`
**Implementer commit:** `db0eaee5613e981a82d97df2349fa3136d0fe576`
**Diff stat:** 1 file changed, 61 insertions(+), 80 deletions(-)

---

## 1. `_format_hit_xml` helper 存在性 / 签名 / 输出

**位置：** `nbrag/mcp_tools.py:273-300`

签名与 brief Step 2 完全一致：

```python
def _format_hit_xml(meta: dict, rank: int, dist: float, rerank_score: float | None, include_content: bool, doc: str = "") -> str:
```

- ✅ 使用 Task 2 的 `_meta_file_path(meta)` / `_meta_chunk_index(meta)` 提取 canonical handle
- ✅ 产出 canonical 属性集：`rank` / `file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`
- ✅ 可选属性 `scope`（非空才加）、`dist`（恒加）、`score`（rerank_score 非 None 才加）
- ✅ `include_content=True` → `<hit ...>\n<content>\n{doc}\n</content>\n</hit>`
- ✅ `include_content=False` → `<hit ... />`（自闭合）
- ✅ 输出为合法 `<hit>` XML 片段

---

## 2. `_format_search_results` 是否真正回改用 helper（DRY）

**位置：** `nbrag/mcp_tools.py:352-356`

原 30 行 inline hit-formatting 块被替换为单一委托调用：

```python
for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
    if meta is None:
        meta = {}
    rerank_score = rerank_scores[i] if rerank_scores and i < len(rerank_scores) else None
    lines.append(_format_hit_xml(meta, i + 1, dist, rerank_score, include_content, doc=doc))
```

- ✅ DRY 强制要求满足：不再是"left as-is"
- ✅ 行为保持：旧代码 5 个独立 list 项（`<hit>`、`<content>`、`doc`、`</content>`、`</hit>`）join 后与 helper 返回的单字符串 `\n`-joined 形式字节一致
- ✅ `rerank_score` 传递逻辑：`rerank_scores[i] if rerank_scores and i < len(rerank_scores) else None` 与 brief Step 3 一致
- ✅ `score` 属性添加条件（`rerank_score is not None`）等价于旧 `rerank_scores and i < len(rerank_scores)` 闸门

---

## 3. `nbrag_search_and_fetch` ranked hits 是否用 helper

**位置：** `nbrag/mcp_tools.py:464-468`

```python
for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
    if meta is None:
        meta = {}
    rerank_score = rerank_scores[i] if rerank_scores and i < len(rerank_scores) else None
    lines_hits.append(_format_hit_xml(meta, i + 1, dist, rerank_score, include_content=True, doc=doc))
```

- ✅ ranked hits 用同一 `_format_hit_xml` helper
- ✅ `include_content=True` 硬编码（brief 要求 search_and_fetch 总返回正文）
- ✅ 同一循环同时构建 `fetch_targets`，原逻辑保留（L470-480）

---

## 4. `<fetched_raw>` section 格式

**位置：** `nbrag/mcp_tools.py:502-507`

```python
for start, end in merged_ranges:
    excerpt = "".join(raw_lines[start - 1:end]) if raw_lines else raw_content
    lines_fetched.append(
        f'<raw file_path="{src}" doc_id="{doc_id}" line_start="{start}" line_end="{end}">\n'
        f'<content>\n{excerpt}\n</content>\n</raw>'
    )
```

- ✅ 格式：`<raw file_path=... doc_id=... line_start=... line_end=...><content>...</content></raw>` 符合 brief
- ✅ 每个 `<raw>` 带 `file_path` / `doc_id` / `line_start` / `line_end` 4 个属性
- ✅ 同文件 N 个不连续 merged ranges → N 个平铺 `<raw>` 元素（L502 循环逐个输出）
- ✅ `<content>` 内正文零转义（brief 全局约束）
- ✅ `lines_fetched` 为空时整个 `<fetched_raw>` section 省略（L520 `if lines_fetched:`）

---

## 5. `<raw>` 的 `line_start`/`line_end` 是否 post-merge

**位置：** `nbrag/mcp_tools.py:496-505`

```python
expanded_ranges = [
    _line_window_from_context_chars(raw_lines, offsets, ls, le, fetch_context_chars)
    for ls, le in ranges
]
merged_ranges = _merge_line_ranges(expanded_ranges)

for start, end in merged_ranges:
    ...
    f'<raw file_path="{src}" doc_id="{doc_id}" line_start="{start}" line_end="{end}">\n'
```

- ✅ `start` / `end` 来自 `merged_ranges`（即 expanded + merged 后的 range）
- ✅ 不是原始 hit 的 `(ls, le)`
- ✅ `_line_window_from_context_chars` / `_merge_line_ranges` 两个 helper 未改（仅在调用处使用）

---

## 6. Header prose 是否删除

Grep 9 个目标散文短语：

```
This tool returns both... | query is the main... | fetch_context_chars is per...
Behavior note... | Ranked search results: | Auto-fetched original content...
Returned raw snippets come from...
```

**结果：** `No matches found` — 全部删除。

- ✅ 旧 `[collection] N chunks | bm25: ... | rerank: ...` header 行删除（diff L459-462 可见）
- ✅ 替换为单一 canonical 提示行：`Follow-up handles in <hit>: file_path, doc_id, chunk_index, line_start, line_end.`（L514）

---

## 7. 改动区间无废弃字段名

Grep 模式：`original_file|chunk:\d|chunk:[A-Z]|line:\d|line:[A-Z]|chunk_index:\d|total_chunks:\d|dist:\d|score:\d|doc_id:[a-zA-Z0-9]|scope:[a-zA-Z]|range:\s*line:`

**命中行号：** 266, 571, 671, 680, 744, 753, 760, 792, 793 — **全部在 L428-L526 之外**。

| 命中行 | 所在函数 | 与 Task 4 关系 |
|--------|---------|---------------|
| 266 | `nbrag_help` docstring | 未改，out of scope |
| 571 | `nbrag_grep` | 未改，out of scope |
| 671, 680 | `nbrag_get_adjacent_chunks` recovery 文案 | 未改，out of scope |
| 744, 753, 760 | `nbrag_get_chunks_by_lines` | 未改，out of scope |
| 792, 793 | `nbrag_get_raw_file` | 未改，Task 5+ 范围 |

- ✅ `nbrag_search_and_fetch`（L428-L526）内零废弃字段名
- ✅ 旧 fetched_raw 的 `original_file:` / `range: line:N-M` 已彻底移除（仅在 `nbrag_get_raw_file` L792-793 残留，属 Task 5+ 范围）

---

## 8. XML 良构性

按代码组装逻辑构造样例输出：

```xml
<nbrag_search_and_fetch collection_name="..." total_chunks="..." bm25="..." rerank="...">
Follow-up handles in <hit>: file_path, doc_id, chunk_index, line_start, line_end.

<ranked_hits>
<hit rank="1" file_path="..." doc_id="..." chunk_index="..." total_chunks="..." line_start="..." line_end="..." scope="..." dist="..." score="...">
<content>
...
</content>
</hit>
</ranked_hits>

<fetched_raw>
<raw file_path="..." doc_id="..." line_start="..." line_end="...">
<content>
...
</content>
</raw>
</fetched_raw>

</nbrag_search_and_fetch>
```

- ✅ 根标签 `<nbrag_search_and_fetch ...>` 闭合
- ✅ `<ranked_hits>` ... `</ranked_hits>` 闭合
- ✅ `<hit>` 内嵌 `<content>`，`include_content=False` 时自闭合
- ✅ `<fetched_raw>` 仅在有内容时出现，闭合
- ✅ `<raw>` 内嵌 `<content>`，闭合
- ✅ 属性值均用双引号包裹

---

## 9. 其他约束验证

- ✅ **仅 `nbrag/mcp_tools.py` 修改**（diff 单文件）
- ✅ **`nbrag_search_and_fetch` 公开签名未变**（L428-436 与原一致）
- ✅ **`fetch_targets` 构建逻辑保留**（L477-480：`i < fetch_top_n_raw and doc_id != "?" and src != "?"`）
- ✅ **range 扩展+合并逻辑未改**（L496-500 调用形式与原一致）
- ✅ **未写正式测试**（仅 import 验证）
- ✅ **`bm25_str` 语义未变**（`"off" if path_filter else "on"`，与原一致）
- ✅ **`src = _meta_file_path(meta)`** 已用 Task 2 helper 替代旧 `meta.get("source", meta.get("filename", "?"))`（L471）

---

## Verdict

- **Spec compliance: ✅**（全部 8 项审查点通过，DRY 强制要求满足，无废弃字段名残留）
- **Task quality: Approved**（实现忠实于 brief，行为保持，无回归风险，无 scope 蔓延）

实现质量高，DRY 重构彻底，XML 良构，所有约束均满足。可以进入 Task 5。
