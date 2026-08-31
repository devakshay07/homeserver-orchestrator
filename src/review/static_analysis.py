import asyncio
import structlog
import os
from pathlib import Path

logger = structlog.get_logger("app")

class StaticAnalyzer:
    async def run(self, project_dir: Path) -> bool:
        image_name = f"sandbox-{project_dir.name.lower()}"
        logger.info("Running mypy in Docker", project_dir=str(project_dir))
        process = await asyncio.create_subprocess_exec(
            "docker", "run", "--rm", "--network", "none",
            "-u", f"{os.getuid()}:{os.getgid()}", "-v", f"{project_dir.absolute()}:/app", "-w", "/app",
            image_name, "mypy", ".",
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            if process.returncode != 0:
                logger.error("Static analysis failed", output=stdout.decode(), error=stderr.decode())
                return False
            return True
        except asyncio.TimeoutError:
            process.kill()
            logger.error("Static analysis timed out")
            return False
