# -*- coding: utf-8 -*-
from __future__ import unicode_literals

"""
    The definitions of programs operations workflow.

    - ProgramCreator: create a new program.
    - ProgramLoader: list program detail.
    - ProgramListLoader: list all programs.
    - ProgramCoursesLoader: list programs's courses list.
    - ProgramCourseRegister: link a course into a program courses list.
    - ProgramCourseReorder: change the order of a course which in program courses list.
    - ProgramPartialUpdate: partial updating for program detail (include program card image file uploading).
    - ProgramCourseEraser: unlink a course from a program courses list.
    - ProgramEraser: delete a program.

"""

import logging
from abc import ABCMeta, abstractmethod
from os.path import getsize as get_file_size
from os.path import join as joinpath
from types import MethodType
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Q
from django.http.request import QueryDict
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from slumber import Resource

from student.models import (
    CourseAccessRole,
    CourseEnrollment
)
from common.djangoapps.student.auth import (
    STUDIO_EDIT_CONTENT,
    STUDIO_VIEW_CONTENT
)
from lms.djangoapps.program_enrollments.api.writing import write_program_enrollment
from lms.djangoapps.program_enrollments.models import ProgramEnrollment
from lms.djangoapps.program_enrollments.models import ProgramCourseEnrollment
from lms.djangoapps.program_enrollments.constants import ProgramCourseEnrollmentStatuses
from lms.djangoapps.program_enrollments.persistance.programs import PartialProgram, _ProgramCourses
from lms.djangoapps.program_enrollments.persistance.programs import DraftPartialProgram
from lms.djangoapps.teams.models import ProgramAccessRole
from lms.djangoapps.teams.program_team_roles import ProgramStaffRoles
from lms.djangoapps.teams.program_team_roles import ProgramInstructorRole
from lms.djangoapps.teams.program_team_roles import ProgramRolesManager
from openedx.core.djangoapps.catalog.utils import create_catalog_api_client


log = logging.getLogger(__name__)


