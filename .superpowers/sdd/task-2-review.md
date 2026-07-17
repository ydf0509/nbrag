# Task 2 Review — 加映射 helper + 重构错误 helper 为 XML error 格式

**Reviewer verdict date:** 2026-07-16
**Commit reviewed:** `207f4fb8f43efc863d3a46211c8b1d64f901df45`
**File modified:** `nbrag/mcp_tools.py`（仅此一个文件，符合全局约束）

---

## 1. Spec compliance（逐条对照 brief 与全局约束）

| 要求 | 状态 | 备注 |
|---|---|---|
| 只改 `nbrag/mcp_tools.py` | ✅ | diff 仅一个文件，1 file changed, 36 insertions(+), 15 deletions(-) |
| 新增 `_meta_file_path(meta: dict) -> str` | ✅ | L76-78，签名与 brief 完全一致，插在 `_bool_param` 之后 |
| 新增 `_meta_chunk_index(meta: dict) -> str` | ✅ | L81-83，签名与 brief 完全一致 |
| 现有 helper 签名不变 | ✅ | `_path_error(field_name: str) -> str` / `_collection_issue_text(collection_name: str, total: int) -> str` / `_collection_presence_issue_text(collection_name: str) -> str` / `_no_search_results_text(total: int) -> str` 均保持原签名 |
| `_path_error` 返回 `<error type="invalid_file_path" field="...">` | ✅ | L132-139，XML 格式正确 |
| `_collection_issue_text` 返回 `<error type="empty_collection">` 或空 | ✅（含合理偏离） | 见下方偏离说明 #1 |
| `_collection_presence_issue_text` 返回 `<error type="missing_collection">` | ✅（含合理偏离） | 见下方偏离说明 #2、#3 |
| `_no_search_results_text` 返回 `<error type="no_results" field="query">` | ✅ | L192-200，文案采用 brief 精简版（移除 "not a keyword list — use exact terms..." 一长句） |
| 错误 helper 均返回 `<error type="..." field="...">...</error>` | ✅ | 4 个 helper 的所有非空返回均为完整 XML |
| `get_stats()` 的 `collections` 是 dict，复用 `list(collections.keys())` | ✅ | 两个 helper 均用 dict-based 逻辑，未误用 brief 中的 list-comprehension 写法 |
| 保留 `_collection_presence_issue_text` 的 3 分支（missing/empty/ok） | ✅ | L165-189，info is None / `not docs and not chunks` / `return ""` 三分支完整保留 |
| 保留 `_collection_issue_text` 的 missing + empty 分支 | ✅ | L142-162，brief Step 3 注解明确要求保留，已照做 |
| 不写正式测试 | ✅ | 仅 Step 6 import 验证 |
| 不改调用点 | ✅ | 14 处调用点（L294 / L302-304 / L307 / L434 / L441 / L446 / L552 / L563-565 / L595 / L645 / L710 / L788 / L814 / L885-887）均未触碰，仍以 `if collection_issue: return collection_issue` 模式调用 |
| Python 解释器 `D:/ProgramData/miniconda3/envs/py312/python.exe` | ✅ | Step 6 验证使用该解释器 |

### 偏离说明（均已正当化）

**#1 — `_collection_issue_text` 保留 missing + empty 两分支**
brief Step 3 目标代码只展示 empty_collection 分支，但其注解明确要求"如果原函数还有'不存在'判断逻辑，保留该逻辑但把返回文本改成 `<error type="missing_collection">` 格式"。原函数确实有 missing 分支，implementer 保留并转 XML，符合 brief 注解。✅ 正当

**#2 — `_collection_presence_issue_text` 保留 3 分支而非无条件返回 missing_collection**
brief Step 4 目标代码无条件返回 missing_collection，但 5 处调用方依赖 `if collection_issue: return collection_issue` 的空字符串判定（后面接 "No ... matches" 兜底文案）。若按 brief 字面改写会让"存在且非空"场景错误返回 missing_collection 并吞掉兜底文案。全局约束明确要求保留 3 分支。✅ 正当

