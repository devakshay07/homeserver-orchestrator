import asyncio
import structlog
import signal
import sys
from pathlib import Path

from config.settings import settings
from app_logging.setup import setup_logging
from task_queue.sqlite_queue import SQLiteQueue
from task_queue.worker import TaskWorker
from task_queue.models import Task, TaskStatus
from telegram.bot import build_app
from scheduler.cron_manager import cron_manager

# Initialize logging before creating loggers
setup_logging()
logger = structlog.get_logger("app")

# Global instances
db_queue = SQLiteQueue()
tg_app, notifier = build_app()

from orchestrator import Orchestrator
from gemini.triage import TriageAgent
from maintenance.system_cleaner import SystemCleaner
orchestrator = Orchestrator(db_queue, notifier)

worker = TaskWorker(db_queue, orchestrator.process_task)

# Inject dependencies into telegram bot context
tg_app.bot_data['db_queue'] = db_queue
tg_app.bot_data['notifier'] = notifier
tg_app.bot_data['worker'] = worker
tg_app.bot_data['cron_manager'] = cron_manager
tg_app.bot_data['triage_agent'] = TriageAgent(orchestrator.gemini_client)

async def shutdown(sig: signal.Signals | None = None) -> None:
    if sig:
        logger.info(f"Received exit signal {sig.name}...")
    
    await worker.stop()
    cron_manager.stop()
    await tg_app.stop()
    await tg_app.shutdown()
    
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    
    logger.info("Canceling outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info("Shutdown complete")
    asyncio.get_event_loop().stop()

def handle_exception(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    msg = context.get("exception", context["message"])
    logger.error(f"Unhandled exception: {msg}")
    asyncio.create_task(shutdown())

async def main() -> None:
    loop = asyncio.get_running_loop()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s)))
        
    loop.set_exception_handler(handle_exception)
    
    logger.info("Starting HomeServer Orchestrator")
    
    # Start Telegram Bot
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()
    

    # Start Worker
    worker.start()
    cron_manager.start()
    
    # Schedule Nightly Maintenance
    cleaner = SystemCleaner(notifier)
    cron_manager.scheduler.add_job(
        cleaner.run_nightly_maintenance,
        'cron',
        hour=3,
        minute=0,
        id='nightly_system_maintenance',
        replace_existing=True
    )

    
    await notifier.send_message("🟢 HomeServer is online and ready.")
    
    # Keep the main loop running
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    Path("data").mkdir(exist_ok=True)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted")
