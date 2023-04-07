import datetime
import logging
import pymongo
import pytz
import re
from traceback import format_exc

from django.core.exceptions import ValidationError
from django.conf import settings
from mongodb_proxy import MongoProxy
from mongodb_proxy import autoretry_read
from pymongo.database import Database
from xmodule.mongo_utils import connect_to_mongodb, create_collection_index


log = logging.getLogger(__name__)


class _MongoDbConnection(object):
    """(MongoDB) PyMongo wrapper class. Maintain a DB connection.
        &&
        expose most of the attributes/methods from `pymongodb.connection.database`
    """
    def __init__(
        self, db, host, port=27017, tz_aware=True, user=None, password=None, retry_wait_time=0.1, **kwargs
    ):
        """Create & open a `DB` connection, authenticate, and provide pointers to the collections
        """
        # Set a write concern of 1, which makes writes complete successfully to the primary
        # only before returning. Also makes pymongo report write errors.
        kwargs['w'] = 1

        self._database = connect_to_mongodb(
            db, host,
            port=port, tz_aware=tz_aware, user=user, password=password,
            retry_wait_time=retry_wait_time, **kwargs
        )

    def __getattr__(self, db_connection_attr):
        """"Return db connection instance's attribute by attr name.

            @param db_connection_attr:    attributes/methods name of mongodb connection
            @type db_connection_attr:     string
            @return:                      attributes/methods of mongodb connection
            @rtype:                       object
        """
        return getattr(self._database, db_connection_attr)

    def __getitem__(self, collection_name):
        """Return collection by collection name from db

            @param collection_name:    mongodb collection name
            @type collection_name:     string
            @return:                   collection
            @rtype:                    pymongo.collection
        """
        return self._database[collection_name]

    def get_raw_db_conn(self):
        """Return raw database connection instance

            @return:                    raw db connection
            @rtype:                     pymongo.database.Database
        """
        return self._database.proxied_object \
            if isinstance(self._database, MongoProxy) \
            else self._database

    def close(self, ignore_exception=True):
        """Closes any open connections to the underlying databases

            @param ignore_exception:    ignore exception flag
            @type ignore_exception:     boolean
        """
        try:
            if self._database:
                self._database.connection.close()
                self._database = None
        except Exception:
            log.error(
                r'Got exception while releasing mongodb handler : {}'.format(format_exc)
            )
            if not ignore_exception:
                raise

    def mongo_wire_version(self):
        """Returns the wire version for mongo. Only used to unit tests which instrument the connection.
        """
        return self._database.connection.max_wire_version


class MongoDbConnectionsManager(object):
    """MongoDb connections cache. It's a singleton instance.
    """
    __singleton_obj = None

    def __new__(cls, *args, **kwargs):
        """Always return identical class instance"""
        if not cls.__singleton_obj:
            cls.__singleton_obj = super(MongoDbConnectionsManager, cls).__new__(cls)

        return cls.__singleton_obj

    def __init__(self):
        self._connections_mapping = {}

    @classmethod
    def get_manager(cls):
        """Return manager instance"""
        if not cls.__singleton_obj:
            cls.__singleton_obj = MongoDbConnectionsManager()

        return cls.__singleton_obj

    def get_connection_by_dbname(self, dbname):
        """Get mongodb connection by database name
            or
            Create a new connection with database name

            @param dbname:          mongodb name
            @type dbname:           string
            @return:                mongodb connection
            @rtype:                 pymongo.database.Database/pymongo.MongoClient
        """
        if not dbname:
            raise ValidationError('Invalid mongodb name: {}'.format(dbname))

        conn = self._connections_mapping.get(dbname)

        if not conn:
            if dbname not in settings.EDX_OBJECTS_MONGODB_SETTINGS:
                raise ValidationError(
                    'Invalid mongodb name : {} : which not in `settings`'.format(dbname)
                )

            config = settings.EDX_OBJECTS_MONGODB_SETTINGS[dbname]
            conn = _MongoDbConnection(**config)
            self._connections_mapping['dbname'] = conn

        return conn

    def close(self):
        """Close all connections
            &
            ignore all exceptions in conn.close()
        """
        for conn in self._connections_mapping.values():
            conn.close()

        self._connections_mapping = {}

    # @autoretry_read()
    # def find_structures_by_id(self, ids, course_context=None):
    #     """
    #     Return all structures that specified in ``ids``.
    #
    #     Arguments:
    #         ids (list): A list of structure ids
    #     """
    #     with TIMER.timer("find_structures_by_id", course_context) as tagger:
    #         tagger.measure("requested_ids", len(ids))
    #         docs = [
    #             structure_from_mongo(structure, course_context)
    #             for structure in self.structures.find({'_id': {'$in': ids}})
    #         ]
    #         tagger.measure("structures", len(docs))
    #         return docs
