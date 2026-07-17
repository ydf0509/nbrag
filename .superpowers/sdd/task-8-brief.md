# Task 8: 重构 3 个清单类函数（废弃 `chunk_count`）

**Files:**
- Modify: `nbrag/mcp_tools.py:646-675`（`nbrag_find_files`）+ `L892-961`（`nbrag_list` + `nbrag_stats`）

## 当前代码结构

### `nbrag_find_files`（L646-675）
- `find_files()` 返回 list，item key：`filename` / `doc_id` / `chunk_count` / `total_chunks` / `match` / `source`(或 `file_path`)
- 当前用 `chunk_count` 字段名 → 废弃，统一 `total_chunks`

### `nbrag_list`（L892-915）
- `list_documents()` 返回 dict `doc_id → row`，row key：`filename` / `chunk_count` / `total_chunks` / `source`
- 当前用 `chunk_count` 字段名 → 废弃，统一 `total_chunks`

### `nbrag_stats`（L918-961）
- `get_stats()` 返回 dict，`collections` 是 dict `name → info`
- info key：`docs`(或 `doc_count`) / `chunks`(或 `chunk_count`) / `display_name` / `description` / `aliases`(list) / `tags`(list) / `chunk_size` / `chunk_overlap` / `last_ingested_at`
- 当前有多行 routing 散文（前后各 2-3 句）

## 目标 XML 格式

### `nbrag_find_files`

```xml
<nbrag_find_files>
Follow-up handle in <file>: file_path.

<files>
<file file_path="D:/codes/foo.py" doc_id="abc123" filename="foo.py" total_chunks="10" match="foo"/>
</files>

</nbrag_find_files>
```

- 单条标签自闭合 `<file ... />`
- `total_chunks` 取 `item.get("total_chunks", item.get("chunk_count", "?"))`（优先 total_chunks，fallback chunk_count）
- 无结果 → `<error type="no_results" field="pattern">` XML

### `nbrag_list`

```xml
<nbrag_list collection_name="my_kb" offset="0" limit="100">
Follow-up handles in <document>: doc_id, file_path.

<documents>
<document doc_id="abc123" file_path="D:/codes/foo.py" filename="foo.py" total_chunks="10"/>
</documents>

</nbrag_list>
```

- 单条标签自闭合
- `total_chunks` 取 `row.get("total_chunks", row.get("chunk_count", "?"))`
- 无结果 → `<error type="no_results" field="collection_name">` XML

### `nbrag_stats`

```xml
<nbrag_stats>
Use collection_name exactly as shown below when calling retrieval tools.

<collections>
<collection collection_name="my_kb" docs="50" chunks="1200" display_name="My Knowledge Base" description="Internal policies." aliases="policies, manuals" tags="internal, policy" chunk_size="1000" chunk_overlap="150" last_ingested_at="2026-07-15"/>
</collections>

After choosing collection_name, continue with nbrag_search_and_fetch for most questions.

</nbrag_stats>
```

- 单条标签自闭合
- 变长可选字段（`display_name`/`description`/`aliases`/`tags`/`chunk_size`/`chunk_overlap`/`last_ingested_at`）有则写、无则省略
- `aliases` / `tags` 是 list → 转成逗号分隔字符串放属性
- 保留 1 句 routing 前（`Use collection_name exactly as shown below...`）+ 1 句 routing 后（`After choosing collection_name, continue with nbrag_search_and_fetch for most questions.`）
- 删除其他多行 routing 散文（"If this is the first nbrag call..." / "This tool resolves..." / "Use nbrag_search_and_fetch() for most..." 等）
- 无 collections → `<error type="no_results" field="collection_name">` XML

## Steps

- [ ] **Step 1: 重写 `nbrag_find_files`（L646-675）**

保留 L647-649（param normalization + `find_files` 调用）不变。

改写 L650-675：
- 无结果 → `<error type="no_results" field="pattern">` XML
- header → `<nbrag_find_files>` + handle 提醒
- 每个 item → `<file file_path="..." doc_id="..." filename="..." total_chunks="..." match="..."/>`
- `file_path` 取 `item.get("source", item.get("file_path", "?"))`

- [ ] **Step 2: 重写 `nbrag_list`（L892-915）**

保留 L893-895 不变。

改写 L896-915：
- 无结果 → `<error type="no_results" field="collection_name">` XML
- header → `<nbrag_list collection_name="..." offset="..." limit="...">` + handle 提醒
- 每个 `doc_id, row` → `<document doc_id="..." file_path="..." filename="..." total_chunks="..."/>`

- [ ] **Step 3: 重写 `nbrag_stats`（L918-961）**

保留 L919-920（`get_stats` 调用 + `collections` 提取）不变。

改写 L921-961：
- 无 collections → `<error type="no_results" field="collection_name">` XML
- 1 句 routing 前 + `<collections>` + 每个 collection 自闭合标签 + `</collections>` + 1 句 routing 后
- 每个 collection：`<collection collection_name="..." docs="..." chunks="..." .../>`，可选字段有则写

- [ ] **Step 4: grep 扫描确认 `chunk_count` 在 mcp_tools.py 里无残留**

Run Grep:
```
pattern: "chunk_count"
path: nbrag/mcp_tools.py
```
Expected: 0 命中（如果底层 `get_stats` 返回的 info 里有 `chunk_count` key，那是在读取时的 fallback 逻辑，不算违规——检查是否仅在 `.get("chunk_count", ...)` fallback 中出现）

- [ ] **Step 5: import 验证**

```powershell
$env:OPENBLAS_NUM_THREADS=1
D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import nbrag_find_files, nbrag_list, nbrag_stats; print('import OK')"
```

- [ ] **Step 6: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): XML format for 3 listing functions, deprecate chunk_count"
```

## Global Constraints

- **Python 解释器**：`D:/ProgramData/miniconda3/envs/py312/python.exe`，`$env:OPENBLAS_NUM_THREADS=1`
- **不改函数签名**
- **canonical handle 字段集**：`file_path` / `doc_id` / `total_chunks`
- **禁止变体**：`chunk_count`（作为输出字段名；在 `.get()` fallback 里读取底层值不算违规）
- **正文零转义**（清单类无正文，自闭合标签）
- **不写正式测试**
