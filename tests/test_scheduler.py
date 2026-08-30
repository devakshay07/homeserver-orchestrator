import pytest
from scheduler.cron_manager import CronManager

def test_cron_manager(mocker, tmp_path):
    mocker.patch("config.settings.settings.db_path", str(tmp_path / "cron.sqlite"))
    cm = CronManager()
    assert not cm.scheduler.running
    cm.start()
    assert cm.scheduler.running
    cm.stop()
    assert not cm.scheduler.running