class _Workflow(object):
    """Interface for all discovery restful api proxy call
        &
        programs operations
    """
    DEFAULT_PROGRAM_CARD_IMAGE_NAME = r'triboo_default_image.jpg'
    DEFAULT_PROGRAM_CARD_IMAGE_PATH = joinpath(
        settings.CMS_ROOT,
        r'static/images/',
        r'triboo_default_image.jpg'
    )

    __metaclass__ = ABCMeta

    def __init__(self, user, program_uuid=None, required_permissions=None, current_site_domain=None):
        """Constructor
            &
            checking the permission if args `program_uuid` and `required_permissions` are both passed.
            (Raise exception if permission denied.)

            @param user:                    user obj.
            @type user:                     object
            @param program_uuid:            program uuid
            @type program_uuid:             string
            @param required_permissions:    required permission for accessing this program.
            @type required_permissions:     integer(mask value)
            @param current_site_domain:     current site domain string ( Sending to Service Discovery )
            @tyhpe current_site_domain:     string
        """
        self._user = user
        self._program_uuid = program_uuid
        self._api_client_handler = None
        self._current_site_domain = current_site_domain

        if self._current_site_domain is None:
            raise ValidationError(r'Invalid current site domain, should not be None.')

        if required_permissions and program_uuid:
            # Permission checking
            user_permissions = ProgramRolesManager.get_permissions(
                self._user,
                self._program_uuid
            )
            # Checking permissions bit masks.
            if not required_permissions & user_permissions:
                raise ValidationError(
                    r'User[{}] has no permission for accessing'.format(self._user)
                )

    @property
    def _api_client(self):
        """Return service discovery programs access api

            @return:            programs data access api
            @rtype:             EdxRestApiClient
        """
        if not self._api_client_handler:
            self._api_client_handler = create_catalog_api_client(
                self._user,
                current_site_domain=self._current_site_domain   # Specify the domain of current site for Target Service
            )

        return self._api_client_handler

    @staticmethod
    def _overwrite_get_method_for_slumber(slumber_attribute):
        """Overwrite get() method of slumber api,
            so the new method would store very LONG parameters into HTTP Body (request.data)
            That also means we could send BIG data like `POST` in `GET` method.

            @param slumber_attribute:   class Slumber.Resource instance
            @type slumber_attribute:    object
            @return:                    http resource obj.
            @rtype:                     class Slumber.Resource instance

        """

        def get(self, data=None, **kwargs):
            """Support `data` for http get method

                @param data:            parameters for Http body
                @type data:             object
                @param kwargs:          query string in url.
                @type data:             string
            """
            resp = self._request("GET", data=data, params=kwargs)
            return self._process_response(resp)

        # Patch new method...
        slumber_attribute.get = MethodType(
            get, slumber_attribute, Resource
        )

        return slumber_attribute

    @staticmethod
    def _overwrite_delete_method_for_slumber(slumber_attribute):
        """Overwrite delete() method of slumber api,
            so the new method would return raw response from discovery services
            Args slumber_attribute:   class Slumber.Resource instance
            Note:
                The old `delete()` method return `True/False` only And this cannot cater our demand.
        """

        def delete(self, **kwargs):
            """Support `param` for http delete method"""
            resp = self._request("DELETE", params=kwargs)
            return self._process_response(resp)

        # Patch new method...
        slumber_attribute.delete = MethodType(
            delete, slumber_attribute, Resource
        )

        return slumber_attribute

    def initialize_program_detail_to_draftdb(self, force=False):
        """Download & save (prod/draft)program data from Service discovery
                if data doesn't exist in MongoDB yet.

            @param force:           force downloading & save flag.
            @type force:            boolean
            @return:                Draft program detail object.
            @rtype:                 DraftPartialProgram
        """
        draft_program = DraftPartialProgram.query_one(
            {'_id': self._program_uuid}
        )
        if not draft_program or force:
            # Fetch program detail by program uuid
            resp_program_detail = self._overwrite_get_method_for_slumber(
                getattr(
                    self._api_client.programs,
                    self._program_uuid
                )
            ).get()
            if not isinstance(resp_program_detail, dict) or \
                    'uuid' not in resp_program_detail:
                raise ValidationError(
                    r'Invalid response data format. Should be dict obj. : {}'.format(resp_program_detail)
                )

            # Update new data into MongoDb(Draft).
            draft_program = DraftPartialProgram(
                init_type=DraftPartialProgram.DEF_INIT_TYPE_IS_RESPONSE,
                data=resp_program_detail
            )
            draft_program.save()

        return draft_program

    @classmethod
    def generate_program_card_image_key(cls, draft_program, specified_file_name=None):
        """Generate program card image key.
            &
            Make sure the prefix string exist in image key string.

            @param draft_program:       draft program data instance
            @type draft_program:        DraftPartialProgram
            @param specified_file_name: specified file name by client user.
            @type specified_file_name:  string
            @return:                    image key
            @rtype:                     string

            Image Key Sample:
                `program_asset_v1:ab72f71b0363490d886a8a9d35c5c2a1:triboo_default_image.jpg`

        """
        card_image_url = draft_program['card_image_url'] \
            if draft_program['card_image_url'] else None

        if not card_image_url:
            return r'{}:{}:{}'.format(
                PartialProgram.PREFIX_PROGRAM_CARD_IMAGE,
                uuid4().hex,
                _Workflow.DEFAULT_PROGRAM_CARD_IMAGE_NAME if not specified_file_name else specified_file_name
            )
        else:
            if PartialProgram.PREFIX_PROGRAM_CARD_IMAGE in card_image_url:
                last_colon_index = card_image_url.rfind(':')
                if last_colon_index:
                    card_image_url = card_image_url[last_colon_index:]
                    card_image_url = card_image_url if card_image_url else 'my_photo'

            return r'{}:{}:{}'.format(
                PartialProgram.PREFIX_PROGRAM_CARD_IMAGE,
                uuid4().hex,
                card_image_url if not specified_file_name else specified_file_name
            )

    @classmethod
    def check_global_staff_permission(cls, user):
        """Ref: def user_has_role(user, role)"""
        if not (user.is_authenticated and user.is_active):
            raise ValidationError(
                'Please login or activate the current user.'
            )

    @abstractmethod
    def execute(self):
        """Execute proxy operations workflow"""
        raise NotImplementedError()


