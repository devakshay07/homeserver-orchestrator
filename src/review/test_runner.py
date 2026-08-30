import asyncio
import structlog
from pathlib import Path

logger = structlog.get_logger("app")

class TestRunner:
    async def run(self, project_dir: Path) -> bool:
        logger.info("Running tests", project_dir=str(project_dir))
        process = await asyncio.create_subprocess_exec(
            str(project_dir / ".venv" / "bin" / "pytest"), "--tb=short",
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error("Tests failed", output=stdout.decode(), error=stderr.decode())
            return False
        return True
