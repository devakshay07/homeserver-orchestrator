from .store import store
from .embedder import Embedder
import structlog

logger = structlog.get_logger("app")

class Retriever:
    def __init__(self):
        self.embedder = Embedder()

    async def search_prompts(self, query: str, n_results: int = 3) -> list[str]:
        embedding = await self.embedder.get_embedding(query)
        if not embedding:
            return []
            
        results = store.prompts.query(
            query_embeddings=[embedding],
            n_results=n_results
        )
        
        documents = results.get("documents")
        if documents and len(documents) > 0:
            return documents[0]
        return []
