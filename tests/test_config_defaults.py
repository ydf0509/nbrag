from nbrag import config


def test_chunking_defaults_when_env_and_yaml_missing(monkeypatch):
    monkeypatch.delenv("NBRAG_CONFIG", raising=False)
    monkeypatch.delenv("NBRAG_CHUNK_SIZE", raising=False)
    monkeypatch.delenv("NBRAG_CHUNK_OVERLAP", raising=False)
    monkeypatch.setattr(config, "_find_config_file", lambda: None)
    config._config = None

    cfg = config.load_config()

    assert cfg.chunking.chunk_size == 1500
    assert cfg.chunking.chunk_overlap == 200


def test_chunking_env_values_override_defaults(monkeypatch):
    monkeypatch.delenv("NBRAG_CONFIG", raising=False)
    monkeypatch.setenv("NBRAG_CHUNK_SIZE", "2048")
    monkeypatch.setenv("NBRAG_CHUNK_OVERLAP", "256")
    monkeypatch.setattr(config, "_find_config_file", lambda: None)
    config._config = None

    cfg = config.load_config()

    assert cfg.chunking.chunk_size == 2048
    assert cfg.chunking.chunk_overlap == 256
