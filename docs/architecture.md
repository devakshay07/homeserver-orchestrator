# Architecture & Design

The HomeServer Orchestrator is built to be resilient, modular, and extremely light on resources, making it perfect for edge devices.

## Core Components

1. **Telegram Interface (`src/telegram/`)**: 
   - Uses `python-telegram-bot` to provide a conversational UI.
   - Built with resilient retry loops and exponential backoff to handle network drops on edge networks.
   - Features a dead-letter queue for notifications that fail to send, ensuring you never miss a PR update.

2. **Persistent Queue & State Machine (`src/queue/`)**: 
   - A WAL-mode SQLite database manages all background tasks. 
   - **Checkpointing**: Every task is a state machine. As it progresses (Spec -> Code -> Quality Gate -> GitHub PR), it saves its state. If the server loses power, the worker resumes the task exactly where it left off, saving expensive LLM API calls.

3. **AI Generation Engine (`src/gemini/`)**:
   - Handles LLM requests to Gemini models.
   - Includes automatic API key rotation and model fallback logic (`gemini-2.5-flash` -> `2.0-flash`) to handle Rate Limits (`429 Quota Exhausted`).

4. **Quality Gates (`src/review/`)**:
   - Before any code is pushed to GitHub, a localized virtual environment is created to run a suite of tests.
   - **Checks include**: `ruff` (formatting), `mypy` (static types), `detect-secrets` (security), and `pytest` (unit tests).
   - Degrades gracefully: Blocking errors (syntax/tests) fail the pipeline, while warnings (formatting) are merely appended to the PR review.

5. **Semantic Memory (`src/memory/`)**:
   - A local ChromaDB instance running entirely in SQLite mode (no daemon required).
   - Embeds and retrieves past project generations to provide context to the LLM, preventing the repetition of mistakes.

6. **Storage Lifecycle Management (`src/storage/`)**:
   - Actively monitors disk space, enforcing minimum thresholds.
   - Automatically cleans up old generated workspaces and heavy virtual environments to prevent disk exhaustion.
