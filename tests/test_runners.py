import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from review.test_runner import TestRunner
from review.static_analysis import StaticAnalyzer

@pytest.mark.asyncio
@patch("review.test_runner.asyncio.create_subprocess_exec")
async def test_test_runner_path(mock_exec):
    runner = TestRunner()
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc
    
    project_dir = Path("my_project")
    await runner.run(project_dir)
    
    # Assert pytest executable path is correctly resolved
    mock_exec.assert_called_once()
    assert mock_exec.call_args[0][0] == str(project_dir / ".venv" / "bin" / "pytest")

@pytest.mark.asyncio
@patch("review.static_analysis.asyncio.create_subprocess_exec")
async def test_static_analysis_path(mock_exec):
    analyzer = StaticAnalyzer()
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc
    
    project_dir = Path("my_project")
    await analyzer.run(project_dir)
    
    # Assert mypy executable path is correctly resolved
    mock_exec.assert_called_once()
    assert mock_exec.call_args[0][0] == str(project_dir / ".venv" / "bin" / "mypy")
