from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import structlog
from pathlib import Path

from config.settings import settings

logger = structlog.get_logger("app")

class CronManager:
    def __init__(self):
        db_url = f"sqlite:///{str(settings.db_path).replace('.sqlite', '_cron.sqlite')}"
        jobstores = {
            'default': SQLAlchemyJobStore(url=db_url, tablename='apscheduler_jobs')
        }
        
        timezone = settings.timezone
            
        self.scheduler = AsyncIOScheduler(jobstores=jobstores, timezone=str(timezone))

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
            
    def get_jobs(self):
        return self.scheduler.get_jobs()
        
    def remove_job(self, job_id: str) -> bool:
        try:
            self.scheduler.remove_job(job_id)
            return True
        except Exception as e:
            logger.error("Failed to remove job", job_id=job_id, error=str(e))
            return False
            
    def pause_job(self, job_id: str) -> bool:
        try:
            self.scheduler.pause_job(job_id)
            return True
        except Exception as e:
            return False
            
    def resume_job(self, job_id: str) -> bool:
        try:
            self.scheduler.resume_job(job_id)
            return True
        except Exception as e:
            return False

cron_manager = CronManager()
