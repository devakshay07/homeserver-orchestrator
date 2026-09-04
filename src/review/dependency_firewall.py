from config.settings import settings
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
            response = await self.client.generate_content(settings.gemini_model_spec, prompt)
            response = response.strip()
            
            import re
            match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            if match:
                response = match.group(1).strip()
                
            data = json.loads(response, strict=False)
            
            if not data.get("safe", False):
                logger.warning("Dependency firewall blocked packages", reason=data.get("reason"))
                # Write the sanitized version back
                req_file.write_text(data.get("sanitized_requirements", ""))
                return False
                
            return True
            
        except Exception as e:
            logger.error("Dependency firewall API failed, falling back to local allowed_list", error=str(e))
            # Local fallback: check if all requirements are in allowed_list
            lines = content.splitlines()
            safe_lines = []
            all_safe = True
            for line in lines:
                pkg = line.split("==")[0].strip().lower()
                if not pkg or pkg.startswith("#"):
                    continue
                if pkg in self.allowed_list:
                    safe_lines.append(line)
                else:
                    logger.warning("Local firewall blocked unknown package", package=pkg)
                    all_safe = False
                    
            if not all_safe:
                req_file.write_text("\n".join(safe_lines))
                return False
            return True

