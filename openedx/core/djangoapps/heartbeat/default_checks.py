"""
A set of built-in default checks for the platform heartbeat endpoint

Other checks should be included in their respective modules/djangoapps
"""
from datetime import datetime, timedelta
from time import sleep, time

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.utils import DatabaseError
from xmodule.modulestore.django import modulestore
from xmodule.exceptions import HeartbeatFailure

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionTimeout, ConnectionError

from .tasks import sample_task


# DEFAULT SYSTEM CHECKS

# Modulestore

def check_modulestore():
    """ Check the modulestore connection

    Returns:
        (string, Boolean, unicode): A tuple containing the name of the check, whether it succeeded, and a unicode
                                    string of either "OK" or the failure message

    """
    # This refactoring merely delegates to the default modulestore (which if it's mixed modulestore will
    # delegate to all configured modulestores) and a quick test of sql. A later refactoring may allow
    # any service to register itself as participating in the heartbeat. It's important that all implementation
    # do as little as possible but give a sound determination that they are ready.
    try:
        #@TODO Do we want to parse the output for split and mongo detail and return it?
        modulestore().heartbeat()
        return 'modulestore', True, u'OK'
    except HeartbeatFailure as fail:
        return 'modulestore', False, unicode(fail)


def check_database():
    """ Check the database connection by attempting a no-op query

    Returns:
        (string, Boolean, unicode): A tuple containing the name of the check, whether it succeeded, and a unicode
                                    string of either "OK" or the failure message

    """
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT 1")
        cursor.fetchone()
        return 'sql', True, u'OK'
    except DatabaseError as fail:
        return 'sql', False, unicode(fail)


# Caching
CACHE_KEY = 'heartbeat-test'
CACHE_VALUE = 'abc123'


def check_cache_set():
    """ Check setting a cache value

    Returns:
        (string, Boolean, unicode): A tuple containing the name of the check, whether it succeeded, and a unicode
                                    string of either "OK" or the failure message

    """
    try:
        cache.set(CACHE_KEY, CACHE_VALUE, 30)
        return 'cache_set', True, u'OK'
    except Exception as fail:
        return 'cache_set', False, unicode(fail)


def check_cache_get():
    """ Check getting a cache value

    Returns:
        (string, Boolean, unicode): A tuple containing the name of the check, whether it succeeded, and a unicode
                                    string of either "OK" or the failure message

    """
    try:
        data = cache.get(CACHE_KEY)
        if data == CACHE_VALUE:
            return 'cache_get', True, u'OK'
        else:
            return 'cache_get', False, u'value check failed'
    except Exception as fail:
        return 'cache_get', False, unicode(fail)


# Celery
def check_celery():
    """ Check running a simple asynchronous celery task

    Returns:
        (string, Boolean, unicode): A tuple containing the name of the check, whether it succeeded, and a unicode
                                    string of either "OK" or the failure message

    """
    now = time()
    datetimenow = datetime.now()
    expires = datetimenow + timedelta(seconds=settings.HEARTBEAT_CELERY_TIMEOUT)

    try:
        task = sample_task.apply_async(expires=expires)
        while expires > datetime.now():
            if task.ready() and task.result:
                finished = str(time() - now)
                return 'celery', True, unicode({'time': finished})
            sleep(0.25)
        return 'celery', False, "expired"
    except Exception as fail:
        return 'celery', False, unicode(fail)


# Elasticsearch

def check_elasticsearch():
    search_host = str(settings.ELASTIC_SEARCH_CONFIG[0]['host']) + ':' + str(settings.ELASTIC_SEARCH_CONFIG[0]['port'])
    search_ssl = settings.ELASTIC_SEARCH_CONFIG[0]['use_ssl']
    search_timeout = settings.HEARTBEAT_ELASTICSEARCH_TIMEOUT

    es = Elasticsearch([search_host], use_ssl=search_ssl)

    try:
        result = es.ping(request_timeout=search_timeout)
        return 'elasticsearch', True, u'OK'
    except ConnectionTimeout:
        return 'elasticsearch', False, u'timeout'
    except ConnectionError as fail:
        return 'elasticsearch', False, unicode(fail)

