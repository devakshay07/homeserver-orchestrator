import asyncio
import structlog
import os
import json
from pathlib import Path

logger = structlog.get_logger("app")

class SecretScanner:
    async def run(self, project_dir: Path) -> bool:
        image_name = f"sandbox-{project_dir.name.lower()}"
        logger.info("Running secret scan in Docker", project_dir=str(project_dir))
        process = await asyncio.create_subprocess_exec(
            "docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--cpus=1.0", "--memory=512m", "--pids-limit=100", "--read-only", "--tmpfs", "/tmp",
            "-u", f"{os.getuid()}:{os.getgid()}", "-v", f"{project_dir.absolute()}:/app", "-w", "/app",
            image_name, "detect-secrets", "scan",
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            if process.returncode != 0:
                logger.error("Secret scan command failed", error=stderr.decode())
                return False
                
            try:
                report = json.loads(stdout.decode())
                results = report.get("results", {})
                if results:
                    logger.error("Secrets found in generated code", results=results)
                    return False
                return True
            except json.JSONDecodeError:
                logger.error("Failed to parse detect-secrets output", output=stdout.decode())
                return False
        except asyncio.TimeoutError:
            process.kill()
            logger.error("Secret scan timed out")
            return False
