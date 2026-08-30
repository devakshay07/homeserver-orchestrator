import asyncio
import structlog
from pathlib import Path

logger = structlog.get_logger("app")

class Linter:
    async def run_format(self, project_dir: Path) -> bool:
        logger.info("Running ruff format", project_dir=str(project_dir))
        process = await asyncio.create_subprocess_exec(
            str(project_dir / ".venv" / "bin" / "ruff"), "format", ".",
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        return True # formatting should not fail the build usually

    async def run_check(self, project_dir: Path) -> bool:
        logger.info("Running ruff check", project_dir=str(project_dir))
        process = await asyncio.create_subprocess_exec(
            str(project_dir / ".venv" / "bin" / "ruff"), "check", ".",
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error("Linting failed", output=stdout.decode(), error=stderr.decode())
            return False
        return True
