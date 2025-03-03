import logging
from logging.handlers import RotatingFileHandler


formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s - %(message)s")


logger = logging.getLogger("main")
logger.setLevel(logging.DEBUG)
file_handler = RotatingFileHandler(
    "logs/main.log", maxBytes=10 * 1024 * 1024, backupCount=5
)
file_handler.setFormatter(formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
