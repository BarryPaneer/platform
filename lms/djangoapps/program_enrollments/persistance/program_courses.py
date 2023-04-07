from copy import deepcopy
from datetime import datetime

from django.core.exceptions import ValidationError

from opaque_keys.edx.locator import CourseKey
from openedx.core.djangoapps.models.course_details import CourseDetails


class _ReferencedFieldFactory(object):
    """
        - Create instance for different field classes which specified with parameter `cls_type`.
        - Hold fields name
        - Generate default value for new instance
    """
    def __init__(self, field_name, cls_type, is_multiple=False):
        """
            @param field_name:      field name
            @type field_name:       string
            @param cls_type:        customized class
            @type cls_type:         class
            @param is_multiple:     the field is a List
            @type is_multiple:      boolean
        """
        self._field_name = field_name
        self._cls_type = cls_type
        self._is_multiple = is_multiple

    @property
    def initialize_value(self):
        """Return initialize value for raw python dict of fields mapping.

            @return:        default value of Initial argument
            @rtype:         object
        """
        return [] if self._is_multiple else None

    @property
    def cls_property(self):
        """Return managed class type"""
        return self._cls_type

    def __str__(self):
        return self._field_name

    def __repr__(self):
        """Always return str(field name) while reading the instance
        """
        return self._field_name


class _AttributesFetcher(object):
    """Update LP courses attributes with specified course attributes value OR `CourseDetails`.
        - DEF_MANDATORY_FIELDS:     all courses attributes in it need to be loaded.
        - DEF_ATTRIBUTES_MAPPING:   This is a map<mandatory fields, CourseDetail.attributes> for loading value from CourseDetail.
                                    All attributes in it also should exist in `DEF_MANDATORY_FIELDS`.

        It's eash for extension if we wanna add more fields in the future.
    """
    DEF_MANDATORY_FIELDS = {}           # Including "ALL" mandatory fields of LP Courses
    DEF_ATTRIBUTES_MAPPING = {}         # Specify fields which need to be loaded from other Collections each time.

    @classmethod
    def load_from_external_data(cls, data, course_detail=None):
        """Load & Initialize from External data

            @param data:                External data for parsing
            @type data:                 object
            @param course_detail:       Course Attributes
            @type course_detail:        CourseDetails
            @return:                    Internal data
            @rtype:                     object
        """
        return _AttributesFetcher._extract_values_from_external_data(
            cls.DEF_MANDATORY_FIELDS,
            cls.DEF_ATTRIBUTES_MAPPING,
            data,
            course_detail
        )

    @classmethod
    def _extract_values_from_external_data(cls, mandatory_fields, managed_attributes, data, course_detail):
        """Extract values from external data & Return internal data
            &
            We may refresh specified attributes from CourseDetails.

            @param mandatory_fields:    Specified mandatory fields
            @type mandatory_fields:     list
            @param managed_attributes:  Specified additional fields which are loaded from CourseDetails.
            @type managed_attributes:   dict
            @param data:                External data for parsing
            @type data:                 structure
            @param course_detail:       Course Attributes ( *** If `None` Return attributes which excluded by `DEF_ATTRIBUTES_MAPPING` *** )
            @type course_detail:        CourseDetails
            @return:                    Internal data
            @rtype:                     structure

        """
        # We discard `class CourseDetails` related fields IF argument `course_detail` is None.
        if not course_detail:
            mandatory_fields = {
                loading_field for loading_field in mandatory_fields if loading_field not in managed_attributes
            }

        def _extract_field_value(field, item):
            field_name = str(field)
            mapped_field = managed_attributes.get(field_name, None)

            def _read_value():
                if mapped_field:
                    if 'image' != field_name:
                        _val = getattr(course_detail, mapped_field, None)
                        return _val.strftime("%Y-%m-%dT%H:%M:%SZ") \
                            if isinstance(_val, datetime) and field_name in ('start', 'end', 'enrollment_start', 'enrollment_end') \
                            else _val

                    # Update field "image"
                    item[field_name] = {
                        'width': None, 'height': None, 'description': None,
                        'src': getattr(course_detail, mapped_field, None)
                        }

                return item[field_name]

            return field.cls_property.load_from_external_data(
                    item[field_name], course_detail
                ) if isinstance(field, _ReferencedFieldFactory) \
                else _read_value()

        if isinstance(data, (tuple, list)):
            return [
                {
                    str(field): _extract_field_value(field, _item) for field in mandatory_fields
                }
                for _item in data
            ]
        else:
            return {
                str(field): _extract_field_value(field, data)
                for field in mandatory_fields
            }


