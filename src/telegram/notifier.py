import asyncio
import structlog
from pathlib import Path
import json
from datetime import datetime, timezone

logger = structlog.get_logger("telegram")

DEAD_LETTER_PATH = Path("data/failed_notifications.jsonl")

class TelegramNotifier:
    MAX_RETRIES = 4
    BACKOFF_BASE = 2

    def __init__(self, app, owner_id: int):
        self.app = app
        self.owner_id = owner_id

    async def _send_with_retry(self, chat_id, text, parse_mode, reply_markup=None) -> bool:
        backoff = self.BACKOFF_BASE
        for attempt in range(self.MAX_RETRIES):
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
                return True
            except Exception as e:
                logger.warning("Telegram send failed, retrying",
                               attempt=attempt, error=str(e))
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30)
        return False

    async def send_message(self, text: str, parse_mode: str = "Markdown") -> None:
        ok = await self._send_with_retry(self.owner_id, text, parse_mode)
        if not ok:
            logger.error("Permanently failed to deliver message, writing to dead letter")
            self._write_dead_letter({"type": "message", "text": text, "parse_mode": parse_mode})

    async def send_pr_notification(self, text: str, task_id: str) -> None:
        from .keyboards import get_pr_keyboard
        ok = await self._send_with_retry(
            self.owner_id, text, "Markdown", get_pr_keyboard(task_id)
        )
        if not ok:
            logger.error("Failed to deliver PR notification", task_id=task_id)
            self._write_dead_letter({"type": "pr_notification", "text": text, "task_id": task_id})

    def _write_dead_letter(self, payload: dict) -> None:
        DEAD_LETTER_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DEAD_LETTER_PATH, "a") as f:
            f.write(json.dumps({**payload, "ts": datetime.now(timezone.utc).isoformat()}) + "\n")
