from copy import deepcopy
import logging

from django.core.exceptions import ValidationError

from lms.djangoapps.program_enrollments.constants import ProgramEnrollmentStatuses
from lms.djangoapps.program_enrollments.models import ProgramEnrollment
from lms.djangoapps.program_enrollments.persistance.dfs import ProgramCardImageDfs
from lms.djangoapps.program_enrollments.persistance.persistent_object import PObject as _PObject
from lms.djangoapps.program_enrollments.persistance.program_courses import _ReferencedFieldFactory, _ProgramCourses
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.models.course_details import CourseDetails
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers


log = logging.getLogger(__name__)


class PartialProgram(_PObject):
    """Partial program data for MongoDB

        *** Thread Unsafe !!! ***

        Usages:
            # New
            program_detail = PartialProgram(init_type=xxx)
            program_detail['uuid'] = 'test_uuid_1'
            program_detail['title'] = 'test_title_1'
            program_detail.save()
            # Query
            saved = PartialProgram.query_one({'title': 'test_title_1'})
            # Update
            saved['title'] = 'test_title_2'
            saved.save()
            # Check
            saved = PartialProgram.query_one({'title': 'test_title_2'})
            assert saved.to_dict()['title'] == 'test_title_2'

    """
    # MACROs for MongoDB
    MONGODB_NAME = 'programs'
    MONGODB_COLLECTION_NAME = 'program_set'
    PROGRAM_CARD_IMG_BUCKET_NAME = 'program_card_images'

    # IMAGES/Assets Prefix definition: Used By: contentserver/middleware.py: def process_request(self, request):
    PREFIX_PROGRAM_CARD_IMAGE = 'program_asset_v1'

    # The Definition is used for initializing program info. of each instance
    MANDATORY_META_FIELDS = {
        'uuid': None,               # [Primary Key] program uuid ==> Doc.`_id`
        'title': None,              # [Mandatory field]  unique field
        'subtitle': None,
        'status': None,             # Program status: `unpublished` / `active`
        'marketing_slug': None,     # [Mandatory field]  unique field
        'courses': _ReferencedFieldFactory('courses', _ProgramCourses, is_multiple=True),
        'partner': None,            # [Mandatory field]
        'overview': None,
        'card_image_url': None,     # Program Card Image URI: Sample: `/program_asset_v1:63c25729592a4148a4d634dc1eb91c7c:test_demo.png`. (Stored In MongoDb)
        'description': None,
        'duration': None,           # Sample: 100000 (seconds).
        'language': None,
        'released_date': None,
        'creator_id': None,
        'creator_username': None,
        'applicable_seat_types': None,
        'start': None,
        'end': None,
        'enrollment_start': None,   # Value would be deduced after each adding/deleting course from program.
        'enrollment_end': None,     # Value would be deduced after each adding/deleting course from program.
        'languages': None,
        'visibility': None,
        'hidden': None,
        'type': None,               # Program type, Sample: `XSeries` / `MicroMasters` / `Professional Certificate` /...
    }
    dfs_handle = None               # Distributed File System handle for `Program Card Images`
    # LP publish status
    DEF_PUBLISHED_STATUS = 'active' # Published status value for program.
    DEF_UNPUBLISHED_STATUS = 'unpublished'
    # LP visibilities
    DEF_VISIBILITY_FULL_PUBLIC = 0
    DEF_VISIBILITY_ACCESSIBLE = 1
    DEF_VISIBILITY_PRIVATE = 2
    # LP loading policy
    POLICY_FULLY_LOADED = _PObject.DEFAULT_LOADING_POLICY_VALUE     # ( value : 0 )
    POLICY_LOAD_LP_ONLY = 1
    POLICY_ALL = [POLICY_FULLY_LOADED, POLICY_LOAD_LP_ONLY]

    def __init__(self, init_type, uuid=None, data=None, files=None, draft_obj=None, loading_policy=POLICY_FULLY_LOADED):
        """Construct/Initialize a program detail object for mongodb.

            @param init_type:       initialization type
            @type init_type:        integer
            @param uuid:            specify program uuid
            @type uuid:             string
            @param data:            dict like obj. (QueryDict: Example: request.POST.data)
            @type data:             dict / QueryDict
            @param files:           dict like obj. (QueryDict: Example: request.POST.FILES)
            @type files:            dict / QueryDict
            @param draft_obj:       instance of DraftPartialProgram
            @type draft_obj:        DraftPartialProgram
            @param loading_policy:  specified loading policy ( fully-loaded / load lp attributes only )
            @type loading_policy:   integer

        """
        super(PartialProgram, self).__init__(init_type)
        self._loading_policy = loading_policy

        if draft_obj is not None:
            # Plan A: Initialize instance with Draft instance. (DEF_INIT_TYPE_IS_MONGO_DATA)
            self._parse_from_draft_program(draft_obj)
        else:
            # Plan B/C: Initialize instance with Standard Dict. (DEF_INIT_TYPE_IS_NEW / DEF_INIT_TYPE_IS_RESPONSE)
            self.parse_from_data_and_files(data, files)
            # Assign `primary key` & `uuid` with program_uuid
            if uuid:
                self._data['_id'] = uuid    # Doc._id (Primary key)
                self._data['uuid'] = uuid   # program uuid string

    def __contains__(self, field_name):
        """Check if field `Value` exist by field name

            @param field_name:    field name of table program
            @type field_name:     string
            @return:              exist or not
            @rtype:               boolean
        """
        if field_name not in self._data and \
                field_name != self.MONGODB_PRIMARY_KEY:
            return False

        return False \
            if self._data[field_name] is None \
            else True

    def __getitem__(self, field_name):
        """"Return field value by field name.
            &
            Raise exception if field name doesn't exist in white-table.
        """
        if field_name not in self._data and \
                field_name != self.MONGODB_PRIMARY_KEY:
            raise KeyError(
                r'Field do not exist : {}'.format(field_name)
            )

        _value = self._data.get(field_name, None)
        if 'visibility' == field_name and (_value in (self.DEF_FIELD_NULL_VALUE, None)):
            self._data['visibility'] = self.DEF_VISIBILITY_PRIVATE
            return self._data['visibility']

        return _value

    def __setitem__(self, field_name, value):
        """Assign new value with field name.
            &
            the value would be handled by class `_ProgramCourses` if the field name is ***`courses`***

            @param field_name:  field name of table program
            @type field_name:   string
            @param value:       field value
            @type value:        object
        """
        if field_name not in self._data:
            raise KeyError(
                r'Field does not exist : {}'.format(field_name)
            )

        ref_field_factory = self.MANDATORY_META_FIELDS.get(field_name, None)

        # Store program card image into MongoDB
        if r'uuid' == field_name:
            self._data[r'_id'] = value      # MongoDb Doc Primary Key.
            self._data[r'uuid'] = value
        elif ref_field_factory and isinstance(ref_field_factory, _ReferencedFieldFactory):
            if self._loading_policy == self.POLICY_FULLY_LOADED:
                _RefClass = ref_field_factory.cls_property
                if self.init_type == self.DEF_INIT_TYPE_IS_RESPONSE:
                    self._data[field_name] = _RefClass(
                        response_data=value, parent_ref=self
                    ).to_list()
                else:
                    self._data[field_name] = _RefClass(
                        mongodb_data=value, parent_ref=self
                    ).to_list()

                if 'courses' == field_name:
                    self.recal_program_courses_dates()
            else:
                self._data[field_name] = []
        else:
            ### Set field value with `DEF_FIELD_NULL_VALUE` if value == None
            self._data[field_name] = self.DEF_FIELD_NULL_VALUE \
                if value is None and not self.is_new_record() \
                else value

    @classmethod
    def get_partners(cls):
        """Return partners name list of the current site."""
        partners = configuration_helpers.get_value('course_org_filter', [])
        if not isinstance(partners, list) and partners:
            partners = [partners]

        return partners

    @classmethod
    def query(cls, *args, **kwargs):
        """
            specify `loading_policy` in `kwargs` :
             - POLICY_FULLY_LOADED: load `LPs` + `Courses`.
             - POLICY_LOAD_LP_ONLY: load `Lps` Only.

        """
        if len(args) > 0:
            if 'partner' not in args[0]:
                args[0]['partner'] = {'$in': cls.get_partners()}

        return super(PartialProgram, cls).query(*args, **kwargs)

    @classmethod
    def default_sort_args(cls):
        """Return default sorting args list.

            Like sql: `order by start desc, title asc`
        """
        return [
            '-start',
            '+lowercase_title'
        ]

    def get_program_courses_manager(self):
        """Return program courses list manager.
        """
        return _ProgramCourses(
            mongodb_data=self._data[r'courses'],
            parent_ref=self
        )

    @classmethod
    def get_program_card_dfs(cls):
        """Return program card images manager"""
        if not cls.dfs_handle:
            cls.dfs_handle = ProgramCardImageDfs(
                db_connection=cls.database().get_raw_db_conn(),
                bucket_name=cls.PROGRAM_CARD_IMG_BUCKET_NAME
            )

        return cls.dfs_handle

    @classmethod
    def count_published_only(cls):
        """Count `published` programs number.

            Return Zero if collection name doesn't exist in MongoDB.
            Return None when an exception raised.
        """
        try:
            return cls.collection().find(
                {
                    'status': 'active',
                    'partner': {'$in': cls.get_partners()},
                    'visibility': {'$in': [0]}
                }
            ).count()
        except Exception:
            return None

    @classmethod
    def count_enrolled(cls, user):
        """Return enrolled lps count of a specified user
        """
        if user.is_anonymous():
            return 0

        _enrolled_program_uuids = [
            str(enrollment['program_uuid'])
            for enrollment in ProgramEnrollment.objects.values('program_uuid').filter(
                user=user,
                status__in=[ProgramEnrollmentStatuses.ENROLLED, ProgramEnrollmentStatuses.PENDING],
            ).all()
        ]
        _filter = {
            '_id': {'$in': _enrolled_program_uuids}
        }

        return cls.count_by_filter(_filter)

    def _parse_from_draft_program(self, draft_obj):
        """Initialize meta data of instance with another draft instance

            @param draft_obj:   instance of DraftPartialProgram
            @type draft_obj:    DraftPartialProgram
        """
        if '_id' not in draft_obj._data or 'uuid' not in draft_obj._data:
            raise ValidationError(
                '_id OR uuid not in draft program data. {}'.format(draft_obj._data)
            )

        self._data = deepcopy(draft_obj._data)
        self.recal_program_courses_dates()

    def parse_from_data_and_files(self, data, files=None):
        """Initialize fields data from Dict Like object.
            &
            The field name in arguments should be same with mongodb collection fields name.

            @param data:    dict like obj. (QueryDict: Example: request.POST.data)
            @type data:     dict / QueryDict
            @param files:   dict like obj. (QueryDict: Example: request.POST.FILES)
            @type files:    dict / QueryDict
        """
        super(PartialProgram, self).__setattr__(
            '_data',
            {
                fd_name: fd_init_value if not isinstance(fd_init_value, _ReferencedFieldFactory) else fd_init_value.initialize_value
                for fd_name, fd_init_value in PartialProgram.MANDATORY_META_FIELDS.items()
            }
        )

        if data:
            for f, v in data.items():
                if f in self._data:
                    self[f] = v
                else:
                    log.warning(
                        r'Invalid initialization arguments in `field`: {}'.format(f)
                    )

        if files:
            for f, v in files.items():
                if f in self._data:
                    self[f] = v

        self.recal_program_courses_dates()

        return self

    def to_dict(self, save_2_mongodb=False):
        """Return mongodb record object as a dict instance.
            &
            Generate/Update new field `lowercase_title`

            This field would be helpfull for case insensitive sorting by program title.

            Because MongoDB only support case insensitive sorting above MongoDB Version 3.4

            @param save_2_mongodb:      `True` means only save Mandatory Fields into DB ( !! Refresh LP's Courses attributes by Force !! ).
                                        `False` : return raw data dict.
            @type save_2_mongodb:       Boolean
        """
        title = self._data.get('title', '')     # LP title

        if not save_2_mongodb:
            self._data['lowercase_title'] = title.lower()

            return self._data
        else:
            # Return a deeply copied dict object  4  Saving to MongoDB
            # Ignore Flag `*** self._loading_policy ***`  &  Refresh courses attributes from MongoDB
            def _extract_field_value(fd_define, fd_value):
                if isinstance(fd_define, _ReferencedFieldFactory):
                    return fd_define.cls_property(
                        mongodb_data=fd_value, parent_ref=None
                        ).to_list(for_mongodb=True)
                else:
                    return fd_value

            mongodb_program = deepcopy(
                {
                    fd_name: _extract_field_value(fd_define, self._data.get(fd_name))
                    for fd_name, fd_define in self.MANDATORY_META_FIELDS.items()
                }
            )
            mongodb_program['_id'] = deepcopy(self._data['_id'])
            mongodb_program['lowercase_title'] = title.lower()

            return mongodb_program

    @property
    def visibility(self):
        if 'visibility' not in self._data:
            # The Default Visibility of Program should be "Full Public"
            self._data['visibility'] = self.DEF_VISIBILITY_PRIVATE

        return self._data['visibility']

    def recal_program_courses_dates(self):
        """Because of the `lantency` of the program coruses Synchronization between Server Studio & Course-Discovery
            (We have a sync. script running with command model).

            So we may need to call this method after changing the course date Or Register/Unregister courses from a program.

            It's not a good way for having such a method.
            But We may find a better way in the future & improve it After considering the current Architecture of our project.

            *** Note: We could call this method before saving. ***
        """
        min_start, max_end, min_enrollment_start, max_enrollment_end = self.get_program_courses_manager().cal_program_dates_by_courses()

        self['start'] = min_start
        self['end'] = max_end
        self['enrollment_start'] = min_enrollment_start
        self['enrollment_end'] = max_enrollment_end


