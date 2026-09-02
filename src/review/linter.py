import asyncio
import structlog
import os
from pathlib import Path

logger = structlog.get_logger("app")

class Linter:
    async def run_format(self, project_dir: Path) -> bool:
        image_name = f"sandbox-{project_dir.name.lower()}"
        logger.info("Running ruff format in Docker", project_dir=str(project_dir))
        process = await asyncio.create_subprocess_exec(
            "docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--cpus=1.0", "--memory=512m", "--pids-limit=100", "--read-only", "--tmpfs", "/tmp",
            # We need to run format as the current user so it can write back to the host filesystem
            # Wait, `ruff format` modifies files. We must pass --user $(id -u):$(id -g) but that's shell logic.
            # We can use os.getuid() and os.getgid().
            "-u", f"{os.getuid()}:{os.getgid()}", "-v", f"{project_dir.absolute()}:/app", "-w", "/app",
            image_name, "ruff", "format", ".",
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            await asyncio.wait_for(process.communicate(), timeout=120)
            return True
        except asyncio.TimeoutError:
            process.kill()
            return False

    async def run_check(self, project_dir: Path) -> bool:
        image_name = f"sandbox-{project_dir.name.lower()}"
        logger.info("Running ruff check in Docker", project_dir=str(project_dir))
        process = await asyncio.create_subprocess_exec(
            "docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--cpus=1.0", "--memory=512m", "--pids-limit=100", "--read-only", "--tmpfs", "/tmp",
            "-u", f"{os.getuid()}:{os.getgid()}", "-v", f"{project_dir.absolute()}:/app", "-w", "/app",
            image_name, "ruff", "check", ".",
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
            if process.returncode != 0:
                logger.error("Linting failed", output=stdout.decode(), error=stderr.decode())
                return False
            return True
        except asyncio.TimeoutError:
            process.kill()
            return False