class ProgramCreator(_Workflow):
    """Program creator

        workflow:
            - Checking for user permission in class constructor.
            - Create program by calling service discovery api.
            - Create Draft Program int MongoDB
            - Create roles (instructor & staff) for api caller(request.user).
            - Enroll into this program for api caller(request.user).
            - Add new program into ES index.

        POST:
            http://0.0.0.0:18010/api/proxy/discovery/api/v1/programs/

        *** Note: ***
            Don't support for creating of Program's card image (card image uploading)

    """
    def __init__(self, user, post_data, post_files, current_site_domain=None):
        """
            @param user:             program creator user obj.
            @type user:              object
            @param post_data:        POST data for Program Creator http call
            @type post_data:         dict
        """
        # 1. Check global staff permissions only
        #       and Don't consider `CourseCreatorRole` here.
        self.check_global_staff_permission(user)

        super(ProgramCreator, self).__init__(
            user,
            current_site_domain=current_site_domain
        )
        self._post_data = QueryDict('', mutable=True)
        self._post_files = QueryDict('', mutable=True)
        self._post_data.update(post_data)
        self._post_files.update(post_files)
        self._card_image_file = None
        # Set program creator id
        self._post_data['creator_id'] = user.id

    def __enter__(self):
        """Support content manager"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release file handlers at last step
        """
        if self._card_image_file:
            self._card_image_file.close()
            self._card_image_file = None

    @property
    def default_card_image(self):
        """Generate & Return default card image for program

            @return:                image file instance
            @rtype:                 InMemoryUploadedFile
        """
        if self._card_image_file:
            self._card_image_file.close()
            self._card_image_file = None

        self._card_image_file = open(
            _Workflow.DEFAULT_PROGRAM_CARD_IMAGE_PATH
        )
        default_image_loaded = InMemoryUploadedFile(
            self._card_image_file,
            'card_image_url',
            'program_card_image.jpg',
            'image/jpg',
            get_file_size(_Workflow.DEFAULT_PROGRAM_CARD_IMAGE_PATH),
            None
        )

        return default_image_loaded

    def execute(self):
        """Program Creating workflow definitions"""
        # 1. Prepare program Draft record for MongoDB.
        new_draft_program = DraftPartialProgram(
            DraftPartialProgram.DEF_INIT_TYPE_IS_NEW,
            data=self._post_data
        )

        if 'visibility' not in self._post_data:
            # The default value of "visibility" is "Private".
            self._post_data['visibility'] = PartialProgram.DEF_VISIBILITY_PRIVATE

        if 'card_image_url' not in self._post_data:
            program_card_dfs_handle = PartialProgram.get_program_card_dfs()

            new_draft_program['card_image_url'] = program_card_dfs_handle.upload_file(
                self.default_card_image,
                self.generate_program_card_image_key(
                    new_draft_program,
                    specified_file_name=self._post_data.pop('new_card_image_name', None)
                )  # get Image Key of program card
            )
            self._post_data['card_image_url'] = new_draft_program['card_image_url']

        # 2. Create program record with Proxy Api
        api_response = self._api_client.programs.post(
            data=self._post_data,
            files=self._post_files
        )
        new_program_uuid = api_response['program_uuid']

        # 3. Save Draft record for MongoDB.
        new_draft_program['uuid'] = new_program_uuid
        new_draft_program.save()

        # 4. Create Roles for Program Creator
        ProgramInstructorRole(new_program_uuid).add_user(self._user)
        ProgramStaffRoles(new_program_uuid).add_user(self._user)

        # 5. Enroll creator on this Program
        write_program_enrollment(
            new_program_uuid,
            {
                'username': self._user.username,
                'status': 'enrolled'
            },
            create=True,
            update=False
        )

        # 6. Add new program into ES Index documents table
        from cms.djangoapps.contentstore.program_index import ProgramESIndex
        ProgramESIndex(
            alias=ProgramESIndex.INDEX_ALIAS_NAME,
            current_site_domain=self._current_site_domain
        ).add_new_program(
            new_program_uuid
        )

        log.info('User {} created learning path "{}", path_id: {}'.format(
            self._post_data['creator_id'], self._post_data['title'], new_program_uuid))
        return api_response


class ProgramListLoader(_Workflow):
    """Retrieve programs list with proxy url"""
    def __init__(self, user, current_site_domain):
        super(ProgramListLoader, self).__init__(
            user,
            required_permissions=STUDIO_VIEW_CONTENT,
            current_site_domain=current_site_domain
        )

    def execute(self):
        """Course registering workflow definitions"""
        # Fetch program list of user
        api_response = self._api_client.programs.get()

        return api_response


class ProgramLoader(_Workflow):
    """Retrieve a program detail with proxy url"""
    def __init__(self, user, program_uuid, additional=True, current_site_domain=None):
        """Constructor

            @param additional:  a flag for adding additional info.
            @type additional:   boolean
        """
        super(ProgramLoader, self).__init__(
            user,
            program_uuid,
            required_permissions=STUDIO_VIEW_CONTENT,
            current_site_domain=current_site_domain
        )
        self._additional = additional

    def execute(self):
        """
            1. Load all fields from Mysql exception program's Courses List
            2. Displace Program status with value in MongoDB Draft Program Collection.
        """
        # 1. Sync. prod/draft program detail data from Service discovery into MongoDB.
        draft_program = self.initialize_program_detail_to_draftdb()
        draft_program_courses = draft_program['courses']
        _filter = {
            r'data': {
                r'courses': None
            }
        } \
            if draft_program_courses is None \
            else {  # Generate argument for `Draft Program Courses UUIDs`
                r'data': {
                    r'courses': [
                        course[r'uuid'] for course in draft_program_courses
                    ]
                }
            }

        # 2. Fetch program detail by program uuid
        #   We also could specify program courses uuids as argument: `courses`. Sample as follow:
        #   data={'courses': ['d591f0a5-92d4-47ba-8f21-bf938e559885', 'cf5fe179-8395-4a30-85ed-a4ebfa00b715']})
        api_response = self._overwrite_get_method_for_slumber(
            getattr(
                self._api_client.programs,
                self._program_uuid
            )
        ).get(**_filter)

        # Flag = true: private courses included LP. field `visibility` cannot be changed.
        api_response['is_frozen_visibility'] = draft_program.is_frozen_visibility_status()

        # Refresh courses' attributes in LP
        api_response['courses'] = _ProgramCourses(
            response_data=api_response['courses']
        ).to_list()
        # The program `status` from Draft & Api may be different.
        api_response['status'] = draft_program['status']

        if not self._additional:
            # Fetch & Return raw data only.
            return api_response

        # For creator
        creator_id = api_response.get('creator_id')
        if creator_id:
            users_info = User.objects.filter(id=creator_id)
            if users_info:
                api_response['creator_username'] = users_info[0].username

        # We need it for rendering the range on page
        if draft_program['enrollment_start'] and draft_program['enrollment_start'] != 'is_null':
            api_response['enrollment_start'] = draft_program['enrollment_start']
        if draft_program['enrollment_end'] and draft_program['enrollment_end'] != 'is_null':
            api_response['enrollment_end'] = draft_program['enrollment_end']
        if draft_program['start'] and draft_program['start'] != 'is_null':
            api_response['start'] = draft_program['start']
        if draft_program['end'] and draft_program['end'] != 'is_null':
            api_response['end'] = draft_program['end']

        return api_response


