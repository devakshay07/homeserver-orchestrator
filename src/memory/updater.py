from .store import store
from .embedder import Embedder
import uuid
import structlog

logger = structlog.get_logger("app")

class MemoryUpdater:
    def __init__(self):
        self.embedder = Embedder()

    async def save_prompt(self, idea: str, spec: str) -> None:
        text = f"Idea: {idea}\n\nSpec: {spec}"
        embedding = await self.embedder.get_embedding(text)
        if not embedding:
            return
            
        doc_id = str(uuid.uuid4())
        store.prompts.add(
            embeddings=[embedding],
            documents=[text],
            metadatas=[{"type": "generation", "idea": idea}],
            ids=[doc_id]
        )
        logger.info("Saved prompt to memory", doc_id=doc_id)
        
    async def save_failure(self, task_id: str, idea: str, error: str) -> None:
        text = f"Idea: {idea}\n\nError: {error}"
        embedding = await self.embedder.get_embedding(text)
        if not embedding:
            return
            
        store.failures.add(
            embeddings=[embedding],
            documents=[text],
            metadatas=[{"task_id": task_id}],
            ids=[task_id]
        )
        logger.info("Saved failure to memory", task_id=task_id)