class _ProgramCourses(_AttributesFetcher):
    """Manage program courses list for Draft Program

        We define mandatory attributes of LP courses in `DEF_MANDATORY_FIELDS`
         &
         define mapping of parts of attributes in `DEF_ATTRIBUTES_MAPPING`, then load them from `CourseDetail` while accessing
         =>
         *** So we always load latest Courses attributes from MongoDB. ***

        [Data SAMPLE] in MongoDB:

            "courses" : [
                {
                    "uuid": "d591f0a5-92d4-47ba-8f21-bf938e559885",
                    "title": "Demonstration Course",
                    "image": {...},
                    "short_description": "short desc...",
                    "key": "edX+DemoX",
                    "course_runs": [
                        {
                            "status": "published",
                            "end": "2021-10-10T00:00:00Z",
                            "uuid": "b5346003-3a70-4f6e-923c-eab963fbd323",
                            "title": "Demonstration Course",
                            ...
                        },
                        {...course run 2...},
                        ...
                    ]
                },
                {...course 2...},
                ...
            ],
    """
    class _CourseRunsField(_AttributesFetcher):
        """Definitions of field `CourseRun`.
        """
        DEF_MANDATORY_FIELDS = {
            'uuid',                     # [Mandatory field] Course Run UUID
            'key',                      # [Mandatory field] Course Run Key, Sample: `course-v1:edX+DemoX+Demo_Course`
            #'status',
            'image',
            'start',
            'end',
            'enrollment_start',
            'enrollment_end',
            'description',
            'duration'
            #'pacing_type',
            #'type'                      # Sample: `verified`
        }
        DEF_ATTRIBUTES_MAPPING = {      # Mapping: Field name of MongoDb ==> CourseDetail Attributes Name for Reloading
            'image': 'course_image_asset_path',
            'start': 'start_date',
            'end': 'end_date',
            'enrollment_start': 'enrollment_start',
            'enrollment_end': 'enrollment_end',
            'description': 'description',
            'duration': 'duration'
        }

        def __str__(self):
            return r'course_runs'

        def __repr__(self):
            """Always return str(field name) while reading the instance
            """
            return r'course_runs'

    DEF_MANDATORY_FIELDS = {
        'uuid',                         # [Mandatory field] Course UUID
        'key',                          # [Mandatory field] Course Key, Sample: `edX+DemoX`
        'title',
        'start',
        'end',
        'short_description',
        'image',
        'description',
        _ReferencedFieldFactory(        # [Mandatory field] Course runs array
            'course_runs',
            _CourseRunsField,
            is_multiple=True
        ),
    }
    DEF_ATTRIBUTES_MAPPING = {
        'title': 'title',
        'start': 'start_date',
        'end': 'end_date',
        'short_description': 'short_description',
        'image': 'course_image_asset_path',
        'description': 'description'
    }

    def __init__(self, response_data=None, mongodb_data=None, parent_ref=None):
        """Constructor
            Generate program's courses list with Response of Program Detail

            @param response_data:   program courses list of program detail page's Response
            @type response_data:    list
            @param mongodb_data:    program courses list for initialization
            @type mongodb_data:     list
            @param parent_ref:      program object reference
            @type parent_ref:       object
        """
        self._parent_ref = parent_ref if parent_ref else None

        if mongodb_data is not None:
            # Initialize with data structure directly
            mongodb_data_backup = deepcopy(mongodb_data)
            self._courses = mongodb_data
            for i in range(0, len(mongodb_data)):
                self._courses.pop()
            self._courses.extend(
                [
                    self.load_from_external_data(mongodb_course, None)
                    for mongodb_course in mongodb_data_backup
                ] if mongodb_data_backup else []
                )

        elif response_data:
            # Initialize with response data of Program Detail URI
            self._courses = [
                self.load_from_external_data(
                    resp_course, None
                )
                for resp_course in response_data
            ] \
                if response_data else []

        else:
            self._courses = []

    def has_course(self, course_uuid=None, course_run_key=None):
        """Return `True` if course uuid/run key does exist

            @param course_uuid:      course uuid
            @type course_uuid:       string
            @param course_run_key:   course run key
            @type course_run_key:    string
            @return:                 True: course exist
            @rtype:                  boolean

        """
        if not course_run_key and not course_uuid:
            raise ValidationError(r'Lack arguments.')

        for course in self._courses:
            if course_uuid and course['uuid'] == course_uuid:
                return True

            if course_run_key and course['course_runs']:
                for course_run in course['course_runs']:
                    if course_run['key'] == course_run_key:
                        return True

        return False

    def _refresh_program_dates(self):
        if self._parent_ref:
            self._parent_ref.recal_program_courses_dates()

    def add_draft_course(self, course_in_response):
        """Add draft course into program courses list.

            @param kwargs:      course data
            @type kwargs:       dict

        """
        _uuid = course_in_response.get('uuid', None)
        if not _uuid:
            raise ValidationError(
                'Invalid course uuid : {}'.format(_uuid)
            )

        for course in self._courses:
            if _uuid == course['uuid']:
                return

        self._courses.append(
            self.load_from_external_data(course_in_response, None)
        )

        self._refresh_program_dates()

    def move_course_to_target(self, course_id, new_index):
        """Move course into a new index of Program Courses list

            @param course_id:           course id(key)
            @type course_id:            string
            @param new_index:           new index target
            @type new_index:            zero-based integer
        """
        if new_index < 0 or not course_id:
            raise ValidationError('Invalid arguments.')

        if new_index >= len(self._courses):
            raise ValidationError(
                'Invalid arguments: target index = {}'.format(new_index)
            )

        last_index = -1
        for index, course in enumerate(self._courses):
            course_runs = course['course_runs']
            if course_runs:
                for run in course_runs:
                    if run['key'] == course_id:
                        last_index = index  # Get index with course uuid
                        break

            if last_index >= 0:
                break

        if -1 == last_index:
            raise ValidationError(
                'Course[{}] does not exist in Draft Program Course list.'.format(course_id)
            )

        if last_index != new_index:
            target_course = self._courses[last_index]

            del self._courses[last_index]
            self._courses.insert(new_index, target_course)

    def delete_draft_course(self, course_id):
        """Delete a course from draft courses list

            @param course_id:        course id(key)
            @type course_id:         string
        """
        if not course_id:
            raise ValidationError(
                'Invalid course key : {}'.format(course_id)
            )

        for index, course in enumerate(self._courses):
            course_runs = course['course_runs']

            if course_runs:
                for run in course_runs:
                    if course_id == run['key']:
                        del self._courses[index]
                        self._refresh_program_dates()
                        return

    @classmethod
    def load_from_external_data(cls, data, additional_data=None):
        """Generate course info For program courses list.
        """
        _course_id = data.get('key', None)
        if not data.get('uuid', None) and not _course_id:
            raise ValidationError(r'course uuid and key are all empty.')

        additional_data = CourseDetails.fetch(CourseKey.from_string(_course_id))

        return _AttributesFetcher._extract_values_from_external_data(
            cls.DEF_MANDATORY_FIELDS,
            cls.DEF_ATTRIBUTES_MAPPING,
            data,
            additional_data
        )

    def __iadd__(self, course_in_response):
        """Add new course into Program Courses List
        """
        self.add_draft_course(course_in_response)
        return self

    def __iter__(self):
        """Return iterator of program courses list.
        """
        return iter(self._courses)

    def __getitem__(self, index):
        """Return course by `index`
        """
        return self._courses[index]

    def cal_program_dates_by_courses(self):
        """Cal. program dates by coures"""
        min_start = max_end = min_enrollment_start = max_enrollment_end = None

        for _course in self._courses:
            for _c_run in _course.get('course_runs', []):
                if not min_start:
                    min_start = _c_run['start']
                elif _c_run['start'] and _c_run['start'] < min_start:
                    min_start = _c_run['start']

                if not max_end:
                    max_end = _c_run['end']
                elif _c_run['end'] and _c_run['end'] > max_end:
                    max_end = _c_run['end']

                if not min_enrollment_start:
                    min_enrollment_start = _c_run['enrollment_start']
                elif _c_run['enrollment_start'] and _c_run['enrollment_start'] < min_enrollment_start:
                    min_enrollment_start = _c_run['enrollment_start']

                if not max_enrollment_end:
                    max_enrollment_end = _c_run['enrollment_end']
                elif _c_run['enrollment_end'] and _c_run['enrollment_end'] > max_enrollment_end:
                    max_enrollment_end = _c_run['enrollment_end']

        return min_start, max_end, min_enrollment_start, max_enrollment_end

    def to_list(self, for_mongodb=False):
        """Return raw list of program courses.
            Return list([]) if empty.
        """
        if not for_mongodb:
            if self._courses is None:
                self._courses = []

            return self._courses
        else:
            if not self._courses:
                return []

            return deepcopy(
                [
                    _AttributesFetcher._extract_values_from_external_data(
                        self.DEF_MANDATORY_FIELDS, self.DEF_ATTRIBUTES_MAPPING,
                        _course, course_detail=None
                    )
                    for _course in self._courses
                ]
            )
