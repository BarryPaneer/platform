import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from opaque_keys.edx.keys import CourseKey

from edxmako.shortcuts import render_to_response
from lms.djangoapps.courseware.courses import get_courses, sort_by_announcement, sort_by_start_date
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from lms.djangoapps.program_enrollments.persistance.programs_statistics import ProgramsCompletionStatistics
from openedx.core.djangoapps.models.course_details import CourseDetails
from openedx.core.djangoapps.programs.models import ProgramsApiConfig
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from student.views import (
    get_course_enrollments,
    get_org_black_and_whitelist_for_site
)
from search.api import QueryParseError, course_discovery_search
from student.triboo_groups import CATALOG_DENIED_GROUP
from util.json_request import JsonResponse
from xmodule.modulestore.django import modulestore


log = logging.getLogger(__name__)


class TrainingOverviewPage(View):
    """Overview Page of Courses & Programs"""
    TEMPLATE_PATH = r'my_training/overview.html'

    @method_decorator(login_required)
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        """Show `programs` / `courses` overview page"""
        if not ProgramsApiConfig.is_student_dashboard_enabled():
            raise Http404       # Raise 404 Exception if program feature is disabled.

        # Only take 4 programs' details.
        programs_stat = ProgramsCompletionStatistics(
            request.user,
            sorted_by_enrollment_date=True
        )
        programs = programs_stat.engaged_programs[:4]
        progress = programs_stat.progress

        # Take 8 courses
        # Get the org whitelist or the org blacklist for the current site
        site_org_whitelist, site_org_blacklist = get_org_black_and_whitelist_for_site()
        course_enrollments = list(
            get_course_enrollments(
                request.user,
                site_org_whitelist,
                site_org_blacklist
            )
        )

        # Referenced from : common/djangoapps/student/views/dashboard.py:924
        def order(course_enrollment):
            """
            This helper function is created to avoid NoneType error raised in test.
            In production, it will return a CourseDescriptor object when we call
            modulestore().get_course
            """
            course_desc = modulestore().get_course(course_enrollment.course_id)

            return course_desc.course_order \
                if course_desc and course_desc.course_order \
                else 999

        # Sorting courses by Field `Course Order`
        course_enrollments.sort(key=order)

        def gen_course(course_overview):
            course_id = str(course_overview.id)
            course_key = CourseKey.from_string(course_id)
            course_descriptor = modulestore().get_course(course_overview.id)

            course_duration_value = 0
            course_duration_unit = ''
            course_duration = CourseDetails.fetch_about_attribute(
                course_overview.id, 'duration'
            )
            duration_availability = False
            if course_duration:
                duration_context = course_duration.strip().split(' ')
                duration_availability = len(duration_context) == 2
            if duration_availability:
                course_duration_value = float(duration_context[0]) \
                    if '.' in duration_context[0] else int(
                        duration_context[0]
                    )
                course_duration_unit = duration_context[1]

            return {
                'id': course_id,
                'course_id': course_id,
                'modified': course_overview.modified,
                'title': course_overview.display_name,
                'start': course_overview.start,
                'end': course_overview.end,
                'non_started': not course_overview.has_started(),
                'image_url': course_overview.course_image_url,
                'language': course_overview.language,
                'org': course_overview.org,
                'progress': int(
                    CourseGradeFactory().get_course_completion_percentage(
                        request.user, course_key
                    ) * 100
                ),
                'duration': course_duration_value,
                'duration_unit': course_duration_unit,
                'badge': CourseGradeFactory().get_nb_trophies_possible(course_descriptor)
            }

        catalog_enabled = configuration_helpers.get_value(
            'COURSES_ARE_BROWSABLE',
            settings.FEATURES.get('COURSES_ARE_BROWSABLE', False)
        ) and CATALOG_DENIED_GROUP not in [group.name for group in request.user.groups.all()]

        courses = [
            gen_course(enrollment.course_overview)
            for enrollment in course_enrollments[:8]
        ] \
            if catalog_enabled \
            else []

        return render_to_response(
            self.TEMPLATE_PATH,
            {
                'is_program_enabled': ProgramsApiConfig.is_student_dashboard_enabled() and len(programs),
                'programs': JsonResponse(programs).getvalue(),
                'user_progress': JsonResponse(progress).getvalue(),
                'courses': JsonResponse(courses).getvalue(),
                'catalog_enabled': catalog_enabled
            }
        )