class ProgramCoursesLoader(_Workflow):
    """Retrieve a program courses list with proxy url"""
    def __init__(self, user, program_uuid, query_data=None, current_site_domain=None):
        super(ProgramCoursesLoader, self).__init__(
            user,
            program_uuid,
            required_permissions=STUDIO_VIEW_CONTENT,
            current_site_domain=current_site_domain
        )
        self._query_data = query_data

    def execute(self):
        """Course registering workflow definitions"""
        # 1. Generate Draft Program Courses UUIDs as GET arguments.
        draft_program = self.initialize_program_detail_to_draftdb()
        draft_program_courses = draft_program['courses']
        _filter = {
            r'data': {
                r'courses': None
            }
        } \
            if draft_program_courses is None \
            else {  # Generate argument for `Draft Program Courses UUIDs`
                r'data': {
                    r'courses': [
                        course[r'uuid'] for course in draft_program_courses
                    ]
                }
            }

        # Query Draft Program Courses by `Title`
        query_by_title = self._query_data.get('title')
        if query_by_title:
            _filter['data']['title'] = query_by_title

        # 2. Fetch program detail by program uuid
        #   We also could specify program courses uuids as argument: `courses`. Sample as follow:
        #   data={'courses': ['d591f0a5-92d4-47ba-8f21-bf938e559885', 'cf5fe179-8395-4a30-85ed-a4ebfa00b715']})
        api_courses_response = self._overwrite_get_method_for_slumber(
            getattr(
                self._api_client.programs,
                self._program_uuid
            ).courses
        ).get(**_filter)

        # Refresh courses' attributes in LP
        return _ProgramCourses(response_data=api_courses_response).to_list()


class CoursesLoader(_Workflow):
    """Retrieve all courses with proxy url

        Usage:
            http://0.0.0.0:18010/api/proxy/discovery/api/v1/courses/?title=test_COUrse

            Query by title=???
    """
    def __init__(self, user, params, current_site_domain):
        super(CoursesLoader, self).__init__(
            user,
            current_site_domain=current_site_domain
        )
        self._params = params

    def execute(self):
        """Courses query workflow definitions

            http://0.0.0.0:18381/api/v1/courses/?title=test_COUrse

        """
        # 1. Get courses list which related with User's Courses Team(s)
        api_response = self._api_client.courses.get(
            **self._params
        )

        return api_response


