# GitHub 项目导入功能 Spec

## Why
用户经常需要把 GitHub 上的开源项目导入到 nbrag 知识库中检索。目前需要手动 clone、再手动调 batch_ingest，流程繁琐。提供一个函数一键下载 GitHub 项目 ZIP 并导入。

## What Changes
- 在 `brag/contrib/ingest_github_proj.py` 中新增 `ingest_github_proj()` 函数
- 函数接收 GitHub URL，下载 ZIP，解压到本地临时目录，然后调用 `batch_ingest()` 导入
- 不注册为 MCP tool，仅作为 Python 函数供脚本调用

## Impact
- Affected specs: 无
- Affected code: `brag/contrib/ingest_github_proj.py`（新建函数）、`brag/ingest.py`（无改动，仅复用）

## ADDED Requirements

### Requirement: 下载 GitHub 项目 ZIP
系统 SHALL 根据 GitHub URL 构造 `https://github.com/{owner}/{repo}/archive/refs/heads/main.zip` 下载链接，下载项目 ZIP 到本地临时目录。

#### Scenario: 正常下载
- **WHEN** 调用 `ingest_github_proj("https://github.com/modelcontextprotocol/servers", collection_name="servers")`
- **THEN** 下载 `servers-main.zip` 到临时目录，解压到同目录下的 `servers-main/` 文件夹

#### Scenario: URL 带尾部斜杠
- **WHEN** 调用 `ingest_github_proj("https://github.com/modelcontextprotocol/servers/", collection_name="servers")`
- **THEN** 自动去除尾部斜杠，正常处理

#### Scenario: URL 包含 tree/branch 路径
- **WHEN** 调用 `ingest_github_proj("https://github.com/owner/repo/tree/dev", collection_name="repo")`
- **THEN** 提取 owner/repo，忽略 /tree/dev 部分

### Requirement: 调用 batch_ingest 导入
系统 SHALL 下载解压后调用 `batch_ingest()` 导入项目代码。

#### Scenario: 导入代码文件
- **WHEN** 下载解压完成，`file_extensions` 指定为 `[".py", ".md"]`
- **THEN** 调用 `batch_ingest(paths=[解压目录], collection_name=..., file_extensions=[".py", ".md", ...], excluded_paths=[解压目录/.git])`，`.git` 目录自动排除

#### Scenario: 自动扩展常见文档类型
- **WHEN** 用户传入 `file_extensions=[".py"]`
- **THEN** 自动追加 `README.md`、`LICENSE`、`CONTRIBUTING.md` 等常见文档文件名到扫描范围（通过 `file_extensions` 扩展 `[".md", ".txt", ".rst"]` 等文档后缀）

### Requirement: 临时文件保留
系统 SHALL 下载和解压后保留临时文件，不自动删除。

#### Scenario: 保留下载文件
- **WHEN** ingest 完成后
- **THEN** ZIP 文件和解压目录保留在临时目录中，打印路径方便用户后续查看

### Requirement: 错误处理
系统 SHALL 在路径不存在或下载失败时直接抛出异常，不捕获吞噬。

#### Scenario: GitHub 仓库不存在
- **WHEN** URL 指向不存在的仓库
- **THEN** 下载失败时抛出异常，包含 HTTP 状态码和 URL 信息

#### Scenario: 网络错误
- **WHEN** 下载过程中网络不可达
- **THEN** 抛出异常，包含原始错误信息