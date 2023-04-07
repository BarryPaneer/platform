from abc import ABCMeta, abstractmethod

from django.core.exceptions import ValidationError
from pymongo import (
    ASCENDING,
    DESCENDING
)
from lms.djangoapps.program_enrollments.persistance.connection import MongoDbConnectionsManager


class PObject(object):
    """Base class for all mongodb record object."""
    # MongoDB Locator Info.
    MONGODB_NAME = None
    MONGODB_COLLECTION_NAME = None

    # Primary Key name
    MONGODB_PRIMARY_KEY = r'_id'        # `from bson.objectid import ObjectId`
    # MACRO Definitions
    DEF_FIELD_NULL_VALUE = 'is_null'

    # Definition: type of initialization
    DEF_INIT_TYPE_IS_NEW = 0            # Initialized from Standard Dict obj.
    DEF_INIT_TYPE_IS_MONGO_DATA = 1     # Initialized from MongoDB
    DEF_INIT_TYPE_IS_RESPONSE = 2       # Initialized from URI Response

    # `Value` of Default data loading policy value
    DEFAULT_LOADING_POLICY_VALUE = 0

    __metaclass__ = ABCMeta

    def __init__(self, init_type):
        """
            @param init_type:          initialization type
            @type init_type:           integer
        """
        self._init_type = init_type
        self._data = {}

    @property
    def init_type(self):
        """Return init type."""
        return self._init_type

    def is_new_record(self):
        """Return record status"""
        return self._init_type == self.DEF_INIT_TYPE_IS_NEW

    @abstractmethod
    def parse_from_data_and_files(self, data, files=None):
        """Initialize fields data from Dict Like object.
            &
            The field name in arguments should be same with mongodb collection fields name.

            @param data:    dict like obj. (QueryDict: Example: request.POST.data)
            @type data:     dict / QueryDict
            @param files:   dict like obj. (QueryDict: Example: request.POST.FILES)
            @type files:    dict / QueryDict
            @return:        self
            @rtype:         instance of Subclass
        """
        raise NotImplementedError

    def to_dict(self, save_2_mongodb=False):
        """Return mongodb record object as a dict instance.

            @param save_2_mongodb:  a flag for indicating DB saving operation
            @type save_2_mongodb:   Boolean
        """
        return self._data

    @classmethod
    def query_one(cls, _filter=None, *args, **kwargs):
        """Query & return 1 record from MongoDB by filter

            @param _filter:         the query to be performed OR any other type to be used as the value for a query for ``"_id"``.
            @type _filter:          dict
            @param args:            any additional positional arguments
            @type args:             tuple
            @param kwargs:          any additional keyword arguments ( specify `loading_policy`, default is Zero )
            @type kwargs:           dict
            @return:                `Record` Or `None`
            @rtype:                 instance of Subclass

        """
        data = cls.collection().find_one(
            _filter, *args, **kwargs
        )
        if not data:
            return None

        new_instance = cls(
            PObject.DEF_INIT_TYPE_IS_MONGO_DATA,
            loading_policy=kwargs.pop('loading_policy', cls.DEFAULT_LOADING_POLICY_VALUE)   # loading policy ( Default: 0 )
        )
        new_instance.parse_from_data_and_files(
            data=data
        )

        return new_instance

    @classmethod
    def default_sort_args(cls):
        """Return default sorting args list

            @return:        sorting args. Sample: [('field_name_1', DESCENDING), ...]
            @rtype:         instance of Subclass
        """
        raise NotImplementedError

    @classmethod
    def query(cls, *args, **kwargs):
        """Query & return records from MongoDB by filter
            &
            The records are sorted by field `start DESC` (Default sort policy).

            @param args:            any additional positional arguments
            @type args:             tuple
            @param kwargs:          any additional keyword arguments
            @type kwargs:           dict
            @return:                Records
            @rtype:                 list of Subclass instance

            options for `kwargs`:
                - limit:            return limitation
                - sort_args:        sort policy. Sample ( +start=>sort by start asc; -start=> sort by start desc )
                                                 Default policy: `start` DESC
                - loading_policy:   default is Zero. ( Sometimes we may need loading parts of attributes ).

        """
        # option: limit
        records_limit = kwargs.pop('limit', 0)
        # option: sort policy
        sort_args = kwargs.pop('sort_args', None)
        if not sort_args:
            sort_args = cls.default_sort_args()
        # option: loading policy ( default value : 0 )
        loading_policy = kwargs.pop('loading_policy', cls.DEFAULT_LOADING_POLICY_VALUE)

        sort_args = [
            (
                arg[1:],
                ASCENDING if arg[0] == '+' else DESCENDING
            )
            for arg in sort_args
        ]

        records = cls.collection().find(
            *args, **kwargs
        ).sort(
            sort_args
        ).limit(
            records_limit
        )

        if not records:
            yield ()

        for record_data in records:
            new_instance = cls(PObject.DEF_INIT_TYPE_IS_MONGO_DATA, loading_policy=loading_policy)
            new_instance.parse_from_data_and_files(
                data=record_data
            )

            yield new_instance

    @classmethod
    def count_by_filter(cls, *args, **kwargs):
        return cls.collection().find(
            *args, **kwargs
        ).count()

    @classmethod
    def delete(cls, _id):
        """Delete data record from MongoDB collection.

            @param _id:         MongoDB record primary key
            @type _id:          string
            @return:            deleted record
            @rtype:             dict
        """
        deleted_one = cls.collection().find_one(
            {'_id': _id}
        )
        cls.collection().remove(
            {'_id': _id}
        )

        return deleted_one

    @classmethod
    def database(cls):
        """Return database"""
        if not cls.MONGODB_NAME:
            raise ValidationError(
                r'Invalid database name : {}'.format(cls.MONGODB_NAME)
            )

        return MongoDbConnectionsManager.get_manager().\
            get_connection_by_dbname(
                cls.MONGODB_NAME
            )

    @classmethod
    def collection(cls):
        """Return db collection according to object type.
        """
        if not cls.MONGODB_NAME or not cls.MONGODB_COLLECTION_NAME:
            raise ValidationError(
                r'Invalid db name or collection name : {} / {}'.format(
                    cls.MONGODB_NAME, cls.MONGODB_COLLECTION_NAME
                )
            )

        db_connection = cls.database()

        return db_connection[cls.MONGODB_COLLECTION_NAME]

    @classmethod
    def count(cls):
        """Count documents number.

            Return Zero if collection name doesn't exist in MongoDB.
            Return None when an exception raised.
        """
        try:
            return cls.collection().count()
        except Exception:
            return None

    def save(self, ignored_fields=None):
        """Save data into a MongoDB collection

            @param ignored_fields:      ignored fields names set (the data of these fields would not be saved)
            @type ignored_fields:       set
        """
        p_object_data = self.to_dict(save_2_mongodb=True)   # Get a filtered data ( remain course keys/uuid only )

        if not p_object_data['_id']:
            raise ValidationError('MongoDB record primary key (`_id`) cannot be empty.')

        if self.is_new_record():
            return self.collection().insert(
                p_object_data
            )
        else:
            # `Update` Or `Insert` if record doesn't exist
            ignored_fields = set() \
                if not ignored_fields else ignored_fields

            return self.collection().update(
                {r'_id': p_object_data[r'_id']},
                {
                    '$set': {
                        fd: None if self.DEF_FIELD_NULL_VALUE == val else val
                        for fd, val in p_object_data.items()
                        if val is not None and fd not in ignored_fields     # Ignore `None` Value while updating.
                    }
                },
                upsert=True
            )
