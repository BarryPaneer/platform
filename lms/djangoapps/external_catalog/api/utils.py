from functools import wraps

from lms.djangoapps.external_catalog.utils import ExternalCatalogLogger


log = ExternalCatalogLogger.getLoggerByName()


class exception_retry(object):
    """Recall method when any exception is raised"""
    def __init__(self, retry_times=3):
        self.__retry_times = retry_times

    def __call__(self, func):
        @wraps(func)
        def wrapped_function(*args, **kwargs):
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    self.__retry_times -= 1
                    if self.__retry_times < 0:
                        raise
                    else:
                        log.warn('Retrying... after got exception : {}'.format(e))

        return wrapped_function


def print_error_arguments(func):
    """Print invalid arguments of method when exception is thrown"""
    @wraps(func)
    def wrapped_function(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if args:
                log.error(r'invalid argument 1 : {}'.format(args))
            if kwargs:
                log.error(r'invalid argument 2 : {}'.format(kwargs))
            raise e

    return wrapped_function
