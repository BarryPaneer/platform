from collections import namedtuple

import search

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import (
    PermissionDenied,
    ValidationError
)
from django.forms import CharField, Form
from rest_framework.generics import ListAPIView

from branding import get_visible_courses
from lms.djangoapps.program_enrollments.programs import CoursesLoader
from lms.djangoapps.program_enrollments.programs import ProgramCoursesLoader
from edx_rest_framework_extensions.paginators import NamespacedPageNumberPagination
from cms.djangoapps.contentstore.api.serializers import CourseSerializer
from cms.djangoapps.api.proxy.views import DiscoveryRequestProxy
from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, view_auth_classes


class _CourseListGetArgsForm(Form):
    """A form to validate query parameters in the course list retrieval endpoint
    """
    search_term = CharField(required=False)
    org = CharField(required=False)
    display_name = CharField(required=False)

    # White list of all supported filter fields
    filter_type = namedtuple(
        'filter_type', ['param_name', 'field_name']
    )
    supported_filters = [
        filter_type(
            param_name='display_name',
            field_name='display_name__icontains'
        ),
    ]

    def clean(self):
        """Return cleaned data, including additional filters.
        """
        cleaned_data = super(_CourseListGetArgsForm, self).clean()

        # create a filter for all supported filter fields
        filter_ = dict()
        for supported_filter in self.supported_filters:
            if cleaned_data.get(supported_filter.param_name) is not None:
                filter_[supported_filter.field_name] = cleaned_data[supported_filter.param_name]
        cleaned_data['filter_'] = filter_ or None

        return cleaned_data


@view_auth_classes(is_authenticated=False)
class UserCourseListView(DeveloperErrorViewMixin, ListAPIView):
    """Query all courses in user's courses Team(s)

        Similar with:
            http://edx.devstack.lms/api/courses/v1/courses/?username=edx&display_name=course

        So, we Reusing the query component of `lms.djangoapps.course_api.views.CourseListView`

    """

    pagination_class = NamespacedPageNumberPagination
    pagination_class.max_page_size = 100
    pagination_class.page_size = 100
    serializer_class = CourseSerializer
    results_size_infinity = 10000

    def get_queryset(self):
        """Return a list of courses visible to the user.
        """
        # Don't support anonymouse user.
        if isinstance(self.request.user, AnonymousUser):
            raise PermissionDenied('permission denied')

        # Parse arguments
        form = _CourseListGetArgsForm(
            self.request.query_params,
            initial={'requesting_user': self.request.user}
        )
        if not form.is_valid():
            raise ValidationError(form.errors)

        # 1. Query courses by user courses Teams(ids)
        db_courses = get_visible_courses(
            org=form.cleaned_data['org'],
            filter_=form.cleaned_data['filter_'],
            teams_courses_user=self.request.user     # Specified user
        )

        # 2. Filter by ES Courses IDs
        search_courses = search.api.course_discovery_search(
            form.cleaned_data['search_term'],
            size=self.results_size_infinity,
        )

        search_courses_ids = {
            course['data']['id']
            for course in search_courses['results']
        }

        db_courses = [
            course for course in db_courses
            if unicode(course.id) in search_courses_ids
        ]

        # 3. Filter by program UUID
        enrolled_program_uuid = self.request.query_params.get(
            'excluded_program_uuid'
        )
        if not enrolled_program_uuid:
            return db_courses

        # Removed courses which already listed in `Draft Program`'s Courses List
        draft_program = ProgramCoursesLoader(
            self.request.user,
            program_uuid=enrolled_program_uuid,
            current_site_domain=DiscoveryRequestProxy.get_site_domain(self.request)
        ).initialize_program_detail_to_draftdb()
        excluded_courses_response = draft_program['courses']

        # Get program courses KEY set obj.
        program_enrolled_courses = {
            course_run['key']
            for course in excluded_courses_response
            for course_run in course['course_runs']
        }

        # Make sure returned courses which are not included in the Program's courses list
        # if argument `excluded_program_uuid` is specified.
        return [
            course
            for course in db_courses
            if unicode(course.id) not in program_enrolled_courses
        ]