class DraftPartialProgram(PartialProgram):
    """Draft Program collection

        *** Thread Unsafe !!! ***

        IF a `PartialProgram` instance exist. Then a `DraftPartialProgram` must exist as well.

    """
    MONGODB_COLLECTION_NAME = 'draft_program_set'

    def is_frozen_visibility_status(self):
        """Return `True` if the published LP's `visibility` status couldn't be changed
            ( private courses included in LP ) .

            As we could change LP visibility status from A ---> B as follow:
             - Full public ---> Accessible by URL
             - Full public ---> Private
             - Accessible by URL ---> Full public
             - Accessible by URL ---> Private
             - Private (exclude private cx) ---> Full public
             - Private (exclude private cx) ---> Accessible by URL

            But we couldn't do as follow:
             - Private (include private ex) ---> Full public
             - Private (include private ex) ---> Accessible by URL
        """
        published_program = PartialProgram.query_one(
            {'_id': self.to_dict()['uuid']}
        )

        if published_program:
            program_course_mgr = published_program.get_program_courses_manager()

            for course in program_course_mgr.to_list():
                if CourseDetails.fetch(CourseKey.from_string(course['key'])).catalog_visibility == 'none':
                    return True

        return False

    @classmethod
    def test_engaged_LP_by_courses_visibility(cls, course_key_string):
        """We wanna know a course whether used by some LPs."""
        used_by_private_lp = False
        used_by_non_private_lp = False

        _filter = {'courses.course_runs.key': course_key_string}
        for _program in cls.query(_filter):
            if used_by_non_private_lp == True and used_by_private_lp == True:
                break

            if _program['visibility'] == PartialProgram.DEF_VISIBILITY_PRIVATE:
                used_by_private_lp = True
            else:
                used_by_non_private_lp = True

        return {'used_by_private': used_by_private_lp, 'used_by_non_private': used_by_non_private_lp}
