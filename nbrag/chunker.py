"""
RAG 分块增强模块 —— 文本切分 + 行号计算 + AST scope 解析 + 头部上下文注入。

从 core.py 拆分出来，专注于「把原始文本变成 enriched chunks」这一步。
core.py 专注于存储和检索。
"""

import os
import ast
import bisect
import warnings

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from nbrag.defaults import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE

# ─── 文件类型映射 ─────────────────────────────────────────

TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
    ".rs", ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".sh",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".csv", ".tsv", ".xml", ".html", ".css", ".sql", ".r", ".lua",
    ".swift", ".kt", ".scala", ".dart", ".vue", ".svelte",
    ".rst", ".tex", ".log", ".env", ".bat", ".ps1",
}

_EXT_TO_LANG = {
    ".py": Language.PYTHON, ".js": Language.JS, ".ts": Language.TS,
    ".jsx": Language.JS, ".tsx": Language.TS,
    ".java": Language.JAVA, ".go": Language.GO,
    ".rs": Language.RUST, ".rb": Language.RUBY,
    ".cpp": Language.CPP, ".c": Language.C, ".h": Language.C, ".hpp": Language.CPP,
    ".cs": Language.CSHARP, ".php": Language.PHP,
    ".swift": Language.SWIFT, ".kt": Language.KOTLIN, ".scala": Language.SCALA,
    ".lua": Language.LUA, ".sol": Language.SOL,
    ".md": Language.MARKDOWN, ".html": Language.HTML,
    ".tex": Language.LATEX, ".rst": Language.RST,
}


# ─── 文本切分 ─────────────────────────────────────────────

def chunk_text(text, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_CHUNK_OVERLAP,
               file_ext=""):
    """根据文件类型自动选择最优切分策略（不含头部注入）。
    代码文件按 class/function 边界切分；Markdown 按标题切分；通用文本按段落切分。
    """
    text = text.strip()
    if not text:
        return []

    lang = _EXT_TO_LANG.get(file_ext.lower())
    if lang:
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=lang, chunk_size=chunk_size, chunk_overlap=overlap,
        )
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=overlap,
            separators=["\n\n", "\n", "。", ".", "；", ";", "，", ",", " ", ""],
        )
    return splitter.split_text(text)


# ─── 行号计算 ─────────────────────────────────────────────

def _build_line_offsets(text):
    """构建行号偏移表: line_offsets[i] = 第 i+1 行的起始字符位置。"""
    offsets = [0]
    for line in text.split('\n'):
        offsets.append(offsets[-1] + len(line) + 1)
    return offsets


def compute_line_ranges(full_text, chunks, overlap=DEFAULT_CHUNK_OVERLAP):
    """为每个 chunk 计算它在原文中的行号范围 (1-based)。

    使用顺序搜索 + 重叠偏移，确保每个 chunk 匹配到正确位置。
    Returns: [(start_line, end_line), ...]
    """
    line_offsets = _build_line_offsets(full_text)
    ranges = []
    search_start = 0

    for chunk in chunks:
        stripped = chunk.strip()
        if not stripped:
            ranges.append((0, 0))
            continue

        needle = stripped[:200]
        pos = full_text.find(needle, search_start)
        if pos == -1:
            pos = full_text.find(needle)

        if pos >= 0:
            start_line = bisect.bisect_right(line_offsets, pos)
            end_pos = pos + len(stripped)
            end_line = bisect.bisect_right(line_offsets, end_pos)
            ranges.append((start_line, end_line))
            advance = max(1, len(stripped) - overlap)
            search_start = pos + advance
        else:
            ranges.append((0, 0))

    return ranges


# ─── Python AST scope 解析 ────────────────────────────────

