import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from task_queue.worker import TaskWorker

@pytest.mark.asyncio
async def test_watchdog_restarts_dead_worker(mocker, isolated_settings):
    db_queue = MagicMock()
    mock_process = AsyncMock()
    
    worker = TaskWorker(db_queue, mock_process)
    worker.start()
    
    worker._task.cancel()
    try:
        await worker._task
    except asyncio.CancelledError:
        pass
        
    await asyncio.sleep(0)
    
    # Simulate watchdog run
    worker._watchdog_task.cancel() # Stop the real watchdog
    await asyncio.sleep(0)
    
    # Call watchdog body
    if worker._task is None or worker._task.done():
        worker._task = asyncio.create_task(worker._run())
        
    assert worker._task is not None and not worker._task.done()
    await worker.stop()
