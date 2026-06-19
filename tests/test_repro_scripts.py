from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests" / "ai_codes" / "repro_nbrag_search_error.py"
PYTHON = Path("D:/ProgramData/miniconda3/envs/py312/python.exe")


def test_repro_nbrag_search_script_calls_mcp_tools_directly():
    completed = subprocess.run(
        [str(PYTHON), str(SCRIPT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    combined = f"{completed.stdout}\n{completed.stderr}"

    assert completed.returncode == 0
    assert "calling nbrag.mcp_tools.nbrag_search" in combined
    assert "collection_name=sanguo" in combined
    assert "query=赤壁之战中曹操为什么失败，周瑜和诸葛亮用了什么计策" in combined
    assert "[sanguo] 575 chunks | hybrid(bm25+vector): on | rerank:" in combined
    assert "file_path: D:/codes/nbrag/scripts/inguest_novel/sanguo_chapters/" in combined
