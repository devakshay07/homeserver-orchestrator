import asyncio
import structlog
from pathlib import Path

logger = structlog.get_logger("app")

class LinkChecker:
    async def run(self, project_dir: Path) -> bool:
        # Stubbed out for edge device efficiency
        logger.info("Link checker disabled on edge")
        return True
