# Task 1: 清理 `server.py` 文案 + 补 boundary case 说明

**Files:**
- Modify: `nbrag/server.py`（Field description 和 docstring，约 L44-L428）

**Interfaces:**
- Consumes: spec 里定义的 canonical 字段名 + boundary case 模板
- Produces: `server.py` 里所有 Field description 无废弃字段名；`filter_file_path` / `start_chunk` 的 Field description 补值兼容说明

**背景**：当前 `server.py` 的 Field description 里提到 `chunk:X/Y` / `line:N-M` / `matched_line` 等废弃形式，和即将 XML 化的返回不一致。先清理文案，避免 AI 看到过时描述。

## Steps

- [ ] **Step 1: 读 `server.py` 找出所有废弃字段名引用**

用 Grep 扫 `server.py` 里的废弃字段名：
```
pattern: "chunk:\\d|line:\\d|matched_line|line_range|chunk_count|chunk_id|start_chunk"
path: nbrag/server.py
output_mode: content, -n=true
```
记录所有命中行号。

- [ ] **Step 2: 清理 Field description 里的废弃字段名**

逐个 Edit 命中行，把废弃字段名改成 canonical 形式：
- `chunk:X/Y` → `chunk_index + total_chunks`
- `line:N-M` → `line_start + line_end`
- `matched_line` → `line_start == line_end`
- `line_range` → `line_start + line_end`
- `chunk_count` → `total_chunks`

注意：`start_chunk` 是 `nbrag_get_file_chunks` 的合法入参名，保留不改（但 Step 4 要给它补值兼容说明）。

- [ ] **Step 3: 给 `filter_file_path` 的 Field description 补值兼容说明**

找到 `filter_file_path` 的 Field description（在 `nbrag_search` / `nbrag_search_and_fetch` / `nbrag_grep` 等函数的入参定义处），追加一句：
```
Value comes from the file_path handle returned by nbrag tools.
```

- [ ] **Step 4: 给 `start_chunk` 的 Field description 补值兼容说明**

找到 `nbrag_get_file_chunks` 的 `start_chunk` 入参 Field description，追加：
```
0-based chunk index; same value space as the chunk_index handle, but used as a pagination cursor (semantic: 'start browsing from chunk N').
```

- [ ] **Step 5: grep 扫描确认 `server.py` 无废弃字段名残留**

Run:
```
pattern: "chunk:\\d|line:\\d|matched_line|line_range|chunk_count"
path: nbrag/server.py
```
Expected: 0 命中（`start_chunk` 作为合法入参名保留，不算违规）

- [ ] **Step 6: Commit**

```bash
git add nbrag/server.py
git commit -m "refactor(server): clean deprecated field names from Field descriptions"
```

## Global Constraints（适用于本 Task）

- **Python 解释器**：`D:/ProgramData/miniconda3/envs/py312/python.exe`（conda py312 环境）
- **不改函数签名**：入参名、类型、默认值保持不变
- **canonical handle 字段集**（跨函数强制一致）：`file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`
- **禁止变体**（必须废弃）：`chunk:X/Y` / `line:N-M` / `matched_line` / `line_range` / `chunk_count` / `chunk_id`（暴露给 AI）/ `index`（暴露给 AI）
- **不写正式测试**：用户明确说不用管测试断言
- **commit 规则**：按 plan 的 commit message 格式，本 Task 完成后 commit
