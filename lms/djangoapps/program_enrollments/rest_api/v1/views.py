"""
ProgramEnrollment Views
"""
from uuid import UUID as _UUID

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from edx_rest_framework_extensions import permissions
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.settings import api_settings
from rest_framework.authentication import BasicAuthentication
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet
from rest_framework.viewsets import ViewSet

from lms.djangoapps.program_enrollments.api import (
    fetch_program_enrollments,
    fetch_program_enrollments_by_student,
    write_program_courses_enrollments,
    write_program_enrollment
)
from lms.djangoapps.program_enrollments.constants import (
    ProgramEnrollmentStatuses,
    ProgramCourseEnrollmentStatuses
)
from lms.djangoapps.program_enrollments.persistance.programs import PartialProgram


class EnrollmentWriteMixin:
    """
    Common functionality for viewsets with enrollment-writing POST/PATCH/PUT methods.

    """
    create_update_by_write_method = {
        'POST': (True, False),
        'PATCH': (False, True),
        'PUT': (True, True),
    }


class PaginatedAPIView(APIView):
    """
    An `APIView` class enhanced with the pagination methods of `GenericAPIView`.
    """
    # pylint: disable=attribute-defined-outside-init
    @property
    def paginator(self):
        """
        The paginator instance associated with the view, or `None`.
        """
        if not hasattr(self, '_paginator'):
            if self.pagination_class is None:
                self._paginator = None
            else:
                self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, queryset):
        """
        Return a single page of results, or `None` if pagination is disabled.
        """
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        """
        Return a paginated style `Response` object for the given output data.
        """
        assert self.paginator is not None
        return self.paginator.get_paginated_response(data)


class UserReadView(GenericViewSet):
    """Used for grabing arguments from url only."""
    lookup_field = r'name'
    lookup_value_regex = r'(.)+'


