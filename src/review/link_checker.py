import asyncio
import structlog
from pathlib import Path

logger = structlog.get_logger("app")

class LinkChecker:
    async def run(self, project_dir: Path) -> bool:
        readme_path = project_dir / "README.md"
        if not readme_path.exists():
            return True
            
        logger.info("Running link check", project_dir=str(project_dir))
        process = await asyncio.create_subprocess_exec(
            "markdown-link-check", str(readme_path),
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.warning("Broken links found", output=stdout.decode(), error=stderr.decode())
            return True # Non-blocking
        return True