def _extract_signature(node):
    """从 AST 节点提取函数签名字符串。ClassDef 返回基类列表。"""
    if isinstance(node, ast.ClassDef):
        if node.bases:
            bases = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
                elif isinstance(b, ast.Attribute):
                    bases.append(b.attr)
                else:
                    bases.append("?")
            return f"class {node.name}({', '.join(bases)})"
        return f"class {node.name}"

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = node.args
        params = []
        all_args = args.args + args.posonlyargs
        defaults_offset = len(all_args) - len(args.defaults)
        for i, arg in enumerate(all_args):
            p = arg.arg
            if arg.annotation and isinstance(arg.annotation, ast.Name):
                p += f": {arg.annotation.id}"
            if i >= defaults_offset:
                p += "=..."
            params.append(p)
        if args.vararg:
            params.append(f"*{args.vararg.arg}")
        if args.kwonlyargs:
            if not args.vararg:
                params.append("*")
            for kw in args.kwonlyargs:
                p = kw.arg
                if kw.annotation and isinstance(kw.annotation, ast.Name):
                    p += f": {kw.annotation.id}"
                params.append(p)
        if args.kwarg:
            params.append(f"**{args.kwarg.arg}")
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        sig = f"{prefix} {node.name}({', '.join(params)})"
        if node.returns and isinstance(node.returns, ast.Name):
            sig += f" -> {node.returns.id}"
        return sig

    return ""


def get_ast_definition_line_range(node):
    """Return the 1-based source line range for a Python definition, including decorators.

    Python AST lineno for ClassDef/FunctionDef/AsyncFunctionDef points to the
    class/def line. For definition lookup and scope metadata, decorators are part
    of the reusable definition and must be included in the start line.
    """
    start = getattr(node, "lineno", 1)
    decorators = getattr(node, "decorator_list", None) or []
    decorator_lines = [getattr(dec, "lineno", start) for dec in decorators]
    if decorator_lines:
        start = min([start, *decorator_lines])
    end = getattr(node, "end_lineno", None) or start
    return start, end


