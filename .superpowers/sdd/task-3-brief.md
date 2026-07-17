# Task 3: 重构 `_format_search_results`（影响 3 个 search 函数）

**Files:**
- Modify: `nbrag/mcp_tools.py:273-414`（`_format_search_results` + 3 个调用方）

**Interfaces:**
- Consumes: Task 2 的 `_meta_file_path(meta)` / `_meta_chunk_index(meta)` helper
- Produces: `_format_search_results` 返回 `<nbrag_search>` XML 格式；3 个 search 函数各自传正确的 `root_tag`

## 当前代码结构（必读）

`_format_search_results` 在 L273-354，是 `nbrag_search` / `nbrag_search_only_bm25` 共用的内部格式化函数。

3 个调用方：
- `nbrag_search`（L357）→ 调 `_format_search_results(use_vector=True, ...)`
- `nbrag_search_only_bm25`（L380）→ 调 `_format_search_results(use_vector=False, use_bm25=True, use_rerank=False, ...)`
- `nbrag_search_only_vector`（L399）→ 当前委托给 `nbrag_search(use_rerank=False, use_bm25=False, ...)`

当前返回格式（L311-354）是散文式：
```
[collection_name] 1234 chunks | bm25: on | rerank: model_name
Returned handle fields for follow-up: file_path, doc_id, chunk_index, line range.
query is the main semantic query...

[1/5] foo.py chunk:3/10 chunk_index:3 total_chunks:10 line:15-28 scope:ClassA.get_by_id doc_id:abc123 dist:0.1234 score:0.5678
file_path: D:/codes/foo.py
<content or "content omitted">

[2/5] ...
```

## 目标 XML 格式

```xml
<nbrag_search collection_name="my_kb" total_chunks="1234" bm25="on" rerank="BAAI/bge-reranker-v2-m3">
Follow-up handles in <hit>: file_path, doc_id, chunk_index, line_start, line_end.

<ranked_hits>
<hit rank="1" file_path="D:/codes/foo.py" doc_id="abc123" chunk_index="3" total_chunks="10" line_start="15" line_end="28" scope="ClassA.get_by_id" dist="0.1234" score="0.5678">
<content>
def get_by_id(self, id):
    ...
</content>
</hit>
</ranked_hits>

</nbrag_search>
```

关键规则：
- `include_content=False` 时 `<hit>` 自闭合 `<hit ... />`（不写 `<content>`）
- `filter_file_path` 为空时省略该属性；非空时加到根属性 `filter_file_path="..."`
- `bm25` 属性值：`"on"` / `"off"`
- `rerank` 属性值：模型名 / `"off"`
- `scope` 为空时省略该属性
- `score` 只有 `rerank_scores` 有值时才写
- 删除 header 里的 query/bm25_query 解释散文、behavior note 散文

## Steps

- [ ] **Step 1: 读当前 `_format_search_results`（L273-354）确认理解**

重点理解：
- `search()` 返回 `(documents, metadatas, distances, rerank_used, total, rerank_scores)` 六元组
- `meta` dict 的 key：`source` / `filename` / `chunk_index` / `total_chunks` / `line_start` / `line_end` / `scope` / `doc_id`
- `bm25_str` / `rerank_str` 的计算逻辑（L309-310）

- [ ] **Step 2: 给 `_format_search_results` 加 `root_tag` 参数**

在函数签名加 `root_tag: str = "nbrag_search"` 参数（放在 `bm25_query` 之后）。

- [ ] **Step 3: 重写 `_format_search_results` 的返回部分（L309-354）为 XML**

保留 L284-307 的逻辑不变（参数归一化、path_filter 校验、search() 调用、collection_issue 检查、no_results 检查）。

重写 L309-354 的返回构建逻辑：