class ProgramCourseRegister(_Workflow):
    """Register course into a program.

        But actually we just affect MongoDb Collection only.
        &
        Don't affect Mysql tables: `program enrollment` and `program courses enrollment`

        POST:
            http://0.0.0.0:18010/api/proxy/discovery/api/v1/programs/b359a4c4-4a1a-487c-906a-3fb89197e5fe/courses/

        Arguments:
            {
                "course_ids": [
                    "course-v1:edX+bcs_101+bcs_2021",
                    "course-v1:edX+DemoX+Demo_Course",
                    ...
                ]
            }
    """
    def __init__(self, user, program_uuid, post_data, current_site_domain=None):
        """
            @param user:             program creator user obj.
            @type user:              object
            @param program_uuid:     program uuid
            @type program_uuid:      string
            @param post_data:        POST data for Course Register http call
            @type post_data:         dict
        """
        super(ProgramCourseRegister, self).__init__(
            user,
            program_uuid,
            required_permissions=STUDIO_EDIT_CONTENT,
            current_site_domain=current_site_domain
        )
        self._post_data = post_data

        if 'course_id' in post_data:
            self._courses_ids = [post_data['course_id']]
        else:
            self._courses_ids = post_data['course_ids']

    def _add_program_users_into_new_course_team(self, course_keys):
        """
            After adding a new Course into a Program,

                then we need to make sure all of users in this program are also need to be added into the CourseTeam of the New Course

            @param course_keys:            Is Course Key class instances list
            @type course_keys:             Course Key class
        """
        for course_key in course_keys:
            # Get users ids of a course team
            existing_course_team_user_ids = {
                id
                for id in CourseAccessRole.objects.filter(
                    course_id=course_key
                ).values_list('user', flat=True)
            }
            # Add users of program team into a course team
            for role in ProgramAccessRole.objects.filter(
                program_id=self._program_uuid
            ).all():
                if role.user.id not in existing_course_team_user_ids:
                    CourseAccessRole(
                        user=role.user,
                        org=course_key.org,
                        course_id=course_key,
                        role=role.role
                    ).save()

    def execute(self):
        """Course registering workflow definitions.

            We only store new course into Program courses List in MongoDB Only.

            Response format as follow:
                [
                    {
                        "title": "Manual Smoke Test Course 1 - Auto",
                        "program_end": "2021-10-10T00:00:00Z",
                        "program_start": "2013-02-05T05:00:00Z",
                        ...
                    },
                    {
                        ...
                    }
                ]
        """
        # 1. Fetch draft program courses data
        draft_program = self.initialize_program_detail_to_draftdb()
        draft_program_mgr = draft_program.get_program_courses_manager()

        course_keys = [
            CourseKey.from_string(key)
            for key in self._courses_ids
            if not draft_program_mgr.has_course(course_run_key=key)
        ]

        # We don't support register "Private" Curses for an "Non-Private" LP.
        if draft_program['visibility'] != PartialProgram.DEF_VISIBILITY_PRIVATE:
            invisible_course_keys = CourseOverview.objects.filter(
                catalog_visibility='none', id__in=course_keys
            ).values_list(
                'id', flat=True
            )
            # We cannot add an "Private" Course into A LP
            for the_invisible in invisible_course_keys:
                course_keys.remove(the_invisible)

        if not course_keys:
            raise ValidationError('Nothing to do Or maybe courses already exist.')

        # 2. Query course info by POST
        api_response = getattr(
            self._api_client.programs,
            self._program_uuid
        ).courses.post(
            data=self._post_data
        )

        if isinstance(api_response, dict) and \
                'api_error_message' in api_response:
            # Got exception, Return raw response data directly.
            return api_response

        # 3. Add new Courses into MongoDB Draft Program data
        for course_in_response in api_response:
            draft_program_mgr.add_draft_course(
                course_in_response
            )

        draft_program['status'] = DraftPartialProgram.DEF_UNPUBLISHED_STATUS
        draft_program.save()                            # Save courses list into MongoDB.

        # 5. Insert all users of program's courses into New course Team.
        self._add_program_users_into_new_course_team(course_keys)
        log.info('User {user_id} added the following coursers into course list: {course_list}, '
                 'Learning Path name: {title}, path_id: {path_id}'.format(user_id=self._user.id,
                                                                          course_list=course_keys,
                                                                          title=draft_program['title'],
                                                                          path_id=self._program_uuid))
        return api_response


class ProgramCourseReorder(_Workflow):
    """Reorder a course to a new position.

        PATCH:
            http://0.0.0.0:18010/api/proxy/discovery/api/v1/programs/b6ca79cf0b5f408ea999e8c0589be5b0/courses/

        Arguments Format as follow:
            Case 1, reorder 1 course:
                {
                    "course_id": "d591f0a5-92d4-47ba-8f21-bf938e559885",
                    "order_no": 0
                }

            Case 2, reorder all courses:
                {
                    "param": [
                        {
                            "course_id": "d591f0a5-92d4-47ba-8f21-bf938e559885",
                            "order_no": 0
                        },
                        {
                            "course_id": "f602e1b6-03e5-58cb-9e32-cg049f660996",
                            "order_no": 3
                        },
                        ...
                    ]
                }

        Response Sample:
                [
                    "e2a6be1b-2add-4234-930b-8c6959de08ae",
                    "d591f0a5-92d4-47ba-8f21-bf938e559885"
                ]

    """
    def __init__(self, user, program_uuid, post_data, current_site_domain=None):
        """
            @param user:            program creator user obj.
            @type user:             object
            @param post_data:       POST data for Program Detail updating http call
            @type post_data:        dict
        """
        super(ProgramCourseReorder, self).__init__(
            user,
            program_uuid,
            required_permissions=STUDIO_EDIT_CONTENT,
            current_site_domain=current_site_domain
        )

        self._post_data = post_data

    def execute(self):
        """Course reorder workflow definitions
        """
        if 'course_id' not in self._post_data and \
                'param' not in self._post_data:
            raise ValidationError('No valid arguments.')

        ret = []
        courses_ids = [self._post_data['course_id']] \
            if 'course_id' in self._post_data \
            else self._post_data['param']

        if not courses_ids:
            raise ValidationError('courses ids list is empty.')

        draft_program = self.initialize_program_detail_to_draftdb()
        draft_program_mgr = draft_program.get_program_courses_manager()

        for course_reorder_info in courses_ids:
            draft_program_mgr.move_course_to_target(
                course_reorder_info['course_id'],
                course_reorder_info['order_no']
            )

            ret.append(
                course_reorder_info['course_id']
            )

        draft_program['status'] = DraftPartialProgram.DEF_UNPUBLISHED_STATUS
        draft_program.save()    # Save courses list into MongoDB.

        return ret


