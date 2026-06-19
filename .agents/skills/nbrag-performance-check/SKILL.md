---
name: nbrag-performance-check
description: Use when changing retrieval, caching, Chroma query flow, grep, find_files, or raw file reading and you need to verify whether nbrag MCP tool latency got faster or slower with tests/ai_codes/benchmark.py.
---

# nbrag Performance Check

用这个 skill 验证 `nbrag` MCP 工具的**性能变化**，尤其是检索、grep、文件发现、原文读取这几类调用是否变快或变慢。

## 什么时候用

- 改了 `retrieval.py`、`mcp_tools.py`、缓存逻辑、Chroma 查询链路后
- 改了 `search / grep / find_files / raw_file` 路径后
- 用户问“这个优化到底快了没有”
- 需要比较不同工具、不同 collection 的平均耗时

不要在只关心返回字段是否友好时用它；那种场景应改用 `nbrag-retrieval-quality-check`。

## 核心脚本

运行：

```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/tests/ai_codes/benchmark.py
```

脚本位置：
- `tests/ai_codes/benchmark.py`

它会：
- 直接调用 `nbrag.mcp_tools`
- 覆盖 `worker_rights`、`funboost`、`langchain_ai_codes_and_docs`
- 统计 `avg/min/max/rounds`
- 输出每个 MCP 函数的结果预览，方便顺手判断是否跑偏

## 怎么解读结果

重点看：

- `nbrag_search*`：通常受 embedding / rerank / 召回链路影响
- `nbrag_grep`：通常受 raw text cache / 原文扫描逻辑影响
- `nbrag_find_files`：通常受 metadata 获取和文档列表缓存影响
- `nbrag_get_raw_file` / `nbrag_get_file_chunks`：通常受本地缓存和文件读取路径影响

### 经验判断

- `0.000x ~ 0.02s`：基本是本地内存/轻量读取
- `0.02 ~ 0.2s`：本地逻辑可接受
- `0.2s+`：值得看是否有多余 IO、全量扫描、全量 metadata 拉取
- `0.6s+`：通常已经包含远程模型调用或较重的本地扫描
- `3s+`：通常是明显热点，优先排查

## 建议流程

1. 先跑一轮 benchmark，记录基线
2. 改代码
3. 再跑一轮 benchmark
4. 比较是否是：
   - 单点变快但别的工具变慢
   - 平均值变快但最大值抖动更大
   - 某个 collection 特别慢（常见于 `langchain`）
5. 如果是慢路径，继续追根因：
   - 网络模型链路
   - Chroma metadata/query
   - raw_files 扫描
   - 文档列表缓存

## 不要误判

- 不要只看 `avg`，也看 `max`
- 不要只看一个 collection，至少对比小库和大库
- 不要把首次冷启动和缓存命中混在一起解释
- `search_and_fetch` 比 `search` 慢不一定是坏事，可能只是多拿了原文证据

## 输出结论时建议

按这三类总结：

- 向量检索链路慢
- 本地扫描 / metadata 链路慢
- 本地缓存命中后已足够快

避免只说“快了/慢了”，而要指出：
- 哪个函数
- 哪个 collection
- 平均耗时
- 可能根因
