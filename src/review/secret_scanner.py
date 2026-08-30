import asyncio
import structlog
from pathlib import Path

logger = structlog.get_logger("app")

class SecretScanner:
    async def run(self, project_dir: Path) -> bool:
        logger.info("Running secret scan", project_dir=str(project_dir))
        process = await asyncio.create_subprocess_exec(
            "detect-secrets", "scan",
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error("Secret scan failed", output=stdout.decode(), error=stderr.decode())
            # Sometimes detect-secrets returns non-zero if it finds things or errors out
            # We assume a finding is a failure.
            return False
        return True
