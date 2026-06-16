"""列出所有 nbrag 知识库，并检查是否存在 funboost 相关的 collection。

用法:
    D:/ProgramData/miniconda3/envs/py312/python.exe tests/ai_codes/list_knowledge_bases.py
"""
from nbrag.core import list_collections


def main():
    cols = list_collections()
    print(f"共 {len(cols)} 个知识库：\n")

    funboost_related = []
    for c in cols:
        name = c.name
        n = c.count()
        is_fb = "funboost" in name.lower()
        marker = "  <-- funboost" if is_fb else ""
        print(f"  - {name:45s}  {n:>7,} chunks{marker}")
        if is_fb:
            funboost_related.append((name, n))

    print()
    if funboost_related:
        print(f"[OK] 找到 {len(funboost_related)} 个 funboost 相关知识库：")
        for name, n in funboost_related:
            print(f"     - {name}  ({n:,} chunks)")
    else:
        print("[X] 没找到任何 funboost 知识库")


if __name__ == "__main__":
    main()
