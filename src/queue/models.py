from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import Any, Dict

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    DONE = "DONE"
    FAILED = "FAILED"
    REJECTED = "REJECTED"

@dataclass
class Task:
    id: str
    status: TaskStatus
    payload: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    attempts: int = 0
    checkpoint: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status.value,
            "payload_json": json.dumps(self.payload),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "attempts": self.attempts,
            "checkpoint_json": json.dumps(self.checkpoint)
        }

    @classmethod
    def from_row(cls, row: tuple) -> 'Task':
        return cls(
            id=row[0],
            status=TaskStatus(row[1]),
            payload=json.loads(row[2]),
            created_at=datetime.fromisoformat(row[3]),
            updated_at=datetime.fromisoformat(row[4]),
            attempts=row[5],
            checkpoint=json.loads(row[6]) if row[6] else {}
        )

class CheckpointKey:
    SPEC_DONE     = "spec_done"
    SPEC_TEXT     = "spec_text"
    REPO_NAME     = "repo_name"
    PROJECT_DIR   = "project_dir"
    AGY_DONE      = "agy_done"
    README_DONE   = "readme_done"
    QUALITY_DONE  = "quality_done"
    GIT_BRANCH    = "git_branch"
    GIT_PUSHED    = "git_pushed"
    PR_URL        = "pr_url"
    PR_NUMBER     = "pr_number"
