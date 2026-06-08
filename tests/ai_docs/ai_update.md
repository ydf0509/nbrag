# AI 重大更新记录

## 2026-06-08: batch_ingest 批量写入优化（delete_first=True）

**改动范围**：core.py

**核心变化**：
- `batch_ingest(delete_first=True)` 新增 `_batch_write_to_db` 批量写入路径
- 旧方式：每个文件 3 次 SQLite 操作（查旧 + 删旧 + upsert），N 文件 = 3N 次
- 新方式：跳过查旧/删旧（collection 已清空），收集所有 chunks 后一次性 upsert
- `delete_first=False`（增量导入）仍使用逐文件 `_write_to_db`，不受影响

**新增函数**：
- `_batch_write_to_db()` — 批量收集 + 缓存原文 + 一次性 upsert

---

## 2026-06-08: find_symbol_definition 性能优化 —— Symbol 索引

**改动范围**：core.py, AGENTS.md

**核心变化**：
- `find_symbol_definition()` 从全量 AST 扫描改为 **Symbol 索引查表**
- 新增 `symbol_index/` 持久化目录，在 `batch_ingest()` 完成后自动构建
- 索引格式：`{simple_name: [{doc_id, filename, source, type, qualified, line_start, line_end, sig, methods}]}`
- 查询时先查索引 O(1)，只读取匹配文件获取定义文本，索引不存在时回退到旧全量扫描

**新增函数**：
- `build_symbol_index()` — 扫描 .py 文件 AST，构建并持久化索引
- `_load_symbol_index()` — 从磁盘加载（带内存缓存）
- `_query_symbol_index()` — 按 name/qualified/suffix 三种方式匹配
- `invalidate_symbol_cache()` — 清除缓存 + 磁盘文件
- `_find_definition_via_index()` — 索引快速路径
- `_find_definition_full_scan()` — 全量扫描回退路径

**生命周期挂接**：
- `batch_ingest()` 完成后自动构建 Symbol 索引
- `ingest_file()` 写入后清除内存缓存
- `delete_document()` / `delete_collection()` 清除 Symbol 缓存 + 磁盘索引

**性能测试结果（langchain_ai_codes_and_docs, 4801 文件, 3144 .py）**：

| 符号 | 旧（全量 AST） | 新（索引） | 加速比 |
|------|--------------|-----------|--------|
| search（找到） | 4.73s | 0.002s | **2365x** |
| embed（找到） | 1.98s | 0.002s | **990x** |
| BrokerEnum（0 结果） | 5.74s | 0.49s | 12x |
| NONEXISTENT（最差） | 4.25s | 0.46s | 9x |

索引构建一次性开销：3.62s（21084 symbols），仅在 ingest 时执行。
架构从"三存储"升级为"四存储"（ChromaDB + raw_files + bm25_index + symbol_index）。

---

## 2026-06-07: 打工人法律百科知识库（worker_rights）

**改动范围**：scripts/ingest_ex3_worker_rights/（新增目录）

**核心变化**：
- 创建"打工人法律百科"知识库，涵盖 18 部劳动/社保/税务法律法规
- 板块覆盖：劳动合同、工资报酬、休假、五险一金、工伤、女职工保护、职业病防治、个人所得税、劳动争议仲裁
- 所有法律从政府官方网站抓取，清洗为 .md 格式
- 导入结果：18 文件 / 111 chunks / 108,397 字符 / 17 秒

**MCP 测试结果**（worker_rights 知识库）：
- 语义搜索"试用期最长几个月" → score 0.94，命中劳动法第21条+劳动合同法第19条
- 语义搜索"工作满10年几天年假" → score 0.90，命中带薪年休假条例第3条
- 语义搜索"周末加班200%" → score 0.50，命中劳动法第44条
- 语义搜索"房贷利息抵扣" → score 0.64，命中专项附加扣除第14条
- 语义搜索"上班路上出车祸算工伤" → score 0.91，命中工伤保险条例第14条(六)

**文件清单**（18 部法律法规）：
- 劳动法、劳动合同法、劳动合同法实施条例
- 社会保险法、住房公积金管理条例、工伤保险条例、失业保险条例
- 个人所得税法、个人所得税法实施条例、专项附加扣除暂行办法
- 带薪年休假条例、带薪年休假实施办法、工资支付暂行规定
- 女职工劳动保护特别规定、职业病防治法
- 劳动争议调解仲裁法、劳动保障监察条例、劳动争议司法解释一

---

## 2026-06-07: README.md + AGENTS.md 通用性完善

**改动范围**：README.md, AGENTS.md

**核心变化**：
- **README.md**：
  - 12 工具表格更新：去掉"取源码"等代码专属描述，改为通用表述
  - 新增"通用知识场景"工作流（法律/医学/技术手册）
  - 导入示例增加法律文本示例代码和 scripts/ 目录引导
  - AST scope 注入说明明确"仅 .py 文件"，补充非 Python 文件处理方式
  - BM25 分词器说明补充对非代码文本的适用性
