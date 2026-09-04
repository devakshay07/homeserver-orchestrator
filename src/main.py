import asyncio
import structlog
from pathlib import Path

from config.settings import settings
from app_logging.setup import setup_logging
from task_queue.sqlite_queue import SQLiteQueue
from task_queue.worker import TaskWorker
from tg_bot.bot import build_app
from scheduler.cron_manager import cron_manager

# Initialize logging before creating loggers
setup_logging()
logger = structlog.get_logger("app")

def main() -> None:
    from orchestrator import Orchestrator
    from gemini.triage import TriageAgent
    from maintenance.system_cleaner import SystemCleaner

    db_queue = SQLiteQueue()
    
    import scheduler.job_builder
    scheduler.job_builder.db_queue = db_queue
    
    # We will pass a post_init hook to build_app
    async def post_init(app) -> None:
        logger.info("Initializing background tasks...")
        
        # Start Worker and Cron
        worker.start()
        cron_manager.start()
        
        # Schedule Nightly Maintenance
        # We must use a standalone function here, not a bound method of `cleaner`.
        # APScheduler cannot pickle bound methods of objects containing unpicklable state
        # (like the `notifier` which contains the Telegram Bot instance).
        cron_manager.scheduler.add_job(
            SystemCleaner.run_standalone_maintenance,
            'cron',
            hour=3,
            minute=0,
            id='nightly_system_maintenance',
            replace_existing=True
        )
        
        try:
            await notifier.send_message("🟢 HomeServer is online and ready.")
        except Exception as e:
            logger.error(f"Failed to send startup message: {e}")

    tg_app, notifier = build_app(post_init=post_init)
    orchestrator = Orchestrator(db_queue, notifier)
    worker = TaskWorker(db_queue, orchestrator.process_task)

    tg_app.bot_data['db_queue'] = db_queue
    tg_app.bot_data['notifier'] = notifier
    tg_app.bot_data['worker'] = worker
    tg_app.bot_data['cron_manager'] = cron_manager
    tg_app.bot_data['triage_agent'] = TriageAgent(orchestrator.gemini_client)

    logger.info("Starting HomeServer Orchestrator")
    
    # run_polling handles the event loop, signals, and graceful shutdown automatically!
    tg_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    Path("data").mkdir(exist_ok=True)
    main()
