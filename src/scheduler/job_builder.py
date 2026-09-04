import structlog
from .cron_manager import cron_manager
from task_queue.sqlite_queue import SQLiteQueue
from task_queue.models import TaskStatus

logger = structlog.get_logger("app")
db_queue = None

import asyncio
from gemini.triage import TriageAgent
from gemini.client import GeminiClient

async def run_scheduled_build(idea: str):
    if db_queue is None:
        logger.error("Skipping scheduled build: db_queue is not initialized")
        return
        
    logger.info("Running scheduled build via TriageAgent", idea=idea)
    
    try:
        # Instantiate lightweight triage agent
        client = GeminiClient()
        triage_agent = TriageAgent(client)
        
        analysis = await triage_agent.analyze_request(idea)
        tasks_to_queue = analysis.get("tasks", [idea])
        
        if analysis.get("needs_clarification"):
            logger.warning("Scheduled job is ambiguous, queueing fallback", question=analysis.get("clarification_question"))
            # Fallback to just running the raw idea
            tasks_to_queue = [idea]
            
        for t_idea in tasks_to_queue:
            task = db_queue.enqueue({"type": "build", "idea": t_idea}, priority=10)
            logger.info("Queued scheduled sub-task", task_id=task.id, idea=t_idea)
            
    except Exception as e:
        logger.error("Triage failed for scheduled job, using fallback", error=str(e))
        task = db_queue.enqueue({"type": "build", "idea": idea}, priority=10)
        logger.info("Queued scheduled task", task_id=task.id)


class JobBuilder:
    @staticmethod
    def add_daily_job(time_str: str, idea: str) -> str:
        import re
        if not re.match(r'^\d{2}:\d{2}$', time_str):
            raise ValueError("Time must be in HH:MM format (e.g., 03:00)")
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