- **AGENTS.md**：
  - 项目概览改为"通用知识库 Agentic RAG MCP Server — 不限于编程"
  - MCP docstring 规范从"必须用英文"改为"中英混合 + 关键概念双语映射"
  - 新增"MCP tool docstring 是 AI 理解的第一道防线"原则
  - AST 作用域注入标注"仅 Python 文件"，补充非 .py 文件的处理和引导
  - 新增"内容类型与功能对照"表格（.py vs .md/.txt 的功能差异）
  - 文件组织补充 ingest_ex1/、ingest_ex2_marriage_law/ 示例目录

---

## 2026-06-07: 婚姻家庭法 ingest + MCP 测试

**改动范围**：scripts/ingest_ex2_marriage_law/

**核心变化**：
- 新增 5 个婚姻家庭法 .md 文件（民法典第五编、司法解释一/二、发布会背景、记者问答）
- 新增 `ingest_marriage_law.py` 导入脚本
- MCP 实测结果（marriage_law 知识库，27 chunks）：
  - 语义搜索"父母为子女婚后买房" → score 0.991，精准命中典型案例
  - grep"直播.*打赏" → 精准命中司法解释二第6条
  - 语义搜索"离婚冷静期" → score 0.036（俗称 vs 法律原文差距大）
  - grep"三十日内.*撤回" → 精准命中第1077条
  - 语义搜索"抢夺藏匿子女" → score 0.869，命中条文+案例

---

## 2026-06-07: 非编程文科知识测试（民法典）+ MCP docstring 强化

**改动范围**：server.py, scripts/ingest_ex1/

**核心变化**：
- **MCP tool docstring 强化**：不依赖 SKILL.md，让 MCP tool 的 docstring 本身就足够 AI 正确使用
  - `nbrag_search`: 加 IMPORTANT 提醒查 nbrag_stats、知识库=collection 映射示例、简化 follow-up 工具说明
  - `nbrag_stats`: 强化入口引导 "CALL THIS FIRST"
  - `nbrag_search_and_fetch`: 加与 nbrag_search 的区别说明
- **民法典测试数据**：从司法部官网抓取《中华人民共和国民法典》全文（~112KB, 1260条），按 7 编拆分为独立 .md 文件
- **MCP 工具实测结果**（civil_code 知识库，181 chunks）：
  - `nbrag_search`：语义搜索"离婚需要什么条件" → 精准命中第四章离婚（第1076-1092条）
  - `nbrag_grep`："建筑物中抛掷" → 精准命中第1254条（高空抛物）
  - `nbrag_find_definition`："物权" → regex fallback 找到第二编物权开头（类型为 unknown）
  - `nbrag_search_and_fetch`："个人信息保护" → 命中第六章全文并自动取回原文
  - BM25 对法律文本效果与纯向量接近（专业术语嵌入质量高）

---

## 2026-06-07: BM25 + RRF 混合检索

**改动范围**：core.py, server.py, pyproject.toml, README.md, SKILL.md, AGENTS.md

**核心变化**：
- `search()` 从纯 Vector → **Vector + BM25 → RRF 融合 → Rerank** 三层混合检索
- 使用 `bm25s` 库（100-500x faster than rank_bm25），索引持久化到 `rag_db/bm25_index/`
- RRF 融合 k=60（SIGIR 2009 标准值），只看排名不看分数
- 代码感知分词器：拆 camelCase/snake_case，去 chunk header
- MCP 工具 `nbrag_search` 新增 `use_bm25` 参数（默认 True）
- 双存储 → 三存储（ChromaDB + raw_files + bm25_index）

**新增函数**：
- `_preprocess_for_bm25()` — 代码感知预处理
- `build_bm25_index()` — 构建并持久化 BM25 索引
- `_load_bm25_index()` — 从磁盘加载 BM25 索引
- `_bm25_search()` — BM25 检索
- `_rrf_fusion()` — Reciprocal Rank Fusion
- `invalidate_bm25_cache()` — 清除 BM25 缓存

**生命周期挂接**：
- `batch_ingest()` 完成后自动构建 BM25 索引
- `ingest_file()` 写入后清除内存缓存（下次搜索时自动重建）
- `delete_document()` / `delete_collection()` 清除 BM25 缓存 + 磁盘索引

---

## 2026-06-07: pyproject.toml 动态版本 + 发布脚本修复

**改动范围**：pyproject.toml, nbrag/__init__.py, pub_pypi_nbrag.py

**核心变化**：
- `version = "0.3.0"` → `dynamic = ["version"]` + `[tool.hatch.version]`，版本号从 `__init__.py` 动态读取
- `license = "MIT"` → `license = {text = "MIT"}`（避免 PEP 639 `License-Expression` 字段导致旧 twine 报错）
- `pub_pypi_nbrag.py`：`os.system("python ...")` → `os.system(f'"{sys.executable}" ...')`，确保用正确的 Python 解释器
