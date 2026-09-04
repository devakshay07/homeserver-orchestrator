import os
import shutil
import sqlite3
import structlog
from pathlib import Path
from datetime import datetime, timedelta
import asyncio

from config.settings import settings

logger = structlog.get_logger("maintenance")

class SystemCleaner:
    def __init__(self, notifier=None):
        self.data_dir = Path("data")
        self.workspace_dir = Path(settings.workspace_dir)
        self.notifier = notifier

    async def run_nightly_maintenance(self):
        logger.info("Starting nightly system maintenance...")
        report = []
        
        # 1. Clean old workspaces
        cleared_workspaces = self._clean_old_workspaces()
        report.append(f"🧹 Cleared {cleared_workspaces} stale workspaces.")
        
        # 2. Vacuum SQLite Databases
        vacuumed_dbs = self._vacuum_databases()
        report.append(f"💾 Vacuumed {vacuumed_dbs} SQLite databases.")
        
        # 3. Clean PyCache
        pycache_cleared = self._clean_pycache()
        report.append(f"🔥 Removed {pycache_cleared} __pycache__ directories.")
        
        # 4. Clean old logs
        old_logs = self._clean_old_logs()
        report.append(f"📝 Deleted {old_logs} outdated log files.")
        
        logger.info("Nightly maintenance complete.")
        
        if self.notifier:
            msg = "🛠️ *Nightly Maintenance Complete*\n\n" + "\n".join(report)
            try:
                await self.notifier.send_message(msg, parse_mode="Markdown")
            except Exception as e:
                logger.error("Failed to send maintenance notification", error=str(e))
                
    def _clean_old_workspaces(self) -> int:
        count = 0
        from datetime import timezone
        now = datetime.now(timezone.utc)
        max_age = timedelta(days=settings.workspace_max_age_days)
        if not self.workspace_dir.exists():
            return count
            
        for p in self.workspace_dir.iterdir():
            if p.is_dir():
                mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
                if now - mtime > max_age:
                    try:
                        shutil.rmtree(p)
                        count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete {p}", error=str(e))
        return count

    def _vacuum_databases(self) -> int:
        count = 0
        for db_file in self.data_dir.glob("*.sqlite"):
            try:
                with sqlite3.connect(db_file) as conn:
                    conn.execute("VACUUM")
                count += 1
            except Exception as e:
                logger.error(f"Failed to vacuum {db_file}", error=str(e))
        return count

    def _clean_pycache(self) -> int:
        count = 0
        src_dir = Path(__file__).parent.parent
        for root, dirs, files in os.walk(src_dir, topdown=False):
            for name in dirs:
                if name == "__pycache__":
                    try:
                        shutil.rmtree(os.path.join(root, name))
                        count += 1
                    except Exception as e:
                        logger.warning("Failed to delete pycache", path=os.path.join(root, name), error=str(e))
        return count

    def _clean_old_logs(self) -> int:
        count = 0
        from datetime import timezone
        now = datetime.now(timezone.utc)
        logs_dir = self.data_dir / "logs"
        if not logs_dir.exists():
            return count
            
        for f in logs_dir.glob("*.log"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if now - mtime > timedelta(days=7):
                try:
                    f.unlink()
                    count += 1
                except: pass
        return count
