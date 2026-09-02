import structlog
import json
from .client import GeminiClient

logger = structlog.get_logger("triage")

class TriageAgent:
    def __init__(self, client: GeminiClient):
        self.client = client

    async def analyze_request(self, text: str) -> dict:
        """
        Analyzes a user's raw message.
        Returns a JSON dict:
        {
          "needs_clarification": bool,
          "clarification_question": "string or null",
          "tasks": ["isolated task 1", "isolated task 2"]
        }
        """
        prompt = f"""You are the Triage Agent for a Personal AI Software Factory.
A user has sent the following request:
"{text}"

Analyze this request.
1. If the request is too vague to even begin architecture planning (e.g., "build an app", "make a game"), set "needs_clarification" to true and provide a short, specific "clarification_question" to ask the user on Telegram.
2. If the request is actionable enough for a senior architect to begin, set "needs_clarification" to false.
3. If the user asked for multiple distinct software projects in one message (e.g., "Build a weather API. Also build a script to scrape news."), split them into separate strings in the "tasks" array.
4. If it's just one project, put it as a single string in the "tasks" array.

Respond in RAW JSON ONLY:
{{
  "needs_clarification": true/false,
  "clarification_question": "...",
  "tasks": ["..."]
}}
"""
        try:
            response = await self.client.generate_content("gemini-1.5-flash", prompt)
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
                
            return json.loads(response)
        except Exception as e:
            logger.error("Triage failed, defaulting to single task", error=str(e))
            # Fallback
            return {
                "needs_clarification": False,
                "clarification_question": None,
                "tasks": [text]
            }
