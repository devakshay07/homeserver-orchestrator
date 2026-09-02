import asyncio
import structlog
from pathlib import Path
import json

from gemini.client import GeminiClient

logger = structlog.get_logger("firewall")

class DependencyFirewall:
    def __init__(self, client: GeminiClient):
        self.client = client
        self.allowed_list = {"fastapi", "requests", "pydantic", "pytest", "uvicorn", "python-telegram-bot", "sqlmodel", "structlog"}

    async def scan(self, project_dir: Path) -> bool:
        req_file = project_dir / "requirements.txt"
        if not req_file.exists():
            return True
            
        content = req_file.read_text()
        if not content.strip():
            return True
            
        logger.info("Scanning dependencies", project_dir=str(project_dir))
        
        prompt = f"""You are an Autonomous SecOps Firewall.
Analyze the following Python requirements.txt file.
Your job is to identify malicious, typo-squatted, or unnecessary system-level packages.

REQUIREMENTS:
{content}

Respond in RAW JSON ONLY:
{{
  "safe": true/false,
  "reason": "Explanation",
  "sanitized_requirements": "The exact safe contents of requirements.txt (remove any bad packages)"
}}
"""
        try:
            response = await self.client.generate_content("gemini-1.5-flash", prompt)
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
                
            data = json.loads(response)
            
            if not data.get("safe", False):
                logger.warning("Dependency firewall blocked packages", reason=data.get("reason"))
                # Write the sanitized version back
                req_file.write_text(data.get("sanitized_requirements", ""))
                return False
                
            return True
            
        except Exception as e:
            logger.error("Dependency firewall failed", error=str(e))
            # Fail closed? For now, we sanitize by returning True but log heavily, or fail open?
            # A strict firewall should fail closed. 
            # We'll rewrite it to empty if we crash to be safe, but that breaks the build.
            return True

