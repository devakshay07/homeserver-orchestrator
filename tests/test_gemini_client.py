import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setattr("config.settings.settings.gemini_keys", ["key1", "key2"])

@pytest.mark.asyncio
async def test_gemini_client_init(mocker, mock_settings):
    # Mock genai to avoid actual API calls
    mocker.patch("google.generativeai.configure")
    from gemini.client import GeminiClient
    
    client = GeminiClient()
    assert client._current_idx == 0
    assert len(client.keys) == 2
    
    await client._rotate_key()
    assert client._current_idx == 1

    await client._rotate_key()
    assert client._current_idx == 0
