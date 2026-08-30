from github import Github, Auth
from config.settings import settings
import structlog

logger = structlog.get_logger("git")

class GithubClientProvider:
    @staticmethod
    def get_client() -> Github:
        if settings.github_app_id and settings.github_app_private_key_path and settings.github_app_private_key_path.strip():
            logger.info("Authenticating with GitHub App")
            with open(settings.github_app_private_key_path, 'r') as f:
                private_key = f.read()
            auth = Auth.AppAuth(settings.github_app_id, private_key)
            return Github(auth=auth)
        elif settings.github_pat and settings.github_pat.get_secret_value().strip():
            logger.info("Authenticating with GitHub PAT")
            auth = Auth.Token(settings.github_pat.get_secret_value())
            return Github(auth=auth)
        else:
            raise ValueError("No GitHub authentication provided")
