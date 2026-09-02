import asyncio
import structlog
from pathlib import Path
import re
from enum import Enum

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

logger = structlog.get_logger("app")

class JobState(str, Enum):
    PLANNING = "PLANNING"
    GENERATING = "GENERATING"
    TESTING = "TESTING"
    DEBUGGING = "DEBUGGING"
    REVIEW = "REVIEW"
    PR_CREATED = "PR_CREATED"
    COMPLETED = "COMPLETED"

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
            
            state = cp.get("job_state", JobState.PLANNING.value)
            
            if not cp:
                await self.notifier.send_message(f"🚀 Started generating: _{idea}_")
            else:
                await self.notifier.send_message(f"🔄 Resuming task: _{idea}_ from {state}")
                
            while state != JobState.COMPLETED.value:
                if state == JobState.PLANNING.value:
                    state = await self._handle_planning(task, cp, idea)
                elif state == JobState.GENERATING.value:
                    state = await self._handle_generating(task, cp)
                elif state == JobState.TESTING.value:
                    state = await self._handle_testing(task, cp)
                elif state == JobState.DEBUGGING.value:
                    state = await self._handle_debugging(task, cp)
                elif state == JobState.REVIEW.value:
                    state = await self._handle_review(task, cp)
                elif state == JobState.PR_CREATED.value:
                    state = await self._handle_pr_created(task, cp, idea)
                
                cp["job_state"] = state
                task.checkpoint = cp
                self.db_queue.update_task(task)

            self.storage.cleanup_old_workspaces(self.db_queue)

        except GeminiQuotaExhausted as e:
            logger.exception(f"Task {task.id} failed (Quota)", error=str(e))
            await self._fail_task(task, idea, str(e), "API Quota Exhausted")
        except GeminiContentBlocked as e:
            logger.exception(f"Task {task.id} failed (Blocked)", error=str(e))
            await self._fail_task(task, idea, str(e), "Content Blocked")
        except Exception as e:
            logger.exception(f"Task {task.id} failed", error=str(e))
            await self._fail_task(task, idea, str(e), "General Failure")

    async def _fail_task(self, task: Task, idea: str, err_str: str, reason: str):
        task.status = TaskStatus.FAILED
        task.payload['error'] = err_str
        self.db_queue.update_task(task)
        await self.memory_updater.save_failure(task.id, idea, err_str)
        await self.notifier.send_message(f"❌ Task `{task.id}` failed ({reason}).\n\nError: {err_str}")
        self.storage.cleanup_old_workspaces(self.db_queue)

    async def _handle_planning(self, task: Task, cp: dict, idea: str) -> str:
        async with StageTimer("spec_generation", task.id):
            await self.notifier.send_message("🧠 Generating architecture & specification...")
        spec = await self.spec_generator.generate_spec(idea)
        await self.memory_updater.save_prompt(idea, spec)
        
        repo_name = self._extract_repo_name(spec, task.id)
        project_dir = str(Path(settings.workspace_dir) / f"{repo_name}_{task.id[:8]}")
        
        cp[CheckpointKey.SPEC_TEXT] = spec
        cp[CheckpointKey.REPO_NAME] = repo_name
        cp[CheckpointKey.PROJECT_DIR] = project_dir
        return JobState.GENERATING.value

    async def _handle_generating(self, task: Task, cp: dict) -> str:
        repo_name = cp[CheckpointKey.REPO_NAME]
        project_dir = Path(cp[CheckpointKey.PROJECT_DIR])
        spec = cp[CheckpointKey.SPEC_TEXT]
        
        async with StageTimer("agy_generation", task.id):
            await self.notifier.send_message(f"⚙️ Generating Code for `{repo_name}`...")
        
        instruction = PromptBuilder.build_generation_prompt(spec)
        ret_code, stdout, stderr = await self.agy_runner.run_command(project_dir, instruction)
        
        if ret_code != 0:
            raise Exception(f"Antigravity CLI failed: {stderr}")
            
        return JobState.TESTING.value

    async def _handle_testing(self, task: Task, cp: dict) -> str:
        project_dir = Path(cp[CheckpointKey.PROJECT_DIR])
        
        async with StageTimer("quality_gate", task.id):
            await self.notifier.send_message("🔍 Running Docker Sandboxed Quality Gate...")
        
        report = await self.quality_gate.run_all(project_dir)
        
        if report.hard_failed:
            cp["test_failures"] = report.summary()
            await self.notifier.send_message(f"⚠️ Quality Gate Failed:\n\n{report.summary()}")
            return JobState.DEBUGGING.value
            
        await self.notifier.send_message(f"✅ Quality Gate Passed!")
        return JobState.REVIEW.value

    async def _handle_debugging(self, task: Task, cp: dict) -> str:
        iters = cp.get("debug_iterations", 0)
        if iters >= 3:
            raise Exception("Quality Gate failed after 3 debug iterations.")
            
        iters += 1
        cp["debug_iterations"] = iters
        
        repo_name = cp[CheckpointKey.REPO_NAME]
        project_dir = Path(cp[CheckpointKey.PROJECT_DIR])
        failures = cp.get("test_failures", "Unknown errors")
        
        await self.notifier.send_message(f"🐛 Debugging issues (Attempt {iters}/3)...")
        
        # We tell agy to fix the code
        instruction = f"The previous tests failed with the following report:\n\n{failures}\n\nPlease analyze the codebase, identify the bug, and modify the files to fix it."
        ret_code, stdout, stderr = await self.agy_runner.run_command(project_dir, instruction)
        
        if ret_code != 0:
            raise Exception(f"Antigravity Debugging failed: {stderr}")
            
        return JobState.TESTING.value

    async def _handle_review(self, task: Task, cp: dict) -> str:
        project_dir = Path(cp[CheckpointKey.PROJECT_DIR])
        
        async with StageTimer("readme_review", task.id):
            readme_path = project_dir / "README.md"
        if readme_path.exists():
            await self.notifier.send_message("📝 Reviewing README...")
            readme_content = readme_path.read_text()
            improvements = await self.readme_reviewer.review(readme_content)
            if improvements and len(improvements) > 20:
                instruction = PromptBuilder.build_readme_update_prompt(improvements)
                await self.agy_runner.run_command(project_dir, instruction)
                
        return JobState.PR_CREATED.value

    async def _handle_pr_created(self, task: Task, cp: dict, idea: str) -> str:
        repo_name = cp[CheckpointKey.REPO_NAME]
        project_dir = Path(cp[CheckpointKey.PROJECT_DIR])
        branch_name = cp.get(CheckpointKey.GIT_BRANCH, f"feature/{task.id[:8]}")
        cp[CheckpointKey.GIT_BRANCH] = branch_name
        
        if not cp.get(CheckpointKey.GIT_PUSHED):
            await self.notifier.send_message("🐙 Pushing to GitHub...")
            await self.repo_manager.init_and_commit(project_dir, branch_name, f"Generate {repo_name}")
            
            try:
                await asyncio.to_thread(self.pr_manager.client.get_repo, f"{settings.github_owner}/{repo_name}")
            except Exception:
                user = await asyncio.to_thread(self.pr_manager.client.get_user)
                await asyncio.to_thread(user.create_repo, repo_name, private=True)
                
            remote_url = f"https://github.com/{settings.github_owner}/{repo_name}.git"
            token = settings.github_pat.get_secret_value() if settings.github_pat else None
            
            if not await self.repo_manager.push_branch(project_dir, remote_url, branch_name, token):
                raise Exception("Failed to push to GitHub")
            cp[CheckpointKey.GIT_PUSHED] = True

        pr_url = cp.get(CheckpointKey.PR_URL)
        if not pr_url:
            pr_url = await self.pr_manager.create_pr(
                repo_name, 
                f"Generated Feature: {idea[:50]}", 
                f"Auto-generated by HomeServer\n\nTask ID: {task.id}", 
                branch_name
            )
            cp[CheckpointKey.PR_URL] = pr_url
            
        task.status = TaskStatus.AWAITING_APPROVAL
        task.payload['pr_url'] = pr_url
        task.payload['repo_name'] = repo_name
        
        await self.notifier.send_pr_notification(
            f"✅ PR ready for task `{task.id}`\n\nFeature: {idea}\n\n[View PR]({pr_url})", 
            task.id
        )
        logger.info(f"Finished processing task: {task.id}")
        
        return JobState.COMPLETED.value
