import asyncio
import structlog
from .client import GithubClientProvider
from config.settings import settings

logger = structlog.get_logger("git")

class PRManager:
    def __init__(self):
        self.client = GithubClientProvider.get_client()

    async def create_pr(self, repo_name: str, title: str, body: str, head: str, base: str = "main") -> str:
        logger.info("Creating PR", repo=repo_name, title=title)
        repo_full_name = f"{settings.github_owner}/{repo_name}"
        repo = await asyncio.to_thread(self.client.get_repo, repo_full_name)
        pr = await asyncio.to_thread(repo.create_pull, title=title, body=body, head=head, base=base)
        return pr.html_url

    async def merge_pr(self, repo_name: str, pr_number: int) -> bool:
        logger.info("Merging PR", repo=repo_name, pr_number=pr_number)
        repo_full_name = f"{settings.github_owner}/{repo_name}"
        repo = await asyncio.to_thread(self.client.get_repo, repo_full_name)
        pr = await asyncio.to_thread(repo.get_pull, pr_number)
        status = await asyncio.to_thread(pr.merge)
        return status.merged

    async def close_pr(self, repo_name: str, pr_number: int) -> bool:
        logger.info("Closing PR", repo=repo_name, pr_number=pr_number)
        repo_full_name = f"{settings.github_owner}/{repo_name}"
        repo = await asyncio.to_thread(self.client.get_repo, repo_full_name)
        pr = await asyncio.to_thread(repo.get_pull, pr_number)
        await asyncio.to_thread(pr.edit, state="closed")
        return True