class ProgramPartialUpdate(_Workflow):
    """Partial update a program

        PATCH:
            http://0.0.0.0:18010/api/proxy/discovery/api/v1/programs/b6ca79cf0b5f408ea999e8c0589be5b0/courses/

        Note:
            Replace card image name if PATCH parameter `card_image_url` is a string (Not a MemoFile instance)
    """
    def __init__(self, user, program_uuid, request_obj, current_site_domain=None):
        """
            @param user:            program creator user obj.
            @type user:             object
            @param request_obj:     POST data for Program Partial Updating http call
            @type request_obj:      http request object (fields data && upload files)
        """
        super(ProgramPartialUpdate, self).__init__(
            user,
            program_uuid,
            required_permissions=STUDIO_EDIT_CONTENT,
            current_site_domain=current_site_domain
        )

        if 'card_image_url' in request_obj.data:
            # Remove `card_image_url` because image file already exist in request.FILES
            request_obj.data.pop('card_image_url')

        self._post_data = request_obj.data
        self._post_files = request_obj.FILES

    def _change_courses_enrollments_for_program(self, current_program):
        """Update Tables `programcoursesenrollments`/`coursesenrollments` after
                publishing a new program OR editing a existing program's courses list

            @param previous_program:                previous program obj.
            @type previous_program:                 Draft/PartialProgram
            @param current_program:                 current program obj.
            @type current_program:                  Draft/PartialProgram

        """
        program_uuid = current_program['uuid']

        current_program_course_ids = {
            CourseKey.from_string(course_run['key'])
            for course in current_program['courses']
            for course_run in course['course_runs']
        } \
            if current_program else set()

        if not current_program_course_ids:
            # Expire courses: Set value of program courses enrollments to `inactive`
            ProgramCourseEnrollment.objects.filter(
                program_enrollment__program_uuid=program_uuid,
                status=ProgramCourseEnrollmentStatuses.ACTIVE
            ).update(
                status=ProgramCourseEnrollmentStatuses.INACTIVE
            )

        if current_program_course_ids:
            # Expire courses: Set value of program courses enrollments to `inactive`
            ProgramCourseEnrollment.objects.filter(
                ~Q(course_key__in=current_program_course_ids),
                program_enrollment__program_uuid=program_uuid,
                status=ProgramCourseEnrollmentStatuses.ACTIVE
            ).update(
                status=ProgramCourseEnrollmentStatuses.INACTIVE
            )

            # ****** This would be a LOW Performance. We should Move it into Celery later. ******
            for user in User.objects.filter(
                programenrollment__program_uuid=program_uuid
            ):
                def _get_inactived_program_course_enrollment(enrollments, course_key):
                    for enrollment in enrollments:
                        if enrollment.course_key == course_key:
                            return enrollment

                    return None

                program_enrollment = ProgramEnrollment.objects.get(
                    program_uuid=program_uuid, user=user
                )
                program_courses_enrollments = ProgramCourseEnrollment.objects.filter(
                    program_enrollment=program_enrollment,
                    program_enrollment__user=user,
                    course_key__in=current_program_course_ids
                )
                for course_key in current_program_course_ids:
                    found_program_courses_enrollment = _get_inactived_program_course_enrollment(
                        program_courses_enrollments, course_key
                    )
                    if found_program_courses_enrollment:
                        if found_program_courses_enrollment.status == ProgramCourseEnrollmentStatuses.INACTIVE:
                            found_program_courses_enrollment.status = ProgramCourseEnrollmentStatuses.ACTIVE
                            found_program_courses_enrollment.save()
                    else:
                        course_enrollment = CourseEnrollment.enroll(
                            user, course_key,
                            check_access=False
                        )
                        program_course_enrollment = ProgramCourseEnrollment(
                            program_enrollment=program_enrollment,
                            course_key=course_key,
                            course_enrollment=course_enrollment,
                            status=ProgramCourseEnrollmentStatuses.ACTIVE,
                        )
                        program_course_enrollment.save()

    def execute(self):
        """Program Detail Partial Updating workflow definitions"""
        if not self._post_data and 'card_image_url' not in self._post_files:
            raise ValidationError('Post arguments is empty !')

        is_ready_for_publish = self._post_data.get('status') == DraftPartialProgram.DEF_PUBLISHED_STATUS
        is_ready_for_uploading_img = 'card_image_url' in self._post_files
        last_program_card_image_key = None
        program_card_dfs_handle = PartialProgram.get_program_card_dfs()
        post_arguments = {
                fd: val
                for fd, val in self._post_data.items()
            }
        draft_program = self.initialize_program_detail_to_draftdb()
        trigger_index_by_courses = False        # A Flag for judging the program's courses will be changed
        old_data = {}
        new_data = {}
        for key, value in self._post_data.items():
            if key in ('status', 'durationUnit'):
                continue
            new_data[key] = value
            old_data[key] = draft_program[key]

        if is_ready_for_publish or is_ready_for_uploading_img:
            last_program_card_image_key = draft_program['card_image_url']

            # 1. Get Draft Program courses & prepare `POST dict` for updating
            if is_ready_for_publish:
                # Set `released date` for each publish
                post_arguments['released_date'] = 'auto_updated'
                post_arguments['creator_id'] = self._user.id
                # Specify courses UUIDs which need to be returned from Service Discovery for the current Program
                draft_program_mgr = draft_program.get_program_courses_manager()
                post_arguments['draft_program_courses'] = [
                    course['uuid']
                    for course in draft_program_mgr.to_list()
                ]

            # 2.1. Save program card image into MongoDB.
            if is_ready_for_uploading_img:
                card_image_url = self._post_files.pop('card_image_url')[0]
                post_arguments['card_image_url'] = program_card_dfs_handle.upload_file(
                    card_image_url,
                    self.generate_program_card_image_key(
                        draft_program,
                        specified_file_name=post_arguments.pop('new_card_image_name', None)
                    )  # get Image Key of program card
                )
                new_data['card_image_url'] = card_image_url
                old_data['card_image_url'] = last_program_card_image_key

        # 3. Partial Updating for Program Detail
        api_response = getattr(
            self._api_client.programs,
            self._program_uuid
        ).patch(
            data=post_arguments,
            files=self._post_files
        )

        # 4. Update Draft Program in MongoDB & `Prod. Program` if it's needed to publish.
        if r'program_uuid' in api_response:
            last_program_card_image_key = last_program_card_image_key[1:] \
                if last_program_card_image_key and r'/' == last_program_card_image_key[0] \
                else last_program_card_image_key

            # Delete previous program card image from MongoDB Dfs.
            if last_program_card_image_key and is_ready_for_uploading_img:
                program_card_dfs_handle.delete_file(last_program_card_image_key)
                draft_program['card_image_url'] = post_arguments['card_image_url']

            # (*** Force ***) Updating Draft from Service Discovery URI
            # &&
            # (WARNING) The Published record would be overwrote to draft record. So we need to
            # recover the previous draft courses list laster.
            existing_draft_program = self.initialize_program_detail_to_draftdb(force=True)

            if not is_ready_for_publish:
                # Recover previous status for Fields ( `courses` / `status` )
                existing_draft_program['courses'] = draft_program['courses']    # Need to recover the unpblished courses 4 Draft
                existing_draft_program['status'] = draft_program['status']      # Recover the previous status
                existing_draft_program.save()
                # Update prod. program record
                PartialProgram(
                    init_type=PartialProgram.DEF_INIT_TYPE_IS_RESPONSE,
                    uuid=api_response[r'program_uuid'],
                    draft_obj=existing_draft_program
                ).save(
                    ignored_fields={'courses', 'status'}
                )

            # Publish program `Draft` to `Production` while clicking button `publish`.
            if is_ready_for_publish:
                deleted_prod_program = PartialProgram.delete(
                    api_response[r'program_uuid']
                )
                # Set Draft Program `status` with value `active` after publishing it.
                existing_draft_program['status'] = DraftPartialProgram.DEF_PUBLISHED_STATUS
                existing_draft_program.save()
                PartialProgram(
                    init_type=PartialProgram.DEF_INIT_TYPE_IS_NEW,
                    uuid=api_response[r'program_uuid'],
                    draft_obj=existing_draft_program
                ).save()
                # Update program's courses enrollments after publishing.
                self._change_courses_enrollments_for_program(
                    current_program=existing_draft_program
                )
                # A Flag For : Trigger program index updating
                draft_courses_len = len(existing_draft_program['courses']) \
                    if existing_draft_program and existing_draft_program['courses'] else 0
                prod_courses_len = len(deleted_prod_program['courses']) \
                    if deleted_prod_program and 'courses' in deleted_prod_program else 0
                trigger_index_by_courses = draft_courses_len != prod_courses_len

            # Update program index if we edited the fields `title` OR `courses`
            if r'title' in post_arguments or \
                    trigger_index_by_courses or \
                    r'language' in post_arguments or \
                    is_ready_for_uploading_img or \
                    r'visibility' in post_arguments:
                from cms.djangoapps.contentstore.program_index import ProgramESIndex
                ProgramESIndex(
                    alias=ProgramESIndex.INDEX_ALIAS_NAME,
                    current_site_domain=self._current_site_domain
                ).update_program(
                    self._program_uuid
                )

        for attr, val in new_data.items():
            log.info('User {user_id} edited "{attribute}" from "{old_val}" to "{new_val}", '
                     'Learning Path name: {title}, path_id: {path_id}'.format(user_id=self._user.id, attribute=attr,
                                                 title=draft_program['title'],
                                                 old_val=old_data[attr],
                                                 new_val=val,
                                                 path_id=self._program_uuid))

        if 'status' in self._post_data and self._post_data['status'] == 'active':
            log.info('User {} published Learning Path "{}", path_id: {}'.format(
                self._user.id, draft_program['title'], self._program_uuid))
        return api_response


