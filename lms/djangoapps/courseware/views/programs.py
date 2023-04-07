import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie

from lms.djangoapps.external_catalog.utils import get_external_catalog_url_by_user
from lms.djangoapps.program_enrollments.persistance.programs import PartialProgram
from edxmako.shortcuts import render_to_response
from openedx.core.djangoapps.programs.models import ProgramsApiConfig


log = logging.getLogger(__name__)


class ProgramsPage(View):
    """Programs list Page"""
    TEMPLATE_PATH = r'courseware/programs.html'

    @method_decorator(login_required)
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        """Show `programs` page"""
        if not ProgramsApiConfig.is_student_dashboard_enabled():
            raise Http404       # Raise 404 Exception if program feature is disabled.

        # request data by `def program_discovery(request):` / `url: program_search/`
        return render_to_response(
            self.TEMPLATE_PATH,
            {
                'is_program_enabled': ProgramsApiConfig.is_student_dashboard_enabled() and PartialProgram.count_published_only(),
                'external_button_url': get_external_catalog_url_by_user(request.user),
            }
        )
