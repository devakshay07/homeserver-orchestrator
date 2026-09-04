from typing import Callable, Awaitable, Any
from telegram import Update
from telegram.ext import BaseHandler
import structlog
logger = structlog.get_logger("auth")

# Middleware removed: Auth is handled inline in bot.py for simplicity.
