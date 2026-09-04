from .store import store
import uuid
import structlog

logger = structlog.get_logger("app")

class MemoryUpdater:
    def __init__(self):
        pass

    async def save_prompt(self, idea: str, spec: str) -> None:
        import asyncio
        await asyncio.to_thread(store.add_prompt, idea, spec, "generation")
        logger.info("Saved prompt to memory", idea_preview=idea[:30])
        
    async def save_failure(self, task_id: str, idea: str, error: str) -> None:
        import asyncio
        await asyncio.to_thread(store.add_failure, task_id, idea, error)
        logger.info("Saved failure to memory", task_id=task_id)
