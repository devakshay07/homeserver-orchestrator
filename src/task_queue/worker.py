import asyncio
import structlog
from typing import Callable, Awaitable

from .sqlite_queue import SQLiteQueue
from .models import Task, TaskStatus
from config.settings import settings

logger = structlog.get_logger("app")

class TaskWorker:
    MIN_POLL_INTERVAL = 2      # seconds when queue is active
    MAX_POLL_INTERVAL = 30     # seconds when queue is empty
    WATCHDOG_INTERVAL = 60     # seconds between watchdog checks

    def __init__(self, queue: SQLiteQueue, process_func: Callable[[Task], Awaitable[None]]):
        self.queue = queue
        self.process_func = process_func
        self._running = False
        self._task: asyncio.Task | None = None
        self._watchdog_task: asyncio.Task | None = None
        self._last_heartbeat: float = 0.0
        self._consecutive_empty_polls = 0

    async def _run(self) -> None:
        logger.info("Task worker started")
        while self._running:
            self._last_heartbeat = asyncio.get_event_loop().time()
            try:
                task = self.queue.dequeue()
                if task:
                    self._consecutive_empty_polls = 0
                    logger.info("Processing task", task_id=task.id)
                    try:
                        await self.process_func(task)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        logger.exception("Task processing failed", task_id=task.id, error=str(e))
                        task.status = TaskStatus.FAILED
                        self.queue.update_task(task)
                    poll_interval = self.MIN_POLL_INTERVAL
                else:
                    self._consecutive_empty_polls += 1
                    poll_interval = min(
                        self.MIN_POLL_INTERVAL * (2 ** min(self._consecutive_empty_polls, 4)),
                        self.MAX_POLL_INTERVAL
                    )
                    await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Error in task worker loop", error=str(e))
                await asyncio.sleep(self.MIN_POLL_INTERVAL)

    async def _watchdog(self) -> None:
        while self._running:
            await asyncio.sleep(self.WATCHDOG_INTERVAL)
            if self._task is None or self._task.done():
                logger.error("Worker task died unexpectedly — restarting")
                self._task = asyncio.create_task(self._run())

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run())
            self._watchdog_task = asyncio.create_task(self._watchdog())

    async def stop(self) -> None:
        self._running = False
        for t in (self._task, self._watchdog_task):
            if t:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
        logger.info("Task worker stopped")
