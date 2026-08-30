# Telegram Commands

The entire Orchestrator is controlled via Telegram. Send these commands to your bot to manage the system.

## Generation & Build
- `/build <idea>`: Generate a brand new software project based on your prompt.
- `/regenerate <task_id>`: Retry generation for a failed or rejected task.

## Queue & Monitoring
- `/queue`: List all pending and in-progress tasks.
- `/status [task_id]`: View the detailed status, current checkpoint, and attempts of a specific task.
- `/history`: View a list of recently completed tasks.
- `/stats`: View system health, disk usage, active workers, and task metrics.
- `/logs [task_id]`: Tail the system logs for a specific generation task.
- `/pending_notifications`: Attempt to flush and resend any notifications that failed due to network issues.

## Pull Requests
- `/pr [task_id]`: View the GitHub PR link and details for a generated project.
- `/approve <task_id>`: Merge the PR directly from Telegram.
- `/reject <task_id>`: Close the PR and mark the task as rejected.

## Memory & Configuration
- `/memory search <query>`: Perform a semantic search on past generations using local ChromaDB.
- `/settings`: View the active system configuration (secrets are masked).

## Scheduler
- `/cron list`: View all scheduled jobs.
- `/cron remove <job_id>`: Remove a scheduled job.
- `/cron daily HH:MM <idea>`: Schedule a daily generation task.
- `/cron weekly <day> HH:MM <idea>`: Schedule a weekly generation task.
