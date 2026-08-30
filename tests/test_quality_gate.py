import pytest
from pathlib import Path
from review.quality_gate import QualityGate

@pytest.mark.asyncio
async def test_quality_gate_run(mocker, tmp_path):
    qg = QualityGate()
    
    # Mock all inner tools to return True
    mocker.patch.object(qg.linter, "run_format", return_value=True)
    mocker.patch.object(qg.linter, "run_check", return_value=True)
    mocker.patch.object(qg.analyzer, "run", return_value=True)
    mocker.patch.object(qg.tester, "run", return_value=True)
    mocker.patch.object(qg.secret_scanner, "run", return_value=True)
    mocker.patch.object(qg.link_checker, "run", return_value=True)
    
    result = await qg.run_all(tmp_path)
    assert result is True
