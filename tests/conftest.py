import os
import pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def isolated_settings(tmp_path):
    env = {
        "TELEGRAM_TOKEN": "test_token",
        "OWNER_TELEGRAM_ID": "999",
        "GEMINI_KEYS": '["test_key"]',
        "GITHUB_PAT": "test_pat",
        "GITHUB_OWNER": "test_owner",
        "DB_PATH": str(tmp_path / "test.sqlite"),
        "CHROMA_DB_PATH": str(tmp_path / "chroma"),
        "WORKSPACE_DIR": str(tmp_path / "workspaces"),
    }
    with patch.dict(os.environ, env, clear=True):
        import config.settings as cs_module
        fresh = cs_module.Settings()
        with patch.object(cs_module, "settings", fresh):
            yield fresh
