import logging
import os
from datetime import datetime
from glob import glob

LOG_DIR = "logs"
MAX_LOG_FILES = 30
_logger: logging.Logger = None


def setup_logger(log_dir: str = LOG_DIR) -> logging.Logger:
    global _logger
    os.makedirs(log_dir, exist_ok=True)
    _rotate(log_dir)

    session = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = os.path.join(log_dir, f"{session}.log")

    logger = logging.getLogger("autobot")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(fh)

    _logger = logger
    logger.info(f"Session started — log: {log_path}")
    return logger


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = logging.getLogger("autobot")
    return _logger


def _rotate(log_dir: str):
    files = sorted(glob(os.path.join(log_dir, "*.log")))
    while len(files) >= MAX_LOG_FILES:
        os.remove(files.pop(0))
