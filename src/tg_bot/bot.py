from telegram.ext import ApplicationBuilder, TypeHandler
import structlog

from config.settings import settings
from .handlers import register_handlers
from .notifier import TelegramNotifier

logger = structlog.get_logger("telegram")

from telegram import Update
from telegram.ext import ApplicationHandlerStop, TypeHandler

def build_app(post_init=None):
    builder = ApplicationBuilder().token(settings.telegram_token.get_secret_value())
    if post_init:
        builder = builder.post_init(post_init)
    app = builder.build()
    
    async def middleware_callback(update: Update, context):
        user_id = update.effective_user.id if update.effective_user else None
        if user_id != settings.owner_telegram_id:
            logger.warning("Unauthorized access attempt", user_id=user_id)
            if update.effective_message:
                await update.effective_message.reply_text("⛔ Unauthorized. You do not have permission to use this bot.")
            raise ApplicationHandlerStop()
            
    app.add_handler(TypeHandler(Update, middleware_callback), group=-1)
    
    register_handlers(app)
    
    notifier = TelegramNotifier(app, settings.owner_telegram_id)
    return app, notifier