class UserProgramsAccessView(EnrollmentWriteMixin, ViewSet):
    """Users' programs enrollments management."""
    authentication_classes = (SessionAuthentication, BasicAuthentication)
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, user_name):
        """
            Fetch & Return programs of user by enrollment status & program title

            Args:
                title:
                    query condition (programs titles need to contain this substring)

                exclude_enrolled_flag:  (Values: 1/0)
                    0: include the enrolled programs of the user only.
                    1: need to exclude the programs with enrollment status `enrolled`.

                lp_loading_policy: (Values: 1/0)
                    0: PartialProgram.POLICY_FULLY_LOADED : load LP + LP courses attributes ( Default )
                    1: PartialProgram.POLICY_LOAD_LP_ONLY : load LP attributes Only

            Usages:
                A) List all enrolled progorams of a user:
                    /api/program_enrollments/v1/users/edx/programs/?exclude_enrolled_flag=0&lp_loading_policy=1

                B) List all unenrolled programs (status == `canceled` + programs doesnt in table enrollment) of a user:
                    /api/program_enrollments/v1/users/edx/programs/?exclude_enrolled_flag=1&lp_loading_policy=1

        """
        query_user = User.objects.get(username=user_name)
        exclude_enrolled_flag = int(request.GET.get('exclude_enrolled_flag', 0))
        lp_loading_policy = int(request.GET.get('lp_loading_policy', PartialProgram.POLICY_FULLY_LOADED))
        if lp_loading_policy not in PartialProgram.POLICY_ALL:
            raise ValidationError(r'Invalid LearningPath loading policy : {}'.format(lp_loading_policy))

        # Get mapping of `program uuid` ---> program enrollment status
        program_enrollments = fetch_program_enrollments_by_student(
            user=query_user
        )
        uuid_2_enrollment_status = {
            str(enrollment.program_uuid): {
                'status': enrollment.status,
                'created': enrollment.created,
                'completed': enrollment.completed
            }
            for enrollment in program_enrollments
        }
        enrolled_programs_uuids = [
            program_uuid
            for program_uuid, program_status in uuid_2_enrollment_status.items()
            if program_status['status'] == ProgramEnrollmentStatuses.ENROLLED
        ]

        # Fetch programs list
        if 1 == exclude_enrolled_flag:
            # Return `canceled/... programs` + `programs which are not in table enrollments`
            _filter_of_the_enrolled = {
                '_id': {
                    '$nin': enrolled_programs_uuids
                }
            }
        else:
            # Return enrolled programs of a user
            _filter_of_the_enrolled = {
                '_id': {
                    '$in': enrolled_programs_uuids
                }
            }

        programs = [
            program.to_dict()
            for program in PartialProgram.query(
                _filter_of_the_enrolled,
                sort_args=['+lowercase_title', '-start'],
                loading_policy=lp_loading_policy
            )
        ]

        # Added field `program status` to program & filter by field `title`
        filtered_programs = []
        search_title = request.GET['title'].lower() \
            if 'title' in request.GET \
            else None

        for program in programs:
            if search_title:
                if search_title not in program['title'].lower():
                    continue

            enrollment_record = uuid_2_enrollment_status.get(
                program['uuid'], None
            )
            program['enrollment_status'] = enrollment_record['status'] if enrollment_record else None
            program['enrollment_created'] = enrollment_record['created'] if enrollment_record else None
            program['enrollment_completed'] = enrollment_record['completed'] if enrollment_record else None

            filtered_programs.append(program)

        if api_settings.DEFAULT_PAGINATION_CLASS:
            paginator = api_settings.DEFAULT_PAGINATION_CLASS()
            page_data = paginator.paginate_queryset(
                filtered_programs, request
            )

            return paginator.get_paginated_response(page_data)

        else:
            return Response(filtered_programs)

    def create(self, request, user_name, *args, **kwargs):
        """Enroll a user into a Program"""
        program_uuid = request.data['uuid']
        need_cascade_courses = True \
            if int(request.data.get('cascade_courses', 0)) in (1, '1') \
            else False

        program_enrollment_status = request.data['status']
        if program_enrollment_status not in ProgramEnrollmentStatuses.__ALL__:
            raise ValidationError(
                r'Invalid program enrollment status : {}'.format(program_enrollment_status)
            )

        user = User.objects.get(username=user_name)
        existing_enrollment = fetch_program_enrollments(
            program_uuid=program_uuid,
            users=[user.id]
        )
        # Consider the situation when enrollment already exist.
        # - give up loading from `self.create_update_by_write_method`
        create, update = (True, False) \
            if not existing_enrollment \
            else (False, True)
        # Enroll a program
        write_program_enrollment(
            program_uuid,
            {
                'username': user_name,
                'status': program_enrollment_status
            },
            create, update
        )

        if need_cascade_courses:
            # Enroll all courses of this program for user.
            program = PartialProgram.query_one(
                {'_id': program_uuid}
            )
            program_course_keys = [
                CourseKey.from_string(course_run['key'])
                for course in program['courses'] for course_run in course['course_runs']
            ] if program else []

            if not program_course_keys:
                raise ValidationError(r'This program has not related with any courses.')

            write_program_courses_enrollments(
                program_uuid,
                program_course_keys,
                {
                    'username': user_name,
                    'status': ProgramCourseEnrollmentStatuses.ACTIVE
                    if program_enrollment_status not in [
                        ProgramEnrollmentStatuses.CANCELED,
                        ProgramEnrollmentStatuses.ENDED
                    ]
                    else ProgramCourseEnrollmentStatuses.INACTIVE
                },
                create,
                update,
            )

        return Response(
            {'program_uuid': program_uuid},
            status=status.HTTP_201_CREATED
        )

    def patch(self, request, user_name):
        """Change enrollment status for a user"""
        program_uuid = request.data['uuid']
        need_cascade_courses = True \
            if int(request.data.get('cascade_courses', 0)) in (1, '1') \
            else False
        program_enrollment_status = request.data['status']
        if program_enrollment_status not in ProgramEnrollmentStatuses.__ALL__:
            raise ValidationError(
                r'Invalid program enrollment status : {}'.format(program_enrollment_status)
            )

        create, update = self.create_update_by_write_method[self.request.method]

        write_program_enrollment(
            program_uuid,
            {
                'username': user_name,
                'status': program_enrollment_status
            },
            create, update
        )

        # Only allow enroll all courses while enrolling a program.
        # Forbid unenroll courses while unenrolling a program.
        is_activated_op = program_enrollment_status not in [
            ProgramEnrollmentStatuses.CANCELED,
            ProgramEnrollmentStatuses.ENDED
        ]
        if need_cascade_courses:
            # Enroll all courses of this program for user.
            program = PartialProgram.query_one(
                {'_id': program_uuid}
            )
            program_course_keys = [
                CourseKey.from_string(course_run['key'])
                for course in program['courses'] for course_run in course['course_runs']
            ] if program else []

            if not program_course_keys:
                raise ValidationError(r'This program has not related with any courses.')

            program_course_enrollment_status = ProgramCourseEnrollmentStatuses.ACTIVE \
                if is_activated_op \
                else ProgramCourseEnrollmentStatuses.INACTIVE
            write_program_courses_enrollments(
                program_uuid,
                program_course_keys,
                {
                    'username': user_name,
                    'status': program_course_enrollment_status
                },
                create,
                update,
            )

        return Response(
            {'program_uuid': program_uuid},
            status=status.HTTP_200_OK
        )


