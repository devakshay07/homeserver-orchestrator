import chromadb
from config.settings import settings
import structlog
from pathlib import Path

logger = structlog.get_logger("app")

class MemoryStore:
    def __init__(self):
        Path(settings.chroma_db_path).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=settings.chroma_db_path)
        
        # Initialize collections
        self.prompts = self.client.get_or_create_collection(name="prompts")
        self.projects = self.client.get_or_create_collection(name="projects")
        self.preferences = self.client.get_or_create_collection(name="preferences")
        self.failures = self.client.get_or_create_collection(name="failures")
        logger.info("Memory store initialized")

store = MemoryStore()
