# Troubleshooting & FAQ

## The bot isn't responding to my messages
Check your `OWNER_TELEGRAM_ID` in `.env`. The bot explicitly ignores all messages from Telegram users whose IDs do not match this variable. You can use bots like `@userinfobot` on Telegram to find your ID.

## "429 Quota Exhausted" Errors
The orchestrator natively supports API key rotation. If you frequently hit rate limits, add more Gemini API keys to the `GEMINI_KEYS` JSON array in your `.env` file.

## "Insufficient disk space" Error
The system requires a minimum amount of disk space to generate code and run isolated Python virtual environments for testing. 
- Try lowering `DISK_MIN_FREE_GB` in your `.env` if your device is extremely constrained.
- Ensure the background janitor is running. You can check disk space anytime using the `/stats` command in Telegram.

## System crashed mid-generation. Do I need to start over?
No. Thanks to the WAL-mode SQLite queue and fine-grained state checkpointing, simply restart the application (`docker-compose restart`). The worker watchdog will automatically pick up the pending task exactly from the stage it failed (e.g., skipping the API spec generation if it was already completed).

## My tests fail on generated projects
If `pytest` or `ruff` fail during the Quality Gate, the orchestrator will not merge the code. You will be notified in Telegram. You can use `/regenerate <task_id>` to have the AI attempt the build again, taking past memory into account.
