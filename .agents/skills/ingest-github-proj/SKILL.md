---
name: ingest-github-proj
description: Use when the user wants to import a GitHub repository into nbrag, mentions "ingest GitHub", "import GitHub project", "add repo to knowledge base", or gives a github.com URL to ingest.
---

# Ingest GitHub Project

将 GitHub 仓库下载并导入 nbrag 知识库，复用 `ingest_github_proj()`。

## 步骤

### 1. 确认参数

向用户确认或合理推断：

- `url` — GitHub 仓库地址（必须）
- `collection_name` — 知识库名称，默认从 URL 提取 repo 名（如 `servers`）
- `relative_paths` — 用户想导入的目录。如果用户说"只导入 src 和 docs"，就用 `["src", "docs"]`；没说则忽略，导入整个仓库
- `file_extensions` — 用户想导入的文件后缀。如果用户说"只要 .py 和 .md"，就用 `[".py", ".md"]`；没说则用默认 `COMMON_FILE_EXTENSIONS`（40+ 种常见文本后缀）
- `branch` — Git 分支名，默认 `"main"`。下载失败且仓库主分支是 `"master"` 时，改为 `"master"`

### 2. 查看并记录解压后的目录结构

在写 `relative_paths` 之前，先下载 ZIP 并解压，列出项目顶层目录，挑选真正有用的目录或文件。不要凭空猜测目录名。

完成标准：你能说出项目根目录下有哪些文件夹，以及你准备导入哪些。

### 3. 写脚本

创建 `d:/codes/nbrag/scripts/ingest_some_githubs/ingest_{repo_name}.py`：

```python
import my_load_config
from nbrag.contrib.ingest_github_proj import ingest_github_proj
from nbrag import set_collection_profile

ingest_github_proj(
    "https://github.com/{owner}/{repo}",
    collection_name="{collection_name}",
    delete_first=True,
    relative_paths=["src", "docs"],  # 根据实际目录结构填写
    # branch="master",               # 仓库主分支不是 main 时指定
    # file_extensions=[".py", ".md"],  # 用户指定时才加
    verbose=True,
)
```

### 4. 填充 profile

**必须**用 `WebFetch` 读取仓库的 README（`https://raw.githubusercontent.com/{owner}/{repo}/main/README.md`），根据实际内容填写 `set_collection_profile`：

- `display_name` — 项目名称（英文优先，和 README 标题一致）
- `description` — 1-2 句话概括核心能力，用 README 里的实际描述
- `aliases` — 用户可能搜索的术语：项目名、核心概念名、缩写，方便ai通过这些术语就知道应该查询的是这个知识库。不要填太泛的词（如 "sdk" 单独作为 alias 无意义）
- `tags` — 分类标签：语言、框架、核心能力名

完成标准：`display_name`、`description`、`aliases`、`tags` 全部填写，且内容来自 README 而非凭空猜测。

### 5. 运行

提醒用户用 `D:/ProgramData/miniconda3/envs/py312/python.exe` 执行刚才写的脚本。ai不要自己运行。

## 参考

- `ingest_github_proj()` 源码：`d:/codes/nbrag/nbrag/contrib/ingest_github_proj.py`
- 已有脚本示例：`d:/codes/nbrag/scripts/ingest_some_githubs/`