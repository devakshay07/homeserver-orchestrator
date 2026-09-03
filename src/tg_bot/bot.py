from telegram.ext import ApplicationBuilder, TypeHandler
import structlog

from config.settings import settings
from .handlers import register_handlers
from .middleware import OwnerOnlyMiddleware
from .notifier import TelegramNotifier

logger = structlog.get_logger("telegram")

def build_app():
    app = ApplicationBuilder().token(settings.telegram_token.get_secret_value()).build()
    
    # Add middleware for owner-only access
    middleware = OwnerOnlyMiddleware(settings.owner_telegram_id)
    
    # We can't strictly add it as a middleware in ptb v20+ easily without wrapping handlers, 
    # but we can use a TypeHandler or process it in the application's process_update
    # For simplicity, we can wrap the main Application's process_update
    original_process_update = app.process_update
    
    async def process_update_with_middleware(update, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        if user_id != settings.owner_telegram_id:
            logger.warning("Unauthorized access attempt", user_id=user_id, username=update.effective_user.username if update.effective_user else None)
            if update.effective_message:
                await update.effective_message.reply_text("⛔ Unauthorized. You do not have permission to use this bot.")
            return
        await original_process_update(update, *args, **kwargs)
        
    app.process_update = process_update_with_middleware
    
    register_handlers(app)
    
    notifier = TelegramNotifier(app, settings.owner_telegram_id)
    return app, notifier
