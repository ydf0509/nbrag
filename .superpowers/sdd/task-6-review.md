# Task 6 Review: 重构 `nbrag_find_definition` 为 XML 格式

## 结论

- **Spec**: ✅
- **Quality**: Approved
- **Summary**: 实现严格遵循 brief，XML 结构、canonical handles、symbol_type 归一、methods_summary 省略规则、no-results error、regex fallback 散文警告全部符合；函数签名未改，无残留 key:value 散文，无测试。

## 逐项核对

| 约束 | 结果 | 证据 |
| --- | --- | --- |
| 仅修改 `nbrag_find_definition` | ✅ | diff 仅触及 `nbrag/mcp_tools.py` L596-643；其余函数未动 |
| 函数签名未改 | ✅ | `inspect.signature` 输出 `(symbol: 'str', collection_name: 'str', max_results: 'int' = 3) -> 'str'`，与原签名一致 |
| `symbol_type` ∈ {class, function, method, regex_fallback} | ✅ | L611 `python_symbol_types = {"class", "function", "method"}`；L629 `display_symbol_type = symbol_type if ... else "regex_fallback"` |
| `<methods_summary>` 子元素，空则省略 | ✅ | L635-638 `if methods_summary:` 包裹 `<methods_summary>...</methods_summary>` |
| `<content>` 包裹定义正文 | ✅ | L632-634 `<content>` / `definition` / `</content>` |
| 无结果 → `<error type="no_results" field="symbol">` | ✅ | L603-609，"Recovery" 措辞符合 brief |
| regex fallback 警告为散文行（无 XML 标签），位于 `<definitions>` 前 | ✅ | L616-619：`has_non_python_fallback and not has_python_definition` 时追加散文 + 空行，随后才 `lines.append('<definitions>')` |
| canonical handles: file_path/doc_id/line_start/line_end | ✅ | L631 `<definition ... file_path="..." doc_id="..." line_start="..." line_end="...">`，四字段齐全作为属性 |
| 无 `line:N-M` / `doc_id:xxx` 残留 | ✅ | grep 在 L592-643 范围内零匹配；其余命中（L227/L673/L700/L706/L737/L744/L775/L781/L807/L808/L836）均属其他未重构函数，不在 Task 6 范围 |
| 未写测试 | ✅ | report 确认无测试；diff 无测试文件 |
| header 散文已删除 | ✅ | 原 `definitions: N` / "Returned handle fields..." 已替换为 `<nbrag_find_definition>` 根 + 单行 handles 提示 |
| import 验证 | ✅ | `from nbrag.mcp_tools import nbrag_find_definition` exit 0 |

## XML 结构核对

输出形态（以有结果路径为例）：

```
<nbrag_find_definition>
Follow-up handles in <definition>: file_path, doc_id, line_start, line_end.

[Only regex fallback ... 散文（可选）]

<definitions>
<definition symbol_type="..." qualified_name="..." file_path="..." doc_id="..." line_start="..." line_end="...">
<content>
...
</content>
<methods_summary>      ← 空则省略
...
</methods_summary>
</definition>
</definitions>

</nbrag_find_definition>
```

- 根元素 `<nbrag_find_definition>` 闭合 ✅
- `<definitions>` 容器闭合 ✅
- 每条 `<definition>` 闭合 ✅
- `<content>` / `<methods_summary>` 均成对闭合 ✅
- 所有属性值双引号包裹 ✅

## 观察（非阻断）

1. **散文行中的 `<definition>` 字面量**：L615 prose 行 `Follow-up handles in <definition>: ...` 含字面 `<definition>`，严格 XML 解析器会将其误判为开始标签。此为 brief 明确指定的模式，且与已重构函数（`nbrag_search` 用 `<hit>`、`nbrag_grep` 用 `<match>`）一致，属于面向 AI 的伪 XML 约定，非实现缺陷。
2. **`qualified_name` 回退**：L622 `r.get("qualified_name") or symbol`，当后端未返回 `qualified_name` 时回退到入参 `symbol`，符合 brief Step 1 代码示例。
3. **`source` → `file_path` 映射**：L623 `file_path = str(r.get("source", "?"))`，正确处理后端 `source` 字段到 canonical handle `file_path` 的命名转换。

## 结论

实现与 brief 完全对齐，无超额改动，无回归风险。Approved。
