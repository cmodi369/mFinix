"""Logging functionality"""
import logging
import sys
from dataclasses import dataclass


@dataclass
class LogConfig:
    name: str = "mfinix"
    format: str = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    logger_level = logging.INFO
    console_level = logging.DEBUG


class Logger:
    @staticmethod
    def get_logger(name: str = LogConfig.name):
        # get logger
        logger = logging.getLogger(name)

        if not logger.handlers:
            Logger.create_logger(name)

        return logger

    @classmethod
    def create_logger(cls, name: str):
        logger = logging.getLogger(name)
        logger.setLevel(LogConfig.logger_level)
        logger.propagate = False

        logger.addHandler(Logger._add_console_handler())
        # logger.addHandler(Logger._add_file_handler())

    @staticmethod
    def _add_console_handler():
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(LogConfig.console_level)
        handler.setFormatter(logging.Formatter(LogConfig.format))

        return handler

    @staticmethod
    def _add_file_handler():
        handler = logging.FileHandler(filename="app.log")
        handler.setLevel(LogConfig.console_level)
        handler.setFormatter(logging.Formatter(LogConfig.format))

        return handler


if __name__ == "__main__":
    logger = Logger.get_logger()
