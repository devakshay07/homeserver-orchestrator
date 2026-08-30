import logging
import logging.handlers
import sys
import structlog
from pathlib import Path
from config.settings import settings

def setup_logging() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Standard library logging configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove all existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # File handlers
    file_handlers = {
        "app": log_dir / "app.log",
        "telegram": log_dir / "telegram.log",
        "generation": log_dir / "generation.log",
        "git": log_dir / "git.log",
        "error": log_dir / "error.log",
        "performance": log_dir / "performance.log",
    }

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer()
    )

    for name, path in file_handlers.items():
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=10*1024*1024, backupCount=5
        )
        handler.setFormatter(formatter)
        if name == "error":
            handler.setLevel(logging.ERROR)
        
        # Add a filter to route specific logs based on logger name
        class LoggerNameFilter(logging.Filter):
            def __init__(self, target_name: str):
                super().__init__()
                self.target_name = target_name

            def filter(self, record: logging.LogRecord) -> bool:
                if self.target_name == "app":
                    return record.name not in ["telegram", "generation", "git", "performance"]
                elif self.target_name == "error":
                    return True # Error file gets all errors
                return record.name == self.target_name
        
        handler.addFilter(LoggerNameFilter(name))
        root_logger.addHandler(handler)

    # Console handler for development/debugging
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer()
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Structlog configuration
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
