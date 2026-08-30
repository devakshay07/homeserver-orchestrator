from typing import Callable, Awaitable, Any
from telegram import Update
from telegram.ext import BaseHandler
import structlog

from config.settings import settings

logger = structlog.get_logger("telegram")

class OwnerOnlyMiddleware:
    def __init__(self, owner_id: int):
        self.owner_id = owner_id

    async def __call__(
        self,
        update: Update,
        context: Any,
        handler: Callable[[Update, Any], Awaitable[Any]],
    ) -> Any:
        user_id = update.effective_user.id if update.effective_user else None
        if user_id != self.owner_id:
            logger.warning("Unauthorized access attempt", user_id=user_id, username=update.effective_user.username if update.effective_user else None)
            if update.effective_message:
                await update.effective_message.reply_text("⛔ Unauthorized. You do not have permission to use this bot.")
            return None
            
        return await handler(update, context)
