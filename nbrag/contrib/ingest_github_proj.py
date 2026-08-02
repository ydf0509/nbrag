"""
通过 GitHub archive ZIP 下载项目并导入到 nbrag 知识库。

用法:
    from nbrag.contrib.ingest_github_proj import ingest_github_proj

    ingest_github_proj(
        "https://github.com/modelcontextprotocol/servers",
        collection_name="mcp-servers",
        relative_paths=["src", "lib"],
        file_extensions=[".py", ".md", ".ts"],
        verbose=True,
    )
"""

import os
import re
import tempfile
import urllib.request
import zipfile

from nbrag.ingest import batch_ingest


def _parse_github_url(url: str) -> tuple[str, str]:
    """从 GitHub URL 提取 (owner, repo)。

    支持格式:
        https://github.com/owner/repo
        https://github.com/owner/repo/
        https://github.com/owner/repo/tree/branch/...
    """
    url = url.rstrip("/")
    # 去掉 /tree/xxx 或 /blob/xxx 等子路径
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)", url)
    if not m:
        raise ValueError(f"无法解析 GitHub URL: {url}")
    owner = m.group(1)
    repo = m.group(2)
    return owner, repo

COMMON_FILE_EXTENSIONS = [
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".rb", ".php", ".swift", ".kt", ".scala", ".r", ".m", ".lua", ".zig",
    ".html", ".css", ".scss", ".less", ".vue", ".svelte",
    ".md",'.mdx', ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml", ".csv",
    ".sql", ".graphql", ".proto",
    ".sh", ".bash", ".ps1", ".bat",
]


def _download_and_extract(owner: str, repo: str, branch: str = "main") -> str:
    """下载 GitHub 仓库指定分支 ZIP 并解压到临时目录。

    Args:
        branch: 分支名，默认 "main"。仓库使用 "master" 时传入 "master"。

    Returns:
        解压后的项目根目录路径。
    """
    zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
    tmp_dir = tempfile.gettempdir()
    zip_path = os.path.join(tmp_dir, f"{repo}-{branch}.zip")

    print(f"[github] 下载 {zip_url}")
    urllib.request.urlretrieve(zip_url, zip_path)

    extract_dir = os.path.join(tmp_dir, f"{repo}-{branch}")
    print(f"[github] 解压到 {extract_dir}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    print(f"[github] 下载完成: {zip_path}")
    print(f"[github] 项目目录: {extract_dir}")
    return extract_dir


def ingest_github_proj(
    url: str,
    collection_name: str,
    relative_paths: list[str] | None = None,
    file_extensions: list[str] | None = None,
    branch: str = "main",
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    delete_first: bool = False,
    sleep_interval: float = 0.01,
    use_cache: bool = True,
    max_workers: int = 1,
    verbose: bool = False,
):
    """下载 GitHub 项目并导入到 nbrag 知识库。

    Args:
        url: GitHub 仓库 URL，如 https://github.com/owner/repo
        collection_name: 目标知识库名称
        relative_paths: 相对于项目根目录的文件夹或文件路径，如 ["src", "lib", "docs"]。
                        会被拼成绝对路径传给 batch_ingest。
                        自动追加 README.md 和 LICENSE（如果存在）。
                        不传则导入整个项目根目录。
        file_extensions: 要导入的文件后缀列表，如 [".py", ".md"]。
                         默认追加 .md, .txt, .rst 以覆盖常见文档。
        branch: Git 分支名，默认 "main"。仓库主分支为 "master" 时传入 "master"。
        chunk_size: 分块大小
        chunk_overlap: 分块重叠字符数
        delete_first: 是否先删除已有知识库再导入
        sleep_interval: embedding 请求间隔（秒），避免 API 限流
        use_cache: 是否跳过未修改的已缓存文件
        max_workers: 并行处理线程数
        verbose: 是否打印详细日志
    """
    owner, repo = _parse_github_url(url)
    extract_dir = _download_and_extract(owner, repo, branch=branch)

    # 找到解压后实际的项目根目录（ZIP 内通常有一层 {repo}-{branch}/ 目录）
    entries = os.listdir(extract_dir)
    subdirs = [e for e in entries if os.path.isdir(os.path.join(extract_dir, e))]
    if len(subdirs) == 1:
        project_root = os.path.join(extract_dir, subdirs[0])
    else:
        project_root = extract_dir

    # 构造目标路径列表
    if relative_paths:
        target_paths = [os.path.join(project_root, p) for p in relative_paths]
    else:
        target_paths = [project_root]

    # 自动追加根目录常见文档文件
    for doc_name in ("README.md", "LICENSE"):
        doc_path = os.path.join(project_root, doc_name)
        if os.path.isfile(doc_path) and doc_path not in target_paths:
            target_paths.append(doc_path)

    # 文件类型：默认使用 COMMON_FILE_EXTENSIONS，用户传了就用用户的
    if file_extensions is None:
        file_extensions = list(COMMON_FILE_EXTENSIONS)
    else:
        file_extensions = list(file_extensions)

    # 自动排除 .git
    excluded_paths = [os.path.join(project_root, ".git")]

    if verbose:
        print(f"[github] 导入路径: {target_paths}")
        print(f"[github] 文件类型: {file_extensions}")
        print(f"[github] 排除路径: {excluded_paths}")

    batch_ingest(
        paths=target_paths,
        collection_name=collection_name,
        file_extensions=file_extensions,
        excluded_paths=excluded_paths,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        delete_first=delete_first,
        sleep_interval=sleep_interval,
        use_cache=use_cache,
        max_workers=max_workers,
        verbose=verbose,
    )