import asyncio
import structlog
from pathlib import Path

from config.settings import settings
from task_queue.models import Task, TaskStatus, CheckpointKey
from monitoring.metrics import StageTimer, log_disk_usage
from task_queue.sqlite_queue import SQLiteQueue
from telegram.notifier import TelegramNotifier

from gemini.client import GeminiClient, GeminiQuotaExhausted, GeminiContentBlocked
from gemini.spec_generator import SpecGenerator
from gemini.readme_reviewer import ReadmeReviewer
from antigravity.runner import AntigravityRunner
from antigravity.prompt_builder import PromptBuilder
from review.quality_gate import QualityGate
from github.repo_manager import RepoManager
from github.pr_manager import PRManager
from memory.retriever import Retriever
from memory.updater import MemoryUpdater
from storage.lifecycle import StorageLifecycle
import re

logger = structlog.get_logger("app")

class Orchestrator:
    def __init__(self, db_queue: SQLiteQueue, notifier: TelegramNotifier):
        self.db_queue = db_queue
        self.notifier = notifier
        self.gemini_client = GeminiClient()
        self.spec_generator = SpecGenerator(self.gemini_client)
        self.readme_reviewer = ReadmeReviewer(self.gemini_client)
        self.agy_runner = AntigravityRunner(settings.workspace_dir)
        self.quality_gate = QualityGate()
        self.repo_manager = RepoManager(settings.workspace_dir)
        self.pr_manager = PRManager()
        self.memory_updater = MemoryUpdater()
        self.storage = StorageLifecycle(settings.workspace_dir, settings.disk_min_free_gb, settings.workspace_max_age_days)
        
    def _extract_repo_name(self, spec: str, task_id: str) -> str:
        match = re.search(r"# Project:\s*([a-zA-Z0-9_-]+)", spec)
        if match:
            return match.group(1).lower()
        return f"generated-project-{task_id[:8]}"


    async def process_task(self, task: Task) -> None:
        logger.info(f"Processing task: {task.id}", payload=task.payload)
        idea = task.payload.get('idea', '')
        
        try:

            cp = task.checkpoint or {}

            ok, free_gb = self.storage.check_disk_space()
            if not ok:
                raise Exception(f"Insufficient disk space: {free_gb:.1f} GB free, {settings.disk_min_free_gb} GB required")
            if not cp:
                await self.notifier.send_message(f"🚀 Started generating: _{idea}_")
            else:
                await self.notifier.send_message(f"🔄 Resuming task: _{idea}_ from checkpoint")
            
            # 1. Spec Generation\n            log_disk_usage(settings.workspace_dir)
            if not cp.get(CheckpointKey.SPEC_DONE):
                async with StageTimer("spec_generation", task.id):
                    await self.notifier.send_message(f"🧠 Generating specification...")
                spec = await self.spec_generator.generate_spec(idea)
                await self.memory_updater.save_prompt(idea, spec)
                
                repo_name = self._extract_repo_name(spec, task.id)
                project_dir = str(Path(settings.workspace_dir) / f"{repo_name}_{task.id[:8]}")
                
                cp[CheckpointKey.SPEC_TEXT] = spec
                cp[CheckpointKey.REPO_NAME] = repo_name
                cp[CheckpointKey.PROJECT_DIR] = project_dir
                cp[CheckpointKey.SPEC_DONE] = True
                task.checkpoint = cp
                self.db_queue.update_task(task)
            else:
                spec = cp[CheckpointKey.SPEC_TEXT]
                repo_name = cp[CheckpointKey.REPO_NAME]
                project_dir = cp[CheckpointKey.PROJECT_DIR]

            project_dir_path = Path(project_dir)
            
            # 2. Antigravity Generation
            if not cp.get(CheckpointKey.AGY_DONE):
                async with StageTimer("agy_generation", task.id):
                    await self.notifier.send_message(f"⚙️ Running Antigravity CLI for `{repo_name}`...")
                instruction = PromptBuilder.build_generation_prompt(spec)
                ret_code, stdout, stderr = await self.agy_runner.run_command(project_dir_path, instruction)
                
                if ret_code != 0:
                    raise Exception(f"Antigravity CLI failed: {stderr}")
                cp[CheckpointKey.AGY_DONE] = True
                task.checkpoint = cp
                self.db_queue.update_task(task)

            # 2.5. README Review
            if not cp.get(CheckpointKey.README_DONE):
                async with StageTimer("readme_review", task.id):
                    readme_path = project_dir_path / "README.md"
                if readme_path.exists():
                    await self.notifier.send_message(f"📝 Reviewing README...")
                    readme_content = readme_path.read_text()
                    improvements = await self.readme_reviewer.review(readme_content)
                    if improvements and len(improvements) > 20:
                        instruction = PromptBuilder.build_readme_update_prompt(improvements)
                        await self.agy_runner.run_command(project_dir_path, instruction)
                cp[CheckpointKey.README_DONE] = True
                task.checkpoint = cp
                self.db_queue.update_task(task)

            # 3. Quality Gate
            if not cp.get(CheckpointKey.QUALITY_DONE):
                async with StageTimer("quality_gate", task.id):
                    await self.notifier.send_message(f"🔍 Running Quality Gate...")
                report = await self.quality_gate.run_all(project_dir_path)
                await self.notifier.send_message(f"🔍 Quality Gate results:\n\n{report.summary()}")

                if report.hard_failed:
                    raise Exception("Quality Gate: hard failure — pipeline aborted")
                cp[CheckpointKey.QUALITY_DONE] = True
                task.checkpoint = cp
                self.db_queue.update_task(task)
                
            # 4. GitHub PR
            branch_name = cp.get(CheckpointKey.GIT_BRANCH)
            if not branch_name:
                branch_name = f"feature/{task.id[:8]}"
                cp[CheckpointKey.GIT_BRANCH] = branch_name
                task.checkpoint = cp
                self.db_queue.update_task(task)

            if not cp.get(CheckpointKey.GIT_PUSHED):
                await self.notifier.send_message(f"🐙 Creating GitHub PR...")
                await self.repo_manager.init_and_commit(project_dir_path, branch_name, f"Generate {repo_name}")
                
                # Remote creation logic
                try:

                    await asyncio.to_thread(self.pr_manager.client.get_repo, f"{settings.github_owner}/{repo_name}")
                except Exception:
                    user = await asyncio.to_thread(self.pr_manager.client.get_user)
                    await asyncio.to_thread(user.create_repo, repo_name, private=True)
                    
                remote_url = f"https://github.com/{settings.github_owner}/{repo_name}.git"
                token = settings.github_pat.get_secret_value() if settings.github_pat else None
                
                if not await self.repo_manager.push_branch(project_dir_path, remote_url, branch_name, token):
                    raise Exception("Failed to push to GitHub")
                    
                cp[CheckpointKey.GIT_PUSHED] = True
                task.checkpoint = cp
                self.db_queue.update_task(task)

            pr_url = cp.get(CheckpointKey.PR_URL)
            if not pr_url:
                pr_url = await self.pr_manager.create_pr(
                    repo_name, 
                    f"Generated Feature: {idea[:50]}", 
                    f"Auto-generated by HomeServer\n\nTask ID: {task.id}", 
                    branch_name
                )
                cp[CheckpointKey.PR_URL] = pr_url
                task.checkpoint = cp
                self.db_queue.update_task(task)
            
            task.status = TaskStatus.AWAITING_APPROVAL
            task.payload['pr_url'] = pr_url
            task.payload['repo_name'] = repo_name
            self.db_queue.update_task(task)
            
            await self.notifier.send_pr_notification(
                f"✅ PR ready for task `{task.id}`\n\nFeature: {idea}\n\n[View PR]({pr_url})", 
                task.id
            )
            logger.info(f"Finished processing task: {task.id}")
            self.storage.cleanup_old_workspaces(self.db_queue)


        except GeminiQuotaExhausted as e:
            logger.exception(f"Task {task.id} failed (Quota)", error=str(e))
            task.status = TaskStatus.FAILED
            task.payload['error'] = str(e)
            self.db_queue.update_task(task)
            await self.memory_updater.save_failure(task.id, idea, str(e))
            await self.notifier.send_message(f"❌ Task `{task.id}` failed (API Quota Exhausted).\n\nError: {str(e)}")
            self.storage.cleanup_old_workspaces(self.db_queue)
            
        except GeminiContentBlocked as e:
            logger.exception(f"Task {task.id} failed (Blocked)", error=str(e))
            task.status = TaskStatus.FAILED
            task.payload['error'] = str(e)
            self.db_queue.update_task(task)
            await self.memory_updater.save_failure(task.id, idea, str(e))
            await self.notifier.send_message(f"❌ Task `{task.id}` failed (Content Blocked).\n\nError: {str(e)}")
            self.storage.cleanup_old_workspaces(self.db_queue)
            
        except Exception as e:
            pass
            logger.exception(f"Task {task.id} failed", error=str(e))
            task.status = TaskStatus.FAILED
            task.payload['error'] = str(e)
            self.db_queue.update_task(task)
            await self.memory_updater.save_failure(task.id, idea, str(e))
            await self.notifier.send_message(f"❌ Task `{task.id}` failed.\n\nError: {str(e)}")
            self.storage.cleanup_old_workspaces(self.db_queue)

