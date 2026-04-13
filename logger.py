import logging
import logging.handlers
import os


def setup_logging(log_file: str = "bot.log") -> None:
    """Configure rotating file handler + stdout. Call once from main.py at startup."""
    log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    fmt = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    root = logging.getLogger()
    root.setLevel(log_level)

    # Rotating file: 5 MB max, keep 3 backups
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # Console output
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named child logger. Call as get_logger(__name__) in each module."""
    return logging.getLogger(name)
