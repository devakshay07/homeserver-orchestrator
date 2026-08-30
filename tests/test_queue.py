import pytest
from queue.sqlite_queue import SQLiteQueue
from queue.models import TaskStatus

def test_enqueue_dequeue(monkeypatch, tmp_path):
    monkeypatch.setattr("config.settings.settings.db_path", str(tmp_path / "test.sqlite"))
    q = SQLiteQueue()
    
    # Enqueue
    task = q.enqueue({"test": "data"})
    assert task.status == TaskStatus.PENDING
    
    # Dequeue
    t2 = q.dequeue()
    assert t2 is not None
    assert t2.id == task.id
    assert t2.status == TaskStatus.IN_PROGRESS
    
    # Empty
    assert q.dequeue() is None
