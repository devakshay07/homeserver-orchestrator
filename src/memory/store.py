import sqlite3
from config.settings import settings
import structlog
from pathlib import Path

logger = structlog.get_logger("app")

class MemoryStore:
    def __init__(self):
        self.db_path = Path("data/memory.sqlite")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info("Memory store initialized (SQLite FTS5)")

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            # Create FTS5 virtual tables
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS prompts 
                USING fts5(idea, spec, type)
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS failures 
                USING fts5(task_id, idea, error)
            """)
            conn.commit()

    def add_prompt(self, idea: str, spec: str, type_val: str):
        with self._get_conn() as conn:
            conn.execute("INSERT INTO prompts(idea, spec, type) VALUES (?, ?, ?)", (idea, spec, type_val))
            conn.commit()

    def search_prompts(self, query: str, limit: int = 3) -> list[str]:
        # Simple FTS5 MATCH query
        # We sanitize the query lightly for MATCH syntax
        safe_query = ''.join(c if c.isalnum() else ' ' for c in query).strip()
        if not safe_query:
            return []
            
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # FTS5 matches tokens
            fts_query = " OR ".join(safe_query.split())
            try:
                cursor.execute(
                    "SELECT idea, spec FROM prompts WHERE prompts MATCH ? ORDER BY rank LIMIT ?", 
                    (fts_query, limit)
                )
                rows = cursor.fetchall()
                return [f"Idea: {r[0]}\n\nSpec: {r[1]}" for r in rows]
            except sqlite3.OperationalError:
                # Fallback if query syntax is bad
                return []

    def add_failure(self, task_id: str, idea: str, error: str):
        with self._get_conn() as conn:
            conn.execute("INSERT INTO failures(task_id, idea, error) VALUES (?, ?, ?)", (task_id, idea, error))
            conn.commit()

store = MemoryStore()