**#3 — `_collection_presence_issue_text` 复用 `list(collections.keys())` 而非 brief 中的 list-comprehension**
brief Step 4 目标代码 `[c.get("collection_name", ...) for c in stats.get("collections", [])]` 假设 `collections` 是 list of dicts，但实际 `get_stats()` 返回的是 dict。全局约束明确要求复用现有 `list(collections.keys())`。✅ 正当

**#4 — `_no_search_results_text` 文案精简**
按 brief 目标代码采用精简版，移除原散文中 "not a keyword list — use exact terms/article numbers/symbols from user wording or context" 一长句。implementer 在 Concerns #5 中明确标注，提示若下游发现 AI 对 bm25_query 构造有歧义，需在别处（如 SKILL.md）补回。✅ 正当，且已透明披露

---

## 2. Task quality（代码质量审查）

### XML 格式正确性 ✅
4 个 error helper 的所有非空返回均为完整、良构的 XML：
- `<error type="invalid_file_path" field="{field_name}">...</error>`
- `<error type="missing_collection" field="collection_name">...</error>`
- `<error type="empty_collection" field="collection_name">...</error>`
- `<error type="no_results" field="query">...</error>`

开闭标签匹配，属性值用 `\"` 转义，无断裂。

### f-string 一致性 ✅
所有 helper 采用统一的 multi-line f-string 拼接风格（每行一个 f-string，靠隐式字符串拼接）。与原代码风格一致。无断裂的 f-string、无遗漏的 `{}` 转义。

### 分支逻辑正确性 ✅
- `_collection_issue_text`：`total == 0` → 查 `get_stats()` → missing 或 empty → 否则 `""`。逻辑链完整。
- `_collection_presence_issue_text`：`info is None` → missing；`not docs and not chunks` → empty；否则 `""`。3 分支覆盖完整，`return ""` 在最后。
- 两个 helper 的 missing_collection 文案与 available collections 输出一致，便于下游 AI 解析。

### 风格一致性 ✅
- 新增 helper 的 docstring 风格（单行 `"""Map ..."""`）与现有 `_str_param` / `_int_param` / `_bool_param` 一致。
- 插入位置（`_bool_param` 之后、`_build_line_char_index` 之前）符合 brief "约 L74 后" 的要求。
- 两个新 helper 之间空两行，与文件其余顶层函数之间的空行风格一致。

### 潜在问题（非本 Task 引入，仅记录）

- **低** — `_collection_issue_text` 使用 `stats["collections"].keys()`（直接下标），而 `_collection_presence_issue_text` 使用 `stats.get("collections", {})`。两者对 `collections` key 缺失时的容错不同。但这是原代码就有的差异，本 Task 未引入，且 `get_stats()` 的契约保证 `collections` key 存在，不构成缺陷。
- **低** — `_no_search_results_text` 文案精简后，bm25_query 的用法说明变弱。implementer 已在 Concerns #5 中透明披露，建议下游 Task 在 SKILL.md 中确认是否需要补回。

### Step 6 验证 ✅
import 验证输出符合期望：包含 `<error type="invalid_file_path"`、`<error type="no_results"`、`D:/foo.py`、`3`。OpenBLAS 内存报错为环境问题（设 `OPENBLAS_NUM_THREADS=1` 绕过），与本 Task 改动无关。

---

## 3. Verdicts

- **Spec compliance**: ✅ — 所有 brief 要求与全局约束均满足；4 处偏离 brief 目标代码的行为均有 brief 注解或全局约束明确支持，且已在 report 的 Concerns 中透明披露。
- **Task quality**: **Approved** — XML 良构、f-string 一致、分支逻辑完整、调用点零改动、风格与现有代码统一。无阻塞性或需要修复的发现。

---

## 4. Summary for downstream tasks

- `_meta_file_path` / `_meta_chunk_index` 已就绪，下游 Task 可直接调用获取 canonical handle。
- 4 个 error helper 现在统一返回 `<error type="..." field="...">...</error>` XML，下游 AI 解析可依赖此格式。
- `_collection_issue_text` 与 `_collection_presence_issue_text` 仍可能返回 `""`（无问题）、`missing_collection`（不存在）、`empty_collection`（存在但空）三种之一，下游 Task 不可假定只返回单一类型。
- `_no_search_results_text` 的 bm25_query 说明被精简，若下游发现 AI 构造 bm25_query 有歧义，考虑在 SKILL.md 补回详细说明。
