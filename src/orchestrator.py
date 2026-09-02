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
from gemini.prompt_builder import PromptBuilder
from gemini.coder import GeminiCoder
from review.quality_gate import QualityGate
from review.dependency_firewall import DependencyFirewall
from github.repo_manager import RepoManager
from github.pr_manager import PRManager
from memory.retriever import Retriever
from memory.updater import MemoryUpdater
from storage.lifecycle import StorageLifecycle

logger = structlog.get_logger("app")

class JobState(str, Enum):
    PLANNING = "PLANNING"
    TEST_GENERATING = "TEST_GENERATING"
    CODE_GENERATING = "CODE_GENERATING"
    FIREWALL = "FIREWALL"
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
        self.gemini_coder = GeminiCoder(self.gemini_client)
        self.quality_gate = QualityGate()
        self.firewall = DependencyFirewall(self.gemini_client)
        self.repo_manager = RepoManager(settings.workspace_dir)
        self.pr_manager = PRManager()
        self.memory_updater = MemoryUpdater()
        self.storage = StorageLifecycle(settings.workspace_dir, settings.disk_min_free_gb, settings.workspace_max_age_days)
        
    def _extract_repo_name(self, spec: str, task_id: str) -> str:
        match = re.search(r"# Project:\s*([a-zA-Z0-9_-]+)", spec)
        if match:
            return match.group(1).lower()
        return f"generated-project-{task_id[:8]}"

    async def _update_job_status(self, task: Task, cp: dict, idea: str, state: str, extra_info: str = ""):
        msg_id = cp.get("status_msg_id")
        
        status_lines = [f"🚀 **Job:** _{idea[:50]}_", ""]
        
        states = [
            (JobState.PLANNING.value, "🧠 Planning"),
            (JobState.TEST_GENERATING.value, "🧪 Writing Tests"),
            (JobState.CODE_GENERATING.value, "⚙️ Generating Code"),
            (JobState.FIREWALL.value, "🛡️ SecOps Firewall"),
            (JobState.TESTING.value, "🔍 Running QA Gate"),
            (JobState.DEBUGGING.value, "🐛 Debugging"),
            (JobState.REVIEW.value, "📝 Reviewing Docs"),
            (JobState.PR_CREATED.value, "🐙 PR Created")
        ]
        
        if state == JobState.COMPLETED.value:
            for s, label in states:
                status_lines.append(f"✅ {label}")
        else:
            current_idx = -1
            for i, (s, label) in enumerate(states):
                if s == state:
                    current_idx = i
                    break
                    
            for i, (s, label) in enumerate(states):
                if current_idx != -1 and i < current_idx:
                    status_lines.append(f"✅ {label}")
                elif i == current_idx:
                    status_lines.append(f"🔄 **{label}**")
                else:
                    status_lines.append(f"⏳ {label}")
                
        if extra_info:
            status_lines.append(f"\n_Info:_ {extra_info}")
            
        text = "\n".join(status_lines)
        new_msg_id = await self.notifier.update_status_message(text, msg_id)
        if new_msg_id and new_msg_id != msg_id:
            cp["status_msg_id"] = new_msg_id
            task.checkpoint = cp
            self.db_queue.update_task(task)

    async def process_task(self, task: Task) -> None:
        logger.info(f"Processing task: {task.id}", payload=task.payload)
        idea = task.payload.get('idea', '')
        
        try:
            cp = task.checkpoint or {}
            
            ok, free_gb = self.storage.check_disk_space()
            if not ok:
                raise Exception(f"Insufficient disk space: {free_gb:.1f} GB free")
            
            state = cp.get("job_state", JobState.PLANNING.value)
                
            while state != JobState.COMPLETED.value:
                await self._update_job_status(task, cp, idea, state)
                
                if state == JobState.PLANNING.value:
                    state = await self._handle_planning(task, cp, idea)
                elif state == JobState.TEST_GENERATING.value:
                    state = await self._handle_test_generating(task, cp)
                elif state == JobState.CODE_GENERATING.value:
                    state = await self._handle_code_generating(task, cp)
                elif state == JobState.FIREWALL.value:
                    state = await self._handle_firewall(task, cp)
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

            await self._update_job_status(task, cp, idea, JobState.COMPLETED.value)
            self.storage.cleanup_old_workspaces(self.db_queue)

        except GeminiQuotaExhausted as e:
            logger.exception(f"Task {task.id} failed (Quota)", error=str(e))
            await self._fail_task(task, cp, idea, str(e), "API Quota Exhausted")
        except GeminiContentBlocked as e:
            logger.exception(f"Task {task.id} failed (Blocked)", error=str(e))
            await self._fail_task(task, cp, idea, str(e), "Content Blocked")
        except Exception as e:
            logger.exception(f"Task {task.id} failed", error=str(e))
            await self._fail_task(task, cp, idea, str(e), "General Failure")

    async def _fail_task(self, task: Task, cp: dict, idea: str, err_str: str, reason: str):
        task.status = TaskStatus.FAILED
        task.payload['error'] = err_str
        self.db_queue.update_task(task)
        await self.memory_updater.save_failure(task.id, idea, err_str)
        await self._update_job_status(task, cp, idea, cp.get("job_state", ""), f"❌ Failed ({reason}): {err_str}")
        self.storage.cleanup_old_workspaces(self.db_queue)

    async def _handle_planning(self, task: Task, cp: dict, idea: str) -> str:
        async with StageTimer("spec_generation", task.id):
            spec = await self.spec_generator.generate_spec(idea)
            await self.memory_updater.save_prompt(idea, spec)
            
            repo_name = self._extract_repo_name(spec, task.id)
            project_dir = str(Path(settings.workspace_dir) / f"{repo_name}_{task.id[:8]}")
            
            cp[CheckpointKey.SPEC_TEXT] = spec
            cp[CheckpointKey.REPO_NAME] = repo_name
            cp[CheckpointKey.PROJECT_DIR] = project_dir
        return JobState.TEST_GENERATING.value

    async def _handle_test_generating(self, task: Task, cp: dict) -> str:
        project_dir = Path(cp[CheckpointKey.PROJECT_DIR])
        spec = cp[CheckpointKey.SPEC_TEXT]
        
        async with StageTimer("test_generation", task.id):
            instruction = f"Based on this spec:\n\n{spec}\n\nWrite a `task.md` checklist and the COMPLETE `tests/` directory (pytest). Do not write the source code yet."
            ret_code, stdout, stderr = await self.gemini_coder.generate(project_dir, instruction)
            if ret_code != 0:
                raise Exception(f"Test Generation failed: {stderr}")
                
        return JobState.CODE_GENERATING.value

    async def _handle_code_generating(self, task: Task, cp: dict) -> str:
        project_dir = Path(cp[CheckpointKey.PROJECT_DIR])
        spec = cp[CheckpointKey.SPEC_TEXT]
        
        async with StageTimer("code_generation", task.id):
            instruction = f"Based on the `task.md` checklist and the failing tests in `tests/`, write the actual source code and requirements.txt to fulfill the spec:\n\n{spec}"
            ret_code, stdout, stderr = await self.gemini_coder.generate(project_dir, instruction)
            if ret_code != 0:
                raise Exception(f"Code Generation failed: {stderr}")
                
        return JobState.FIREWALL.value

    async def _handle_firewall(self, task: Task, cp: dict) -> str:
        project_dir = Path(cp[CheckpointKey.PROJECT_DIR])
        async with StageTimer("firewall", task.id):
            await self.firewall.scan(project_dir)
        return JobState.TESTING.value

    async def _handle_testing(self, task: Task, cp: dict) -> str:
        project_dir = Path(cp[CheckpointKey.PROJECT_DIR])
        
        async with StageTimer("quality_gate", task.id):
            report = await self.quality_gate.run_all(project_dir)
            
            if report.hard_failed:
                cp["test_failures"] = report.summary()
                return JobState.DEBUGGING.value
                
        return JobState.REVIEW.value

    async def _handle_debugging(self, task: Task, cp: dict) -> str:
        iters = cp.get("debug_iterations", 0)
        if iters >= 3:
            raise Exception("Quality Gate failed after 3 debug iterations.")
            
        iters += 1
        cp["debug_iterations"] = iters
        
        project_dir = Path(cp[CheckpointKey.PROJECT_DIR])
        failures = cp.get("test_failures", "Unknown errors")
        
        instruction = f"The tests failed with:\n\n{failures}\n\nAnalyze the codebase and apply a fix."
        ret_code, stdout, stderr = await self.gemini_coder.generate(project_dir, instruction)
        if ret_code != 0:
            raise Exception(f"Gemini Debugging failed: {stderr}")
            
        return JobState.TESTING.value

    async def _handle_review(self, task: Task, cp: dict) -> str:
        project_dir = Path(cp[CheckpointKey.PROJECT_DIR])
        
        async with StageTimer("readme_review", task.id):
            readme_path = project_dir / "README.md"
        if readme_path.exists():
            readme_content = readme_path.read_text()
            improvements = await self.readme_reviewer.review(readme_content)
            if improvements and len(improvements) > 20:
                instruction = PromptBuilder.build_readme_update_prompt(improvements)
                await self.gemini_coder.generate(project_dir, instruction)
                
        return JobState.PR_CREATED.value

    async def _handle_pr_created(self, task: Task, cp: dict, idea: str) -> str:
        repo_name = cp[CheckpointKey.REPO_NAME]
        project_dir = Path(cp[CheckpointKey.PROJECT_DIR])
        branch_name = cp.get(CheckpointKey.GIT_BRANCH, f"feature/{task.id[:8]}")
        cp[CheckpointKey.GIT_BRANCH] = branch_name
        
        if not cp.get(CheckpointKey.GIT_PUSHED):
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
        return JobState.COMPLETED.value
