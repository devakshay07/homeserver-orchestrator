import asyncio
import structlog
import os
from pathlib import Path
from typing import Tuple

from config.settings import settings

logger = structlog.get_logger("generation")

class AntigravityRunner:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = settings.agy_timeout_seconds

    async def run_command(self, project_dir: Path, instruction: str) -> Tuple[int, str, str]:
        # Write instruction to a temporary file to avoid command line length limits
        instruction_file = project_dir / ".agy_instruction.txt"
        project_dir.mkdir(parents=True, exist_ok=True)
        instruction_file.write_text(instruction)
        
        logger.info("Starting Antigravity CLI", project_dir=str(project_dir))
        
        try:
            # We assume 'agy' is installed and authenticated
            # agy --project <dir> --instruction-file <file>
            process = await asyncio.create_subprocess_exec(
                "agy", 
                # This assumes a hypothetical CLI interface for antigravity.
                # Adjust based on the actual agy CLI.
                # Assuming `agy --workspace <dir> "<instruction>"` or similar
                # Let's use `agy --dir <dir> --prompt-file <file>` as a placeholder
                "--dir", str(project_dir),
                "--prompt-file", str(instruction_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(project_dir)
            )
            
            try:
                stdout_data, stderr_data = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
                stdout_str = stdout_data.decode() if stdout_data else ""
                stderr_str = stderr_data.decode() if stderr_data else ""
                
                logger.info("Antigravity CLI completed", returncode=process.returncode)
                return process.returncode or 0, stdout_str, stderr_str
            except asyncio.TimeoutError:
                process.kill()
                logger.error("Antigravity CLI timed out")
                return -1, "", "Timeout"
        except asyncio.CancelledError:
            if 'process' in locals() and process.returncode is None:
                try:
                    process.terminate()
                except Exception:
                    pass
            logger.warning("Antigravity CLI was cancelled")
            raise
        finally:
            if 'process' in locals() and process.returncode is None:
                try:
                    process.terminate()
                except Exception:
                    pass
            if instruction_file.exists():
                instruction_file.unlink()
