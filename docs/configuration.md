# Configuration Guide

All configuration for the HomeServer Orchestrator is managed through environment variables. You can provide these by creating a `.env` file in the root directory.

## Core Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `TELEGRAM_TOKEN` | Bot token provided by @BotFather | **Yes** | None |
| `OWNER_TELEGRAM_ID` | Your Telegram User ID. The bot will ignore messages from anyone else. | **Yes** | None |
| `GEMINI_KEYS` | A JSON array of Gemini API keys (e.g., `["key1", "key2"]`). Used for automatic rotation. | **Yes** | None |
| `GITHUB_PAT` | GitHub Personal Access Token with repo scope. | **Yes** | None |
| `GITHUB_OWNER` | Your GitHub Username or Organization where repos will be created. | **Yes** | None |

## Advanced / Tuning Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_MODEL_SPEC` | The model used for writing specifications. | `gemini-2.5-pro` |
| `GEMINI_MODEL_CODE` | The model used for generating the codebase. | `gemini-2.5-flash` |
| `WORKSPACE_DIR` | Directory where generated projects are temporarily stored. | `./data/workspaces` |
| `MAX_RETRIES` | Max attempts a task makes before failing. | `3` |
| `DISK_MIN_FREE_GB` | Minimum free disk space required to start a new generation task. | `2.0` |
| `WORKSPACE_MAX_AGE_DAYS`| How long to keep generated files on disk before cleanup. | `7` |
| `LOG_LEVEL` | Application logging level (`INFO`, `DEBUG`, etc.) | `INFO` |

## Example `.env`

```env
TELEGRAM_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ
OWNER_TELEGRAM_ID=987654321
GEMINI_KEYS=["AIzaSyXXXX...", "AIzaSyYYYY..."]
GITHUB_PAT=ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GITHUB_OWNER=yourusername

DISK_MIN_FREE_GB=2.0
WORKSPACE_MAX_AGE_DAYS=5
```
