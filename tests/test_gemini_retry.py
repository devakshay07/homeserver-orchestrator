import pytest
from unittest.mock import MagicMock, AsyncMock
from gemini.client import GeminiClient, GeminiQuotaExhausted

@pytest.mark.asyncio
async def test_rotates_key_on_429(mocker, isolated_settings):
    client = GeminiClient()
    call_count = 0
    
    async def fake_generate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("429 quota exceeded")
        return MagicMock(parts=["ok"], text="result")
    
    mocker.patch.object(client, "_call_api", side_effect=fake_generate)
    result = await client.generate_content("gemini-2.5-flash", "test")
    assert result == "result"
