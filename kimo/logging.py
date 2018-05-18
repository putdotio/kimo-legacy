import logging

from kimo import logger

FORMAT = "[%(asctime)s] Thread(%(threadName)s) %(levelname)s %(name)s:%(funcName)s:%(lineno)s - %(message)s"


def setup_logging(level):
    level = getattr(logging, level.upper())
    file_handler = logging.FileHandler("/var/log/kimo.log")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(FORMAT))
    logger.setLevel(level)
    logger.addHandler(file_handler)
