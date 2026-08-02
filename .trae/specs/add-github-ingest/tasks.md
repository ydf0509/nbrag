# Tasks

- [x] Task 1: 实现 URL 解析函数
  - 解析 GitHub URL，提取 owner 和 repo 名
  - 处理带 `/tree/xxx` 的 URL 和尾部斜杠
  - 返回 `(owner, repo)` 元组

- [x] Task 2: 实现下载和解压函数
  - 使用 `urllib.request` 下载 `https://github.com/{owner}/{repo}/archive/refs/heads/main.zip`
  - 使用 `zipfile` 解压到临时目录
  - 打印下载和解压路径

- [x] Task 3: 实现 `ingest_github_proj()` 主函数
  - 组合 URL 解析 + 下载解压 + batch_ingest 调用
  - 参数：`url`, `collection_name`, `file_extensions`, `chunk_size`, `chunk_overlap`, `max_workers`, `verbose`
  - `file_extensions` 自动追加文档后缀 `.md`, `.txt`, `.rst`
  - `excluded_paths` 自动排除解压目录下的 `.git`
  - 不捕获错误，异常直接上抛

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2