import logging

from datetime import datetime
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from opaque_keys.edx.keys import CourseKey
from pytz import UTC

from edxmako.shortcuts import render_to_response
from lms.djangoapps.courseware.courses import get_courses, sort_by_announcement, sort_by_start_date
from lms.djangoapps.external_catalog.utils import get_external_catalog_url_by_user
from lms.djangoapps.program_enrollments.persistance.programs import PartialProgram
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from openedx.core.djangoapps.models.course_details import CourseDetails
from openedx.core.djangoapps.programs.models import ProgramsApiConfig
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from search.api import QueryParseError, course_discovery_search
from util.json_request import JsonResponse
from xmodule.modulestore.django import modulestore
from xmodule import course_metadata_utils


log = logging.getLogger(__name__)


class OverviewPage(View):
    """Overview Page of Courses & Programs"""
    TEMPLATE_PATH = r'courseware/courses_overview.html'

    @method_decorator(login_required)
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        """Show `programs` / `courses` overview page"""
        if not ProgramsApiConfig.is_student_dashboard_enabled():
            raise Http404       # Raise 404 Exception if program feature is disabled.

        # Only take 4 programs' details.
        _filter = {
            'status': 'active',
            # We deem it as "Public LearningPaths" if the LP is not assigned with any visibility value (old LPs.)
            'visibility': {'$in': (PartialProgram.DEF_VISIBILITY_FULL_PUBLIC, None)}
        }
        programs = [
            program.to_dict()
            for program in PartialProgram.query(
                _filter, limit=4
            )
        ]
        for p in programs:
            if p['start'] == 'is_null':
                p['non_started'] = False
            elif type(p['start']) in (unicode, str):
                try:
                    program_start = datetime.strptime(p['start'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)
                    p['non_started'] = not course_metadata_utils.has_course_started(program_start)
                except Exception as e:
                    p['non_started'] = False
            else:
                p['non_started'] = not course_metadata_utils.has_course_started(p['start'])

        # Courses from Elasticsearch.
        courses = course_discovery_search(
            size=8,
            include_course_filter=True
        )['results']

        def gen_course(course):
            course_id = course['id']
            course_key = CourseKey.from_string(course_id)
            course_descriptor = modulestore().get_course(course_key)

            course_duration_value = 0
            course_duration_unit = ''
            course_duration = CourseDetails.fetch_about_attribute(
                course_key, 'duration'
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
                'title': course['content'].get('display_name', ''),
                'start': course.get('start'),
                'end': course.get('end'),
                'image_url': course.get('image_url'),
                'language': course.get('language'),
                'org': course.get('org'),
                'progress': int(
                    CourseGradeFactory().get_course_completion_percentage(
                        request.user, course_key
                    ) * 100
                ),
                'duration': course_duration_value,
                'duration_unit': course_duration_unit,
                'badge': CourseGradeFactory().get_nb_trophies_possible(course_descriptor),
                'non_started': not course_metadata_utils.has_course_started(
                    datetime.strptime(course.get('start').replace(
                        '+00:00', ''), '%Y-%m-%dT%H:%M:%S').replace(tzinfo=UTC)
                )
            }

        courses = [
            gen_course(course['data'])
            for course in courses[:8]
        ]

        return render_to_response(
            self.TEMPLATE_PATH,
            {
                'is_program_enabled': ProgramsApiConfig.is_student_dashboard_enabled() and len(programs),
                'programs': JsonResponse(programs).getvalue(),
                'courses': JsonResponse(courses).getvalue(),
                'external_button_url': get_external_catalog_url_by_user(request.user),
            }
        )
