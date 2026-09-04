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
from tg_bot.bot import build_app
from scheduler.cron_manager import cron_manager

# Initialize logging before creating loggers
setup_logging()
logger = structlog.get_logger("app")

async def shutdown(worker, tg_app, sig: signal.Signals | None = None) -> None:
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
    asyncio.get_running_loop().stop()

def handle_exception(worker, tg_app, loop: asyncio.AbstractEventLoop, context: dict) -> None:
    msg = context.get("exception", context["message"])
    logger.error(f"Unhandled exception: {msg}")
    asyncio.create_task(shutdown(worker, tg_app))

async def main() -> None:
    from orchestrator import Orchestrator
    from gemini.triage import TriageAgent
    from maintenance.system_cleaner import SystemCleaner

    db_queue = SQLiteQueue()
    
    import scheduler.job_builder
    scheduler.job_builder.db_queue = db_queue
    
    tg_app, notifier = build_app()
    orchestrator = Orchestrator(db_queue, notifier)
    worker = TaskWorker(db_queue, orchestrator.process_task)

    tg_app.bot_data['db_queue'] = db_queue
    tg_app.bot_data['notifier'] = notifier
    tg_app.bot_data['worker'] = worker
    tg_app.bot_data['cron_manager'] = cron_manager
    tg_app.bot_data['triage_agent'] = TriageAgent(orchestrator.gemini_client)

    loop = asyncio.get_running_loop()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(worker, tg_app, s)))
        
    loop.set_exception_handler(lambda l, c: handle_exception(worker, tg_app, l, c))
    
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

    
    try:
        await notifier.send_message("🟢 HomeServer is online and ready.")
    except Exception as e:
        logger.error(f"Failed to send startup message: {e}")
    
    # Keep the main loop running
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    Path("data").mkdir(exist_ok=True)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted")
