import pytest
from unittest.mock import MagicMock

def test_memory_store(mocker, tmp_path):
    mocker.patch("config.settings.settings.chroma_db_path", str(tmp_path / "chroma"))
    from memory.store import MemoryStore
    store = MemoryStore()
    assert store.prompts is not None