class UserProgramCoursesAccessView(EnrollmentWriteMixin, ModelViewSet):
    """Users' program courses enrollments management."""
    authentication_classes = (SessionAuthentication, BasicAuthentication)
    permission_classes = (permissions.IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        """Enroll all courses in a program for user"""
        program_uuid = str(_UUID(self.kwargs['program_pk']))
        user_name = self.kwargs['user_name']
        program_course_keys = [CourseKey.from_string(request.data['course_id'])] \
            if 'course_id' in request.data else []
        create, update = self.create_update_by_write_method[self.request.method]

        if not program_course_keys and 'course_uuid' in request.data:
            course_uuid = request.data['course_uuid']
            program = PartialProgram.query_one(
                {
                    '_id': program_uuid,
                    'courses.uuid': course_uuid
                }
            )
            program_course_keys = [
                CourseKey.from_string(course_run['key'])
                for course in program['courses']
                for course_run in course['course_runs']
                if course['uuid'] == course_uuid
            ] if program else []

        if not program_course_keys:
            program = PartialProgram.query_one(
                {'_id': program_uuid}
            )
            program_course_keys = [
                CourseKey.from_string(course_run['key'])
                for course in program['courses'] for course_run in course['course_runs']
            ] if program else []

        if not program_course_keys:
            raise ValueError('This program has not related with any courses.')

        results = write_program_courses_enrollments(
            program_uuid,
            program_course_keys,
            {
                'username': user_name,
                'status': request.data['status']
            },
            create,
            update,
        )

        return Response(results, status=status.HTTP_201_CREATED)

    def patch(self, request, *args, **kwargs):
        """Enroll / Unenroll all courses in a program for user"""
        program_uuid = str(_UUID(self.kwargs['program_pk']))
        user_name = self.kwargs['user_name']
        program_course_keys = [CourseKey.from_string(request.data['course_id'])] \
            if 'course_id' in request.data else []
        create, update = self.create_update_by_write_method[self.request.method]

        if not program_course_keys and 'course_uuid' in request.data:
            course_uuid = request.data['course_uuid']
            program = PartialProgram.query_one(
                {
                    '_id': program_uuid,
                    'courses.uuid': course_uuid
                }
            )
            program_course_keys = [
                CourseKey.from_string(course_run['key'])
                for course in program['courses']
                for course_run in course['course_runs']
                if course['uuid'] == course_uuid
            ] if program else []

        if not program_course_keys:
            program = PartialProgram.query_one(
                {'_id': program_uuid}
            )
            program_course_keys = [
                CourseKey.from_string(course_run['key'])
                for course in program['courses'] for course_run in course['course_runs']
            ] if program else []

        if not program_course_keys:
            raise ValueError('This program has not related with any courses.')

        results = write_program_courses_enrollments(
            program_uuid,
            program_course_keys,
            {
                'username': user_name,
                'status': request.data['status']
            },
            create,
            update,
        )

        return Response(results, status=status.HTTP_201_CREATED)
