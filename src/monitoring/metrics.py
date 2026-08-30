import time
import shutil
import structlog

perf_logger = structlog.get_logger("performance")

class StageTimer:
    def __init__(self, stage_name: str, task_id: str):
        self.stage_name = stage_name
        self.task_id = task_id

    async def __aenter__(self):
        self._start = time.monotonic()
        return self

    async def __aexit__(self, *_):
        elapsed = time.monotonic() - self._start
        perf_logger.info("stage_complete",
                         stage=self.stage_name,
                         task_id=self.task_id,
                         duration_seconds=round(elapsed, 2))

def log_disk_usage(workspace_dir: str) -> None:
    stat = shutil.disk_usage(workspace_dir)
    free_gb = stat.free / (1024 ** 3)
    used_pct = (stat.used / stat.total) * 100
    perf_logger.info("disk_usage",
                     free_gb=round(free_gb, 2),
                     used_pct=round(used_pct, 1))