```python
    rerank_str = cfg.rerank.model if rerank_used else "off"
    bm25_str = "off" if path_filter and use_vector else ("on" if use_bm25 else "off")

    # 根标签属性
    root_attrs = [f'collection_name="{collection_name}"', f'total_chunks="{total}"', f'bm25="{bm25_str}"', f'rerank="{rerank_str}"']
    if path_filter:
        root_attrs.append(f'filter_file_path="{path_filter}"')
    lines = [f"<{root_tag} {' '.join(root_attrs)}>"]
    lines.append("Follow-up handles in <hit>: file_path, doc_id, chunk_index, line_start, line_end.")
    lines.append("")
    lines.append("<ranked_hits>")

    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        if meta is None:
            meta = {}
        file_path = _meta_file_path(meta)
        chunk_index = _meta_chunk_index(meta)
        total_chunks = str(meta.get("total_chunks", "?"))
        line_start = str(meta.get("line_start", "?"))
        line_end = str(meta.get("line_end", "?"))
        scope = str(meta.get("scope", ""))
        doc_id = str(meta.get("doc_id", "?"))

        hit_attrs = [
            f'rank="{i + 1}"',
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
        if rerank_scores and i < len(rerank_scores):
            hit_attrs.append(f'score="{rerank_scores[i]:.4f}"')

        if include_content:
            lines.append(f'<hit {" ".join(hit_attrs)}>')
            lines.append("<content>")
            lines.append(doc)
            lines.append("</content>")
            lines.append("</hit>")
        else:
            lines.append(f'<hit {" ".join(hit_attrs)} />')

    lines.append("</ranked_hits>")
    lines.append("")
    lines.append(f"</{root_tag}>")
    return "\n".join(lines)
```

- [ ] **Step 4: 修改 `nbrag_search`（L357）传 `root_tag`**

```python
def nbrag_search(...) -> str:
    return _format_search_results(
        ...
        bm25_query=bm25_query,
        root_tag="nbrag_search",
    )
```

- [ ] **Step 5: 修改 `nbrag_search_only_bm25`（L380）传 `root_tag`**

```python
def nbrag_search_only_bm25(...) -> str:
    return _format_search_results(
        ...
        root_tag="nbrag_search_only_bm25",
    )
```

- [ ] **Step 6: 修改 `nbrag_search_only_vector`（L399）改为直接调 `_format_search_results`**

当前它委托给 `nbrag_search`，但那样 root_tag 会是 "nbrag_search" 而非 "nbrag_search_only_vector"。改成直接调 `_format_search_results`：

```python
def nbrag_search_only_vector(
    query: str,
    collection_name: str,
    top_k: int = 5,
    filter_file_path: str = "",
    include_content: bool = True,
) -> str:
    return _format_search_results(
        query=query,
        collection_name=collection_name,
        top_k=top_k,
        use_rerank=False,
        use_bm25=False,
        use_vector=True,
        filter_file_path=filter_file_path,
        include_content=include_content,
        root_tag="nbrag_search_only_vector",
    )
```

- [ ] **Step 7: grep 扫描确认 `_format_search_results` 作用域内无废弃字段名**

Run Grep:
```
pattern: "chunk:\\d|chunk:[A-Z]|line:\\d|line:[A-Z]|matched_line|line_range|chunk_count"
path: nbrag/mcp_tools.py
```
重点看 L273-L414 区间无命中（`chunk_index` / `total_chunks` / `line_start` / `line_end` 是 canonical 名字，不算违规）。

- [ ] **Step 8: import 验证**

Run:
```powershell
$env:OPENBLAS_NUM_THREADS=1
D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import _format_search_results, nbrag_search, nbrag_search_only_bm25, nbrag_search_only_vector; print('import OK')"
```
Expected: `import OK`（不报错即可，真正的功能验证在 Task 10）

- [ ] **Step 9: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): XML format for _format_search_results (affects 3 search fns)"
```

## Global Constraints（适用于本 Task）

- **Python 解释器**：`D:/ProgramData/miniconda3/envs/py312/python.exe`
- **OpenBLAS 绕过**：import 前设 `$env:OPENBLAS_NUM_THREADS=1`
- **不改函数签名**：3 个 search 函数的公开签名（入参名、类型、默认值）不变。`_format_search_results` 加 `root_tag` 参数是内部函数，允许。
- **canonical handle 字段集**：`file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`
- **禁止变体**：`chunk:X/Y` / `line:N-M` / `chunk_index:X` / `total_chunks:Y`（key:value 形式也不要，改 XML 属性）
- **正文零转义**：`<content>` 内纯文本
- **不写正式测试**
- **使用 Task 2 的 helper**：`_meta_file_path(meta)` / `_meta_chunk_index(meta)`，不要重复映射逻辑
