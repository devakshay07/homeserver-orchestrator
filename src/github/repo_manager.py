import asyncio
import structlog
from pathlib import Path
import os

logger = structlog.get_logger("git")

class RepoManager:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)

    async def _run_git(self, repo_dir: Path, *args) -> bool:
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        process = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=str(repo_dir),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            cmd_str = ' '.join(args)
            # Mask possible token in URL
            import re
            cmd_str = re.sub(r'x-access-token:[^@]+@', 'x-access-token:***@', cmd_str)
            logger.error(f"Git command failed: git {cmd_str}", error=stderr.decode())
            return False
        return True

    async def init_and_commit(self, repo_dir: Path, branch_name: str, message: str) -> bool:
        logger.info("Initializing git repository", repo_dir=str(repo_dir))
        
        if not (repo_dir / ".git").exists():
            if not await self._run_git(repo_dir, "init"): return False
            if not await self._run_git(repo_dir, "checkout", "-b", "main"): return False
            if not await self._run_git(repo_dir, "add", "."): return False
            if not await self._run_git(repo_dir, "commit", "-m", "Initial commit"): return False
            
        if not await self._run_git(repo_dir, "checkout", "-b", branch_name): return False
        if not await self._run_git(repo_dir, "add", "."): return False
        if not await self._run_git(repo_dir, "commit", "-m", message): return False
        
        return True
        
    async def push_branch(self, repo_dir: Path, remote_url: str, branch_name: str) -> bool:
        logger.info("Pushing branch", branch_name=branch_name)
        # Adding remote if not exists
        await self._run_git(repo_dir, "remote", "add", "origin", remote_url)
        return await self._run_git(repo_dir, "push", "-u", "origin", branch_name)
