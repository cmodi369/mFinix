"""Logging functionality"""
import logging
import sys


class LogConfig:
    NAME: str = "mfinix"
    FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOGGER_LEVEL = logging.INFO
    CONSOLE_LEVEL = logging.DEBUG


class Logger:
    @staticmethod
    def get_logger():
        # get logger
        logger = logging.getLogger(LogConfig.NAME)

        if not logger.handlers:
            Logger.create_logger()

        return logger

    @classmethod
    def create_logger(cls):
        logger = logging.getLogger(LogConfig.NAME)
        logger.setLevel(LogConfig.LOGGER_LEVEL)

        logger.addHandler(Logger._add_console_handler())
        # logger.addHandler(Logger._add_file_handler())

    @staticmethod
    def _add_console_handler():
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(LogConfig.CONSOLE_LEVEL)
        handler.setFormatter(logging.Formatter(LogConfig.FORMAT))

        return handler

    @staticmethod
    def _add_file_handler():
        handler = logging.FileHandler(filename="app.log")
        handler.setLevel(LogConfig.CONSOLE_LEVEL)
        handler.setFormatter(logging.Formatter(LogConfig.FORMAT))

        return handler


if __name__ == "__main__":
    logger = Logger.get_logger()
