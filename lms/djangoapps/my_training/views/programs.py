import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie

from edxmako.shortcuts import render_to_response
from lms.djangoapps.program_enrollments.persistance.programs_statistics import ProgramsCompletionStatistics
from openedx.core.djangoapps.programs.models import ProgramsApiConfig
from util.json_request import JsonResponse


log = logging.getLogger(__name__)


class MyTrainingProgramsPage(View):
    """Programs list Page"""
    TEMPLATE_PATH = r'my_training/programs.html'

    @method_decorator(login_required)
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        """Show `programs` page"""
        if not ProgramsApiConfig.is_student_dashboard_enabled():
            raise Http404       # Raise 404 Exception if program feature is disabled.

        programs_stat = ProgramsCompletionStatistics(
            request.user,
            sorted_by_enrollment_date=True
        )
        programs = programs_stat.engaged_programs
        progress = programs_stat.progress

        return render_to_response(
            self.TEMPLATE_PATH,
            {
                'is_program_enabled': ProgramsApiConfig.is_student_dashboard_enabled() and len(programs),
                'programs': JsonResponse(programs).getvalue(),
                'user_progress': JsonResponse(progress).getvalue(),
            }
        )
