import asyncio
import structlog
import json
from pathlib import Path

logger = structlog.get_logger("app")

class SecretScanner:
    async def run(self, project_dir: Path) -> bool:
        logger.info("Running secret scan", project_dir=str(project_dir))
        venv_bin = project_dir / ".venv" / "bin"
        executable = str(venv_bin / "detect-secrets")
        if not (venv_bin / "detect-secrets").exists():
            executable = "detect-secrets"
            
        process = await asyncio.create_subprocess_exec(
            executable, "scan",
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            # Command failed completely
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