class ProgramEraser(_Workflow):
    """Delete a program with proxy url

        - Delete program record.
        - Delete program access roles.
        - Delete program enrollment records.
        - Delete program data from MongoDB.
        - Delete program from ES index.

        Platform Admin / Super Admin could delete any program, Or
            The current user should exists in program teams.

    """
    def __init__(self, user, program_uuid, current_site_domain=None):
        super(ProgramEraser, self).__init__(
            user,
            program_uuid,
            required_permissions=STUDIO_EDIT_CONTENT,
            current_site_domain=current_site_domain
        )

    def execute(self):
        # 2. Delete program
        caller = getattr(
            self._api_client.programs,
            self._program_uuid
        )

        api_response = self._overwrite_delete_method_for_slumber(
            caller
        ).delete()

        if 'program_uuid' in api_response:
            # 3. Delete all roles for this progarm
            ProgramAccessRole.objects.filter(
                program_id=self._program_uuid
            ).delete()
            # 4. Delete program enrollment
            # Because program enrollment would never be removed until delete this program.
            program_enrollments_ids = [
                id
                for id in ProgramEnrollment.objects.filter(
                    program_uuid__in=[self._program_uuid]
                ).values_list(
                    'id', flat=True
                ).all()
            ]
            ProgramEnrollment.objects.filter(
                program_uuid=self._program_uuid
            ).delete()
            ProgramCourseEnrollment.objects.filter(
                program_enrollment_id__in=program_enrollments_ids
            ).delete()
            # 5. Delete from MongoDB
            deleted_program = PartialProgram.delete(self._program_uuid)
            deleted_draft_program = DraftPartialProgram.delete(self._program_uuid)

            if deleted_program or deleted_draft_program:
                # delete program card image
                program_card_image_key = deleted_program['card_image_url'] \
                    if deleted_program \
                    else deleted_draft_program['card_image_url']

                if program_card_image_key:
                    program_card_dfs_handle = PartialProgram.get_program_card_dfs()
                    program_card_image_key = program_card_image_key[1:] \
                        if program_card_image_key and r'/' == program_card_image_key[0] \
                        else program_card_image_key
                    try:
                        program_card_dfs_handle.delete_file(program_card_image_key)
                    except Exception:
                        pass

            log.info('User {user_id} delete the Learning Path "{title}", path_id: {path_id}'.format(
                user_id=self._user.id, title=deleted_draft_program['title'], path_id=self._program_uuid
            ))

            # 6. Delete program from ES index.
            from cms.djangoapps.contentstore.program_index import ProgramESIndex
            ProgramESIndex(
                alias=ProgramESIndex.INDEX_ALIAS_NAME,
                current_site_domain=self._current_site_domain
            ).delete_program(
                self._program_uuid
            )

        return api_response


