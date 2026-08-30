import asyncio
import structlog
from pathlib import Path

logger = structlog.get_logger("app")

class StaticAnalyzer:
    async def run(self, project_dir: Path) -> bool:
        # Assuming python project for now. Adjust based on language detection if needed.
        logger.info("Running mypy", project_dir=str(project_dir))
        process = await asyncio.create_subprocess_exec(
            str(project_dir / ".venv" / "bin" / "mypy"), ".",
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error("Static analysis failed", output=stdout.decode(), error=stderr.decode())
            return False
        return True
