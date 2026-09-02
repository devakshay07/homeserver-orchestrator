import asyncio
import structlog
import os
from pathlib import Path

logger = structlog.get_logger("app")

class TestRunner:
    async def run(self, project_dir: Path) -> bool:
        image_name = f"sandbox-{project_dir.name.lower()}"
        logger.info("Running tests in Docker", project_dir=str(project_dir))
        
        # docker run --rm --network none -v $(pwd):/app -w /app image_name pytest --tb=short
        process = await asyncio.create_subprocess_exec(
            "docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--cpus=1.0", "--memory=512m", "--pids-limit=100", "--read-only", "--tmpfs", "/tmp",
            "-u", f"{os.getuid()}:{os.getgid()}", "-v", f"{project_dir.absolute()}:/app", "-w", "/app",
            image_name, "pytest", "--tb=short",
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            if process.returncode != 0:
                logger.error("Tests failed", output=stdout.decode(), error=stderr.decode())
                return False
            return True
        except asyncio.TimeoutError:
            process.kill()
            logger.error("Tests timed out in Docker")
            return False