class ProgramCourseEraser(_Workflow):
    """Delete a course from a program courses list with proxy url

        Note:
            We just remove courses from Draft program courses list,

                But don't remove this from Mysql, Until we `publish` the Program.

        Arguments sample:
            {
                "course_ids": [
                    "course-v1:edX+bcs_101+bcs_2021",
                    "course-v1:edX+DemoX+Demo_Course"
                ]
            }

        Response sample:
            {
                "course_ids": [
                    "e2a6be1b-2add-4234-930b-8c6959de08ae",
                    "d591f0a5-92d4-47ba-8f21-bf938e559885"
                ]
            }

    """
    def __init__(self, user, program_uuid, params, current_site_domain=None):
        super(ProgramCourseEraser, self).__init__(
            user,
            program_uuid,
            required_permissions=STUDIO_EDIT_CONTENT,
            current_site_domain=current_site_domain
        )
        self._course_ids = params['course_ids']

        if not self._course_ids:
            raise ValidationError('Argument: `course_ids` is empty.')

    def execute(self):
        draft_program = self.initialize_program_detail_to_draftdb()
        draft_program_mgr = draft_program.get_program_courses_manager()

        for course_id in self._course_ids:
            draft_program_mgr.delete_draft_course(
                course_id=course_id
            )

        draft_program['status'] = DraftPartialProgram.DEF_UNPUBLISHED_STATUS
        draft_program.save()                         # Save courses list into MongoDB.
        log.info('User {user_id} removed the following coursers from course list: {course_list}, '
                 'Learning Path name: {title}, path_id: {path_id}'.format(user_id=self._user.id,
                                                                          course_list=self._course_ids,
                                                                          title=draft_program['title'],
                                                                          path_id=self._program_uuid))

        return {
            'course_ids': self._course_ids
        }
