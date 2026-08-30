import structlog
import google.generativeai as genai
from config.settings import settings

logger = structlog.get_logger("app")

class Embedder:
    def __init__(self):
        # We can reuse the first key for embeddings, or use the client wrapper
        # For simplicity, configure genai directly here
        keys = settings.get_gemini_keys()
        if keys:
            genai.configure(api_key=keys[0])

    async def get_embedding(self, text: str) -> list[float]:
        try:
            result = await genai.embed_content_async(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_document",
            )
            return result['embedding']
        except Exception as e:
            logger.error("Failed to generate embedding", error=str(e))
            return []
