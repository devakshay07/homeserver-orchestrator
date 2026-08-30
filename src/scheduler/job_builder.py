import structlog
from .cron_manager import cron_manager
from queue.sqlite_queue import SQLiteQueue
from queue.models import TaskStatus

logger = structlog.get_logger("app")
db_queue = SQLiteQueue()

def run_scheduled_build(idea: str):
    logger.info("Running scheduled build", idea=idea)
    task = db_queue.enqueue({"type": "build", "idea": idea})
    logger.info("Queued scheduled task", task_id=task.id)

class JobBuilder:
    @staticmethod
    def add_daily_job(time_str: str, idea: str) -> str:
        hour, minute = map(int, time_str.split(':'))
        job = cron_manager.scheduler.add_job(
            run_scheduled_build,
            'cron',
            hour=hour,
            minute=minute,
            args=[idea]
        )
        return job.id
        
    @staticmethod
    def add_weekly_job(day_of_week: str, time_str: str, idea: str) -> str:
        hour, minute = map(int, time_str.split(':'))
        job = cron_manager.scheduler.add_job(
            run_scheduled_build,
            'cron',
            day_of_week=day_of_week.lower()[:3], # mon, tue, etc.
            hour=hour,
            minute=minute,
            args=[idea]
        )
        return job.id
