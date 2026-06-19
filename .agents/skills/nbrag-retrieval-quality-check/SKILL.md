---
name: nbrag-retrieval-quality-check
description: Use when changing help text, result formatting, retrieval guidance, grep/raw/chunk outputs, or tool contracts and you need to verify AI-friendly returns and actionable fields with tests/ai_codes/result_check.py.
---

# nbrag Retrieval Quality Check

用这个 skill 验证 `nbrag` MCP 工具的**检索质量与返回契约**，重点不是速度，而是：

- AI 能不能看懂返回
- 返回里有没有可继续调用的关键字段
- 错误/无结果时是否给出合理调整方向
- `help` / `stats` / `search` / `grep` / `raw_file` 等工具是否仍然“AI 友好”

## 什么时候用

- 改了 `mcp_tools.py` 的返回文本
- 改了 `server.py` 的 docstring / 工具说明
- 改了 `help`、`skill`、`workflow` 文案
- 改了 `grep`、`find_files`、`get_raw_file`、`adjacent_chunks` 的输出结构
- 用户问“这个 MCP 现在到底对 AI 友不友好”

不要在只关心耗时变快还是变慢时用它；那种场景应改用 `nbrag-performance-check`。

## 核心脚本

运行：

```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/tests/ai_codes/result_check.py
```

脚本位置：
- `tests/ai_codes/result_check.py`

它会：
- 构造典型用户问题
- 直接调用 `nbrag.mcp_tools`
- 检查返回里是否包含 `file_path`、`doc_id`、`chunk`、`line_range`、`Possible adjustments` 等字段
- 输出 `passed / failed / total`
- 列出失败 case 名称，便于直接定位

## 你应该看什么

### 1. help / stats 是否建立正确心智模型

重点看：
- `nbrag_help()` 是否说明这是 Agentic RAG，而不是普通文件搜索
- `nbrag_stats()` 是否能帮助 AI 找到正确 `collection_name`
- 是否有过强、过死的流程提示，把 AI 束缚死

### 2. 检索结果是否可继续调用

重点字段：
- `file_path:`
- `doc_id:`
- `chunk:`
- `line:` / `line_range:`
- `matched_line:`
- `original_file:`

如果这些缺了，AI 往往没法顺利继续调下一个工具。

### 3. 失败分支是否足够友好

重点看：
- collection 不存在时，是否提示先确认 `collection_name`
- 路径错误时，是否明确要求“完整绝对路径”
- 无结果时，是否给出较软的调整方向，而不是僵硬命令

## 判断标准

### 好的返回

- 说明当前结果是什么
- 给出 AI 能复制的关键字段
- 不要求 AI 猜下一步参数
- 不强迫 AI 走固定流程
- 出错时给“Possible adjustments”而不是死命令

### 不好的返回

- 只有自然语言解释，没有结构字段
- 只有 chunk 内容，没有 `file_path/doc_id`
- 错误文案太泛，不知道怎么修正输入
- 帮助文案太死，像脚本模板而不是策略建议

## 建议流程

1. 跑 `result_check.py`
2. 看 `failed case`
3. 判断问题属于：
   - 缺字段
   - 字段命名不清
   - 错误提示太弱
   - 指导文案太死
4. 只做最小修复
5. 重新跑脚本，直到 `passed=... failed=0`

## 和 benchmark 的区别

- `benchmark.py` 回答：**快不快**
- `result_check.py` 回答：**AI 好不好用、返回对不对**

两个脚本通常要配合使用。

## 输出结论时建议

从 AI 视角总结：

- 哪些工具最适合作为入口
- 哪些工具返回字段最完整
- 哪些失败分支仍然会误导 AI
- 是否存在“太死的流程提示”

不要只说“脚本通过了”，而要说明：
- 通过说明了什么
- 是否还存在主观上的误导风险
