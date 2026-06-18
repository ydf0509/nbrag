import json
from pathlib import Path
from types import SimpleNamespace

import nbrag.collection_profiles as collection_profiles
from nbrag.config import ChunkingConfig, EmbeddingConfig, RagConfig, RerankConfig, StorageConfig
from nbrag import retrieval, server
from nbrag.storage import get_collection


def _profile_config(tmp_path):
    db_path = tmp_path / "rag_db"
    return RagConfig(
        embedding=EmbeddingConfig(),
        rerank=RerankConfig(),
        storage=StorageConfig(db_path=str(db_path), raw_files_path=str(db_path / "raw_files")),
        chunking=ChunkingConfig(),
    )


def test_collection_profile_round_trip(tmp_path, monkeypatch):
    cfg = _profile_config(tmp_path)
    monkeypatch.setattr(collection_profiles, "get_config", lambda: cfg)

    updated = collection_profiles.set_collection_profile(
        "sanguo_yanyi",
        display_name="三国演义知识库",
        description="包含《三国演义》章节正文，适合查询关羽、张飞、刘备、曹操、诸葛亮等内容。",
        aliases=["三国", "三国演义", "关羽", "张飞", "刘备"],
        tags=["古典小说", "文学"],
    )

    assert updated["collection_name"] == "sanguo_yanyi"
    assert updated["display_name"] == "三国演义知识库"
    assert updated["aliases"] == ["三国", "三国演义", "关羽", "张飞", "刘备"]

    manifest_path = Path(cfg.storage.db_path) / "collection_profiles.json"
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert saved["collections"]["sanguo_yanyi"]["description"].startswith("包含《三国演义》")
    assert collection_profiles.get_collection_profile("sanguo_yanyi")["display_name"] == "三国演义知识库"


def test_collection_profile_does_not_write_chroma_metadata(tmp_path, monkeypatch):
    cfg = _profile_config(tmp_path)
    monkeypatch.setattr(collection_profiles, "get_config", lambda: cfg)
    monkeypatch.setattr("nbrag.storage.get_config", lambda: cfg)
    monkeypatch.setattr("nbrag.state._chroma_client", None)
    monkeypatch.setattr("nbrag.state._data_dir_initialized", False)

    collection_profiles.set_collection_profile(
        "sanguo_yanyi",
        display_name="三国演义知识库",
        description="包含《三国演义》章节正文。",
        aliases=["三国", "关羽"],
    )

    col = get_collection("sanguo_yanyi")

    assert col.metadata == {"hnsw:space": "cosine"}


def test_get_stats_merges_collection_profile_fields(monkeypatch):
    class FakeCollection:
        def __init__(self, count):
            self._count = count

        def count(self):
            return self._count

    class FakeChroma:
        def __init__(self, collections):
            self._collections = collections

        def get_collection(self, name):
            return self._collections[name]

    monkeypatch.setattr(
        retrieval,
        "list_collections",
        lambda: [SimpleNamespace(name="sanguo_yanyi")],
    )
    monkeypatch.setattr(
        retrieval,
        "_get_chroma",
        lambda: FakeChroma({"sanguo_yanyi": FakeCollection(12)}),
    )
    monkeypatch.setattr(
        retrieval,
        "_batch_get",
        lambda col, include, ids=None, where=None: {
            "ids": ["a", "b"],
            "metadatas": [{"doc_id": "doc1"}, {"doc_id": "doc2"}],
        },
    )
    monkeypatch.setattr(
        retrieval,
        "list_collection_profiles",
        lambda: {
            "sanguo_yanyi": {
                "collection_name": "sanguo_yanyi",
                "display_name": "三国演义知识库",
                "description": "包含《三国演义》章节正文。",
                "aliases": ["三国", "三国演义"],
                "tags": ["古典小说"],
            }
        },
    )

    stats = retrieval.get_stats()
    info = stats["collections"]["sanguo_yanyi"]

    assert info["display_name"] == "三国演义知识库"
    assert info["description"] == "包含《三国演义》章节正文。"
    assert info["aliases"] == ["三国", "三国演义"]
    assert info["doc_count"] == 2
    assert info["chunk_count"] == 12


def test_nbrag_stats_renders_collection_profile_summary(monkeypatch):
    monkeypatch.setattr(
        server,
        "get_config",
        lambda: SimpleNamespace(chunking=SimpleNamespace(chunk_size=1500, chunk_overlap=200)),
    )
    monkeypatch.setattr(
        server,
        "get_stats",
        lambda: {
            "embedding_model": "BAAI/bge-m3",
            "rerank_model": "BAAI/bge-reranker-v2-m3",
            "data_dir": "D:/codes/nbrag/rag_db",
            "collection_count": 1,
            "collections": {
                "sanguo_yanyi": {
                    "doc_count": 12,
                    "chunk_count": 88,
                    "display_name": "三国演义知识库",
                    "description": "包含《三国演义》章节正文，适合查询关羽、张飞、刘备、曹操、诸葛亮等内容。",
                    "aliases": ["三国", "三国演义", "关羽", "张飞", "刘备"],
                    "tags": ["古典小说"],
                }
            },
        },
    )

    output = server.nbrag_stats()

    assert "三国演义知识库" in output
    assert "description:" in output
    assert "aliases: 三国, 三国演义, 关羽, 张飞, 刘备" in output
