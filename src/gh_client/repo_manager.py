import asyncio
import structlog
from pathlib import Path
import os
import re

logger = structlog.get_logger("git")

class RepoManager:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)

    async def _run_git(self, repo_dir: Path, *args) -> tuple[bool, str]:
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
            cmd_str = re.sub(r'x-access-token:[^@]+@', 'x-access-token:***@', cmd_str)
            cmd_str = re.sub(r'bearer\s+[^\s]+', 'bearer ***', cmd_str, flags=re.IGNORECASE)
            err_msg = stderr.decode().strip()
            logger.error(f"Git command failed: git {cmd_str}", error=err_msg)
            return False, err_msg
        return True, stdout.decode()

    async def _run_git_raise(self, repo_dir: Path, *args) -> str:
        ok, out = await self._run_git(repo_dir, *args)
        if not ok:
            cmd_str = ' '.join(args)
            cmd_str = re.sub(r'bearer\s+[^\s"\'\\]+', 'bearer ***', cmd_str, flags=re.IGNORECASE)
            raise Exception(f"Git operation failed: git {cmd_str[:50]} ... -> {out}")
        return out

    async def init_and_commit(self, repo_dir: Path, branch_name: str, message: str) -> None:
        logger.info("Initializing git repository", repo_dir=str(repo_dir))
        
        # Configure local git user if not present
        await self._run_git(repo_dir, "config", "user.name", "HomeServer Orchestrator")
        await self._run_git(repo_dir, "config", "user.email", "bot@homeserver.local")

        if not (repo_dir / ".git").exists():
            await self._run_git_raise(repo_dir, "init")
            await self._run_git_raise(repo_dir, "checkout", "-b", "main")
            await self._run_git_raise(repo_dir, "add", ".")
            await self._run_git(repo_dir, "commit", "-m", "Initial commit") # might be nothing to commit
            
        ok, branches = await self._run_git(repo_dir, "branch")
        branch_list = [b.strip().lstrip("* ") for b in branches.splitlines()]
        if branch_name in branch_list:
            await self._run_git_raise(repo_dir, "checkout", branch_name)
        else:
            await self._run_git_raise(repo_dir, "checkout", "-b", branch_name)
            
        await self._run_git_raise(repo_dir, "add", ".")
        await self._run_git(repo_dir, "commit", "-m", message) # Ignore failure if no changes
        
    async def push_branch(self, repo_dir: Path, remote_url: str, branch_name: str, token: str = None) -> bool:
        logger.info("Pushing branch", branch_name=branch_name)
        ok, remotes = await self._run_git(repo_dir, "remote")
        if "origin" in remotes:
            await self._run_git(repo_dir, "remote", "set-url", "origin", remote_url)
        else:
            await self._run_git(repo_dir, "remote", "add", "origin", remote_url)
            
        try:
            if token:
                await self._run_git_raise(repo_dir, "-c", f"http.extraHeader=AUTHORIZATION: bearer {token}", "push", "-u", "origin", branch_name)
            else:
                await self._run_git_raise(repo_dir, "push", "-u", "origin", branch_name)
            return True
        except Exception as e:
            logger.error("Push failed", error=str(e))
            return False
