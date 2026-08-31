import pytest
from unittest.mock import AsyncMock, MagicMock
from orchestrator import Orchestrator
from task_queue.models import Task, TaskStatus, CheckpointKey
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_spec_stage_skipped_when_checkpointed(mocker, isolated_settings):
    db_queue = MagicMock()
    notifier = MagicMock()
    notifier.send_message = AsyncMock()
    
    orch = Orchestrator(db_queue, notifier)
    
    task = Task(
        id="123",
        status=TaskStatus.IN_PROGRESS,
        payload={"idea": "test"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    task.checkpoint = {
        CheckpointKey.SPEC_DONE: True, 
        CheckpointKey.SPEC_TEXT: "cached spec",
        CheckpointKey.REPO_NAME: "test-repo",
        CheckpointKey.PROJECT_DIR: "/tmp/test"
    }
    
    mock_gen = mocker.patch.object(orch.spec_generator, "generate_spec", new_callable=AsyncMock)
    mock_run = mocker.patch.object(orch.agy_runner, "run_command", new_callable=AsyncMock, return_value=(0, "", ""))
    mocker.patch.object(orch.readme_reviewer, "review", new_callable=AsyncMock, return_value="")
    mocker.patch.object(orch.quality_gate, "run_all", new_callable=AsyncMock, return_value=True)
    mocker.patch.object(orch.repo_manager, "init_and_commit", new_callable=AsyncMock)
    mocker.patch.object(orch.repo_manager, "push_branch", new_callable=AsyncMock, return_value=True)
    mocker.patch.object(orch.pr_manager, "create_pr", new_callable=AsyncMock, return_value="http://pr")
    mocker.patch("asyncio.to_thread", new_callable=AsyncMock)
    
    await orch.process_task(task)
    mock_gen.assert_not_called()

def test_extract_repo_name_with_project():
    from orchestrator import Orchestrator
    orchestrator = Orchestrator(None, None)
    spec = "# Project: my-project\nSome text"
    assert orchestrator._extract_repo_name(spec, "task-123") == "my-project"

def test_extract_repo_name_fallback():
    from orchestrator import Orchestrator
    orchestrator = Orchestrator(None, None)
    spec = "Some text without project"
    assert orchestrator._extract_repo_name(spec, "task-123456789") == "generated-project-task-123"

