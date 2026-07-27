# `nbrag_read_more_original_text` 原文返回标签调整计划

## 目标

只调整当前 `nbrag_read_more_original_text` 工具的对外返回契约，消除该工具名称中的 `original_text` 与返回标签中的 `raw` 混用。

本次不扩展为全局术语迁移：不修改 `nbrag_search_and_fetch` 的自动摘录标签、不修改其他工具、不修改参数名、不修改内部 retrieval 实现、不修改 README、SKILL 或历史文档。

## 确定后的返回结构

```xml
<nbrag_read_more_original_text status="success" returned_original_text_count="1">
...
<nbrag_original_text>
file_path = ...
doc_id = ...
total_lines = ...
line_start = ...
line_end = ...

<nbrag_original_text_content>
...
</nbrag_original_text_content>
</nbrag_original_text>
</nbrag_read_more_original_text>
```

### 标签职责

- `<nbrag_original_text>`：一次按文件和行范围读取到的知识库保存原文。
- `<nbrag_original_text_content>`：该原文结果的实际文本内容。
- `returned_original_text_count`：返回的 `<nbrag_original_text>` 实体数量。

虽然 `text_content` 在自然语言上存在轻微重叠，但该命名与现有 `<nbrag_chunk_content>`、`<nbrag_definition_content>` 一致：父标签表示结果实体，子标签表示该实体的正文。它也能避免将 stored original text 误解为实时本地文件或低层 raw bytes。

## 仅修改范围

### 1. `nbrag/mcp_tools.py`

仅修改 `nbrag_read_more_original_text()` 的输出格式和该函数自身错误文案：

- [ ] 将装饰器从：

  ```python
  @_contract_tool("returned_raw_count", "nbrag_raw_content")
  ```

  改为：

  ```python
  @_contract_tool("returned_original_text_count", "nbrag_original_text_content")
  ```

- [ ] 将函数内的结果实体标签从 `<nbrag_raw_file>` 改为 `<nbrag_original_text>`。
- [ ] 将函数内的正文标签从 `<nbrag_raw_content>` 改为 `<nbrag_original_text_content>`。
- [ ] 将未找到错误消息从 `Raw file not found.` 改为 `Stored original text not found.`。
- [ ] 保持以下实现和对外 handles 不变：
  - 参数：`file_path`、`collection_name`、`line_start`、`line_end`；
  - 绝对路径校验；
  - 行号清洗；
  - `get_file_chunks(..., raw=True, ...)` 调用；
  - `file_path`、`doc_id`、`total_lines`、`line_start`、`line_end` 返回字段；
  - 函数名和根标签：`nbrag_read_more_original_text`。

### 2. `nbrag/server.py`

只修改 `nbrag_read_more_original_text()` 自己的 docstring / Field 描述中直接提到其返回标签或 raw file 的文字：

- [ ] 将 `<nbrag_raw_content>` 改为 `<nbrag_original_text_content>`。
- [ ] 将“raw file”这类表述改成“stored original text snapshot”。
- [ ] 保持参数、默认值和约 500 行的阅读策略不变。

### 3. 直接相关测试

只更新断言该工具自身返回协议的测试：

- [ ] `returned_raw_count` 改为 `returned_original_text_count`。
- [ ] `<nbrag_raw_file>` 改为 `<nbrag_original_text>`。
- [ ] `<nbrag_raw_content>` 改为 `<nbrag_original_text_content>`。
- [ ] `Raw file not found` 断言（如存在）改为 `Stored original text not found`。
- [ ] 不修改 `search_and_fetch` 的 `<nbrag_raw_excerpt>` / `<nbrag_raw_content>` 测试；那些属于另一个工具的现有契约。

## 明确不修改

- `nbrag_search_and_fetch`、`nbrag_grep`、chunk 工具及它们的 XML 标签。
- `fetch_top_n_raw`、`fetch_context_chars`、`match_context_chars` 等参数。
- `retrieval.py` 中的 `raw=True`、raw cache、raw files、`get_raw_file()` 兼容 API 和内部变量。
- `nbrag/skills/nbrag-workflow/SKILL.md`、`.agents/skills/`、`README.md`、`README.zh-CN.md`。
- 历史计划、spec、审计文档。

## 验证

- [ ] 使用项目指定解释器运行直接相关测试。
- [ ] 重启 MCP HTTP 服务。
- [ ] 调用 `nbrag_read_more_original_text`，确认：
  - 根标签仍为 `<nbrag_read_more_original_text>`；
  - 计数字段为 `returned_original_text_count`；
  - 返回实体为 `<nbrag_original_text>`；
  - 正文标签为 `<nbrag_original_text_content>`；
  - handles 未变。
- [ ] 用无效 `file_path` 调用，确认错误根标签不变且消息为 `Stored original text not found.`。
- [ ] 调用 `nbrag_search_and_fetch`，确认其现有 raw excerpt 返回完全未受影响。

## 完成标准

`nbrag_read_more_original_text` 的工具名、描述、成功响应和错误消息均使用 `original text` 术语；其他工具、参数和内部实现不因本次最小改动发生变化。
