from logging import (
    Formatter,
    getLogger,
    handlers,
    INFO
)
from os import path
from time import gmtime


class ExternalCatalogLogger(object):
    """
        External logger class (specified log format)

        Usage:
            log = ExternalCatalogLogger(
                log_file_name=r'edflex_external_catalog_update.log'
            ).logger

            log.info(r'hello, logger...')
    """
    LOGGER_NAME = r'external_catalog'
    LOG_ROOT = r'/edx/var/log/lms/'

    def __init__(self, log_file_name):
        """Format a logger output"""
        log_formatter = Formatter(
            r'%(asctime)s [%(name)s] [%(filename)s:%(lineno)d] %(levelname)s  - %(message)s'
        )
        log_formatter.converter = gmtime

        log_handler = handlers.TimedRotatingFileHandler(
            path.join(self.LOG_ROOT, log_file_name),
            when='D',
            interval=10,
            backupCount=4,
            encoding='utf-8'
        )
        log_handler.setFormatter(log_formatter)
        log_handler.setLevel(INFO)

        self.__logger = getLogger(self.LOGGER_NAME)
        self.__logger.addHandler(log_handler)

    @property
    def logger(self):
        """Return handle of Logger"""
        return self.__logger

    @classmethod
    def getLoggerByName(cls):
        """Return logger by same logger name"""
        return getLogger(
            ExternalCatalogLogger.LOGGER_NAME
        )
