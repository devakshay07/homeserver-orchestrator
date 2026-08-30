import structlog
from .client import GeminiClient
from config.settings import settings

logger = structlog.get_logger("generation")

class ReadmeReviewer:
    def __init__(self, client: GeminiClient):
        self.client = client

    async def review(self, readme_content: str) -> str:
        system_instruction = (
            "You are an expert Technical Writer and Code Reviewer. Review the following README.md. "
            "Identify any inaccuracies, missing setup instructions, missing API docs, missing environment variables, "
            "or lack of examples. "
            "Provide specific, actionable improvements or rewrite sections to make it production-ready."
        )
        
        logger.info("Reviewing README")
        improvements = await self.client.generate_content(
            model_name=settings.gemini_model_review,
            prompt=readme_content,
            system_instruction=system_instruction
        )
        return improvements
