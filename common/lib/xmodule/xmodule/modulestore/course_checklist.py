from xmodule.modulestore.django import modulestore


class Checkpoints(object):
    """Definitions of checkpoints ( keys + status )
    """
    UNCHECKED = 0
    CHECKED = 1
    ALL_CHECKPOINT_STATUS = [UNCHECKED, CHECKED]

    class STEP(object):
        """Checkpoint definition class
        """
        def __init__(self, name, desc):
            """
                @param name:        step name (lower case)
                @type name:         string
                @param desc:        step description
                @type desc:         string
            """
            self._name = name
            self._desc = desc

        def __repr__(self):
            return self._name

        @property
        def name(self):
            """Return step name
            """
            return self._name

        @property
        def description(self):
            """Return step description
            """
            return self._desc

        @property
        def field_name(self):
            """Return (lowercase) step name
            """
            return self._name.lower()

        def __eq__(self, other):
            """ Equality is based on being of the same class, and having same name
            """
            return self.field_name == other.name.lower() \
                if isinstance(other, Checkpoints.STEP) else self.field_name == other.lower()

    # We define supported Steps here.
    DEF_STEP_1 = STEP('1', 'Start Creating Your Course Content')
    DEF_STEP_2 = STEP('2', 'Create Your Course Grading Policy')
    DEF_STEP_3 = STEP('3', 'Add Team Members to This Course')
    DEF_STEP_4 = STEP('4', 'Add a Course Image and Course Description')
    DEF_STEP_5 = STEP('5', 'Make Your Course Available or Hide it on the Catalog')
    DEF_STEP_6 = STEP('6', 'Set Important Course Dates')
    DEF_STEP_7 = STEP('7', 'Publish All Your Content')
    ALL_DEFINED_STEPS = [DEF_STEP_1, DEF_STEP_2, DEF_STEP_3, DEF_STEP_4, DEF_STEP_5, DEF_STEP_6, DEF_STEP_7]

    @classmethod
    def is_valid_checkpoint_status(cls, status):
        return status in cls.ALL_CHECKPOINT_STATUS

    @classmethod
    def is_valid_step_keys(cls, key_name):
        return key_name in cls.ALL_DEFINED_STEPS


class StudioCoursesChecklists(object):
    """Manage Studio Courses' checklists collection of MongoDB (database: edxapp).
        It's a singleton instance.
    """
    __singleton_obj = None
    MONGO_PRIMARY_KEY = r'_id'
    COLLECTION_NAME = r'lt_studio_courses.checklists'

    def __new__(cls, *args, **kwargs):
        """Always return identical class instance"""
        if not cls.__singleton_obj:
            cls.__singleton_obj = super(StudioCoursesChecklists, cls).__new__(cls)

        return cls.__singleton_obj

    def __init__(self):
        self._checklists_collection = None
        self._prepare_chercklists_collection_handle()

    def get_checklists_by_key(self, course_key):
        """Get document of checklists by `course_key`.

            Only fields defined in `Checkpoints.ALL_DEFINED_STEPS` could be returned.

            @param course_key:      course key
            @type course_key:       string
            @return                 Return document of checklists
            @rtype                  dict

            Sample:
                {
                    'step_name': [1, "desc...1"],
                    'step_2': [0, "desc...2"],
                    ...
                }
        """
        if not self._checklists_collection:
            raise RuntimeError('checklists collection is a invalid instance.')

        _record = self._checklists_collection.find_one(
            {StudioCoursesChecklists.MONGO_PRIMARY_KEY: course_key}
        )

        return [
            {
                'name': step.name,
                'key': step.field_name,
                'status': _record[step.field_name] if _record and step in _record.keys() else Checkpoints.UNCHECKED,
                'desc': step.description
            }
            for step in Checkpoints.ALL_DEFINED_STEPS
        ]

    def upsert_checklists_by_key(self, course_key, steps_logs):
        """Update an document according to `course_key` if the key already exist, otherwise Insert a new one.

            Raise `pymongo.errors.OperationFailure` or `TypeError` if got exception.

            @param course_key:      course key
            @type course_key:       string
            @param steps_logs:      field / value pairs needed to be updated
            @type steps_logs:       dict
            @return:                A dict describing the effect of the update or None if write acknowledgement is disabled.
                                    Sample:
                                        `{"updatedExisting":false,"nModified":0,"ok":1,"upserted":"course-v1:edX+bcs_101+2022-10-10","n":1}`
                                        `{"updatedExisting":true,"nModified":1,"ok":1,"n":1}`
            @rtype:                 dict
        """
        if not self._checklists_collection:
            raise RuntimeError('checklists collection is a invalid instance.')

        return self._checklists_collection.update(
            {StudioCoursesChecklists.MONGO_PRIMARY_KEY: course_key},
            {'$set': steps_logs},
            upsert=True
        )

    def _prepare_chercklists_collection_handle(self):
        """Prepare mongodb collection handle by `StudioCoursesChecklists.COLLECTION_NAME`

            Only `xmodule.modulestore.mongo.MongoModuleStore` + `xmodule.modulestore.split_mongo.split.SplitMongoModuleStore` are
                supported for load mongodb database instance from.
            Otherwise raising Exception.

        """
        _mixed_ms = modulestore()
        _default_modulestore = _mixed_ms.default_modulestore

        from xmodule.modulestore.mongo import MongoModuleStore
        from xmodule.modulestore.split_mongo.split import SplitMongoModuleStore

        # Get mongodb's database instance
        if isinstance(_default_modulestore, SplitMongoModuleStore):
            _mongo_database = _default_modulestore.db_connection.database
        elif isinstance(_default_modulestore, MongoModuleStore):
            _mongo_database = _default_modulestore.database
        else:
            raise ValueError('Unknow modulestore type.')

        # Grap collection with a specified collection name.
        self._checklists_collection = _mongo_database[StudioCoursesChecklists.COLLECTION_NAME]
