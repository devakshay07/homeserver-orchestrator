import pytest
from unittest.mock import MagicMock

def test_gemini_client_init(mocker):
    # Mock genai to avoid actual API calls
    mocker.patch("google.generativeai.configure")
    from gemini.client import GeminiClient
    
    client = GeminiClient()
    assert client._current_idx == 0
    assert len(client.keys) == 1
    
    await client._rotate_key()
    assert client._current_idx == 0 # Only 1 key in test env
