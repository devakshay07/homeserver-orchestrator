import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta
import structlog

logger = structlog.get_logger("app")

class StorageLifecycle:
    def __init__(self, workspace_dir: str, min_free_gb: float, max_age_days: int):
        self.workspace_dir = Path(workspace_dir)
        self.min_free_gb = min_free_gb
        self.max_age_days = max_age_days

    def check_disk_space(self) -> tuple[bool, float]:
        stat = shutil.disk_usage(self.workspace_dir.parent)
        free_gb = stat.free / (1024 ** 3)
        return free_gb >= self.min_free_gb, free_gb

    def cleanup_old_workspaces(self, db_queue) -> int:
        if not self.workspace_dir.exists(): return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
        deleted = 0
        for entry in self.workspace_dir.iterdir():
            if not entry.is_dir(): continue
            task_id_prefix = entry.name.split("_")[-1]
            tasks = db_queue.list_tasks(limit=200)
            for task in tasks:
                if task.id.startswith(task_id_prefix) \
                   and task.status.value in ("DONE", "FAILED", "REJECTED") \
                   and task.updated_at < cutoff:
                    logger.info("Deleting old workspace", path=str(entry), task_id=task.id)
                    shutil.rmtree(entry, ignore_errors=True)
                    deleted += 1
                    break
        return deleted

    def cleanup_venvs(self) -> None:
        if not self.workspace_dir.exists(): return
        for entry in self.workspace_dir.rglob(".venv"):
            if entry.is_dir():
                logger.info("Removed project venv", path=str(entry))
                shutil.rmtree(entry, ignore_errors=True)
