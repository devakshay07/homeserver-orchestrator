from .store import store
import structlog

logger = structlog.get_logger("app")

class Retriever:
    def __init__(self):
        pass

    async def search_prompts(self, query: str, n_results: int = 3) -> list[str]:
        import asyncio
        return await asyncio.to_thread(store.search_prompts, query, limit=n_results)