def _build_python_scope_map(text):
    """解析 Python 代码，构建 scope 列表。

    返回: [(start_line, end_line, scope_str, signature), ...]
    scope_str 示例: "MyClass", "MyClass.my_method", "my_function"
    signature 示例: "def my_method(self, x, y=...)"
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text)
    except SyntaxError:
        return []

    scopes = []

    def _walk(node, parent_chain=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = child.name
                scope_str = f"{parent_chain}.{name}" if parent_chain else name
                start, end = get_ast_definition_line_range(child)
                sig = _extract_signature(child)
                scopes.append((start, end, scope_str, sig))
                _walk(child, scope_str)

    _walk(tree)
    return scopes


def get_python_scope_at_line(text, line_number):
    """给定行号，返回该行所属的完整 scope 链字符串。

    返回示例: "MyClass", "MyClass.my_method", ""(模块级)
    """
    scope_map = _build_python_scope_map(text)
    scope, _sig, _parent = _find_scope_in_map(scope_map, line_number)
    return scope


# ─── 头部上下文注入 ───────────────────────────────────────

def _format_header(file_path, line_start, line_end, scope="", signature="",
                   parent_class_sig=""):
    """格式化 chunk 头部注入字符串。"""
    parts = [f"[File: {file_path}]"]
    if scope:
        if "." in scope:
            class_part, method_part = scope.rsplit(".", 1)
            if parent_class_sig:
                parts.append(f"[Class: {parent_class_sig}]")
            else:
                parts.append(f"[Class: {class_part}]")
            parts.append(f"[Method: {method_part}]")
        else:
            parts.append(f"[Scope: {scope}]")
    if signature:
        parts.append(f"[Sig: {signature}]")
    if line_start and line_end:
        parts.append(f"[Lines: {line_start}-{line_end}]")
    return "# " + " ".join(parts)


def _find_scope_in_map(scope_map, line_number):
    """从预构建的 scope_map 中查找指定行号的最内层 scope。
    返回 (scope_str, signature, parent_class_sig) 元组。
    parent_class_sig: 如果当前 scope 是方法（如 Cls.method），返回父类的签名（含继承链）。"""
    best_scope = ""
    best_sig = ""
    best_size = float('inf')
    parent_class_sig = ""
    for entry in scope_map:
        s_start, s_end, s_str = entry[0], entry[1], entry[2]
        sig = entry[3] if len(entry) > 3 else ""
        if s_start <= line_number <= s_end:
            size = s_end - s_start
            if size < best_size:
                best_size = size
                best_scope = s_str
                best_sig = sig
    if "." in best_scope:
        class_name = best_scope.rsplit(".", 1)[0]
        for entry in scope_map:
            if entry[2] == class_name:
                parent_class_sig = entry[3] if len(entry) > 3 else ""
                break
    return best_scope, best_sig, parent_class_sig


def enrich_chunks(chunks, full_text, file_path="", file_ext=""):
    """为 chunks 注入头部上下文信息，返回 (enriched_chunks, line_ranges, scopes)。

    头部注入在 embedding 前完成，让向量包含上下文信息。
    line_ranges 和 scopes 用于存入 metadata。
    """
    if not chunks:
        return [], [], []

    line_ranges = compute_line_ranges(full_text, chunks)

    scope_map = []
    if file_ext.lower() == ".py":
        scope_map = _build_python_scope_map(full_text)

    enriched = []
    scopes = []
    for i, chunk in enumerate(chunks):
        ls, le = line_ranges[i]
        if scope_map and ls > 0:
            scope, sig, parent_cls_sig = _find_scope_in_map(scope_map, ls)
        else:
            scope, sig, parent_cls_sig = "", "", ""
        scopes.append(scope)
        header = _format_header(file_path, ls, le, scope, sig, parent_cls_sig)
        enriched.append(f"{header}\n{chunk}")

    return enriched, line_ranges, scopes


def _normalize_path_for_match(path):
    return os.path.normcase(os.path.normpath(os.path.abspath(os.path.expanduser(str(path)))))


def _prepare_excluded_paths(excluded_paths=None):
    if not excluded_paths:
        return []
    if isinstance(excluded_paths, (str, os.PathLike)):
        excluded_paths = [excluded_paths]
    return [_normalize_path_for_match(path) for path in excluded_paths]


def _is_path_under_or_equal(path, candidate_parent):
    path = _normalize_path_for_match(path)
    candidate_parent = _normalize_path_for_match(candidate_parent)
    if path == candidate_parent:
        return True
    try:
        return os.path.commonpath([path, candidate_parent]) == candidate_parent
    except ValueError:
        return False


def _is_excluded_path(path, prepared_excluded_paths):
    if not prepared_excluded_paths:
        return False
    return any(_is_path_under_or_equal(path, excluded) for excluded in prepared_excluded_paths)


def collect_files(path, file_extensions=None, excluded_paths=None):
    """收集路径下所有文本文件（支持单文件或递归目录）。

    Args:
        path: 文件或目录路径。
        file_extensions: 可选，限定的后缀列表（如 [".py", ".md"]）。
                         传入时只收集这些后缀；不传则使用 TEXT_EXTENSIONS 全集。
                         后缀不区分大小写，自动补 "." 前缀（"py" → ".py"）。
        excluded_paths: 可选，排除的文件或目录路径列表。路径会规范化为绝对路径匹配，
                        兼容 Windows 反斜杠和 POSIX 顺斜杠。
    """
    if file_extensions is not None:
        allowed = set()
        for ext in file_extensions:
            ext = ext.strip().lower()
            if not ext.startswith("."):
                ext = "." + ext
            allowed.add(ext)
    else:
        allowed = TEXT_EXTENSIONS

    prepared_excluded_paths = _prepare_excluded_paths(excluded_paths)
    if _is_excluded_path(path, prepared_excluded_paths):
        return []

    if os.path.isfile(path):
        ext = os.path.splitext(path)[1].lower()
        if ext in allowed:
            return [path]
        return []
    files = []
    for root, dirnames, fnames in os.walk(path):
        dirnames[:] = [
            dirname for dirname in dirnames
            if not _is_excluded_path(os.path.join(root, dirname), prepared_excluded_paths)
        ]
        for fn in sorted(fnames):
            file_path = os.path.join(root, fn)
            if _is_excluded_path(file_path, prepared_excluded_paths):
                continue
            if os.path.splitext(fn)[1].lower() in allowed:
                files.append(file_path)
    return files
