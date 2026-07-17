# Task 7: 重构 4 个 chunk 视图函数

**Files:**
- Modify: `nbrag/mcp_tools.py:678-812`（`nbrag_get_adjacent_chunks` / `nbrag_get_file_chunks` / `nbrag_get_chunks_by_lines` / `nbrag_get_raw_file`）

**Interfaces:**
- Consumes: Task 2 的 `_meta_file_path(meta)` / `_meta_chunk_index(meta)` / `_path_error` / `_collection_presence_issue_text`
- Produces: 4 个函数分别返回 `<nbrag_get_*>` XML，`<chunk>` 用 canonical handle 属性

## 当前代码结构

4 个函数模式一致：调底层 `get_context_chunks` 或 `get_file_chunks` → 拿 `data` dict → 遍历 `chunks` 列表 → 格式化输出。

底层 `data` dict 的 key：`found` / `chunks` / `source`(=file_path) / `total_chunks` / `total_lines` / `filename` / `doc_id` / `line_start` / `line_end` / `start_chunk` / `end_chunk` / `content` / `error` / `message`

底层 `chunk` dict 的 key：`index` / `line_start` / `line_end` / `scope` / `content`

当前格式用废弃字段名：`chunk:X` / `line:N-M` / `original_file` / `line_range: line:N-M` / `doc_id:xxx`

## 目标 XML 格式

### `nbrag_get_file_chunks`（分页）

```xml
<nbrag_get_file_chunks file_path="..." doc_id="..." total_chunks="10" total_lines="200" start_chunk="0" max_chunks="10" has_more="false">
Follow-up handles in <chunk>: chunk_index, line_start, line_end.

<chunks>
<chunk chunk_index="0" total_chunks="10" line_start="1" line_end="28" scope="module">
<content>...</content>
</chunk>
</chunks>

</nbrag_get_file_chunks>
```

- `has_more` = `end_chunk < total_chunks - 1`（`end_chunk` 从 `data.get('end_chunk')` 取，`total_chunks` 从 `data.get('total_chunks')` 取）
- `scope` 为空时省略

### `nbrag_get_adjacent_chunks`（window 扩展）

```xml
<nbrag_get_adjacent_chunks file_path="..." doc_id="..." total_chunks="10" window="3" anchor_chunk_index="5">
Follow-up handles in <chunk>: chunk_index, line_start, line_end.

<chunks>
<chunk chunk_index="2" total_chunks="10" line_start="..." line_end="..." scope="...">
<content>...</content>
</chunk>
</chunks>

</nbrag_get_adjacent_chunks>
```

- `anchor_chunk_index` = 入参的 `chunk_index`
- `file_path` = `data.get('source', '?')`

### `nbrag_get_chunks_by_lines`（按行范围查 chunk）

```xml
<nbrag_get_chunks_by_lines doc_id="..." file_path="..." total_chunks="10" requested_line_start="15" requested_line_end="40">
Follow-up handles in <chunk>: chunk_index, line_start, line_end.

<chunks>
<chunk chunk_index="3" total_chunks="10" line_start="15" line_end="28" scope="...">
<content>...</content>
</chunk>
</chunks>

</nbrag_get_chunks_by_lines>
```

- `requested_line_start` / `requested_line_end` = 入参的 `line_start` / `line_end`

### `nbrag_get_raw_file`（无 chunk 结构，纯原文）

```xml
<nbrag_get_raw_file file_path="..." doc_id="..." total_lines="200" line_start="1" line_end="200">
<content>
... 原始文件内容，原样无转义 ...
</content>

</nbrag_get_raw_file>
```

- 没有 `<chunks>` 集合标签，直接 `<content>` 子元素
- `line_start`/`line_end` 放根属性

### 错误返回

所有 4 个函数的 "not found" 错误改成 `<error type="not_found" field="...">` XML：

```xml
<error type="not_found" field="doc_id">
No adjacent chunks found. Check that doc_id is valid and chunk_index came from a search result.
Recovery: ...
</error>
```

## Steps

- [ ] **Step 1: 重写 `nbrag_get_adjacent_chunks`（L678-709）**

保留 L679-681（param normalization + `get_context_chunks` 调用）不变。

改写 L682-709：
- not found → `<error type="not_found" field="doc_id">` XML
- header → `<nbrag_get_adjacent_chunks file_path="..." doc_id="..." total_chunks="..." window="..." anchor_chunk_index="...">` + handle 提醒
- 每个 chunk → `<chunk chunk_index="..." total_chunks="..." line_start="..." line_end="..." scope="..."><content>...</content></chunk>`
- `chunk_index` 用 `_meta_chunk_index(chunk)`，`file_path` 用 `str(data.get('source', '?'))`

- [ ] **Step 2: 重写 `nbrag_get_file_chunks`（L712-750）**

保留 L713-718 不变。

改写 L719-750：
- not found → `<error type="not_found" field="file_path">` XML
- `has_more` 计算：`str(data.get('end_chunk', 0) < data.get('total_chunks', 0) - 1).lower()`
- header → `<nbrag_get_file_chunks file_path="..." doc_id="..." total_chunks="..." total_lines="..." start_chunk="..." max_chunks="..." has_more="...">` + handle 提醒
- 每个 chunk → `<chunk chunk_index="..." total_chunks="..." line_start="..." line_end="..." scope="..."><content>...</content></chunk>`

- [ ] **Step 3: 重写 `nbrag_get_chunks_by_lines`（L753-787）**

保留 L754-756 不变。

改写 L757-787：
- not found → `<error type="not_found" field="doc_id">` XML
- header → `<nbrag_get_chunks_by_lines doc_id="..." file_path="..." total_chunks="..." requested_line_start="..." requested_line_end="...">` + handle 提醒
- 每个 chunk → 同上格式

- [ ] **Step 4: 重写 `nbrag_get_raw_file`（L790-812）**

保留 L791-796 不变。

改写 L797-812：
- not found → `<error type="not_found" field="file_path">` XML
- header → `<nbrag_get_raw_file file_path="..." doc_id="..." total_lines="..." line_start="..." line_end="...">`
- 直接 `<content>` 子元素放 `data.get("content", "")`
- 无 `<chunks>` 集合标签

- [ ] **Step 5: grep 扫描确认 L678-L813 无废弃字段名**

Run Grep:
```
pattern: "chunk:\\d|chunk:[A-Z]|line:\\d|line:[A-Z]|original_file|line_range"
path: nbrag/mcp_tools.py
```
重点看该区间无命中（`_merge_line_ranges` 函数名/调用不算违规）。

- [ ] **Step 6: import 验证**

```powershell
$env:OPENBLAS_NUM_THREADS=1
D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import nbrag_get_adjacent_chunks, nbrag_get_file_chunks, nbrag_get_chunks_by_lines, nbrag_get_raw_file; print('import OK')"
```

- [ ] **Step 7: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): XML format for 4 chunk view functions"
```

## Global Constraints

- **Python 解释器**：`D:/ProgramData/miniconda3/envs/py312/python.exe`，`$env:OPENBLAS_NUM_THREADS=1`
- **不改函数签名**
- **canonical handle 字段集**：`file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`
- **禁止变体**：`chunk:X` / `line:N-M` / `original_file` / `line_range: line:N-M` / `doc_id:xxx`
- **正文零转义**
- **使用 Task 2 helper**：`_meta_chunk_index(chunk)` for chunk 序号
- **不写正式测试**
