"""
    Program team members list.

    Add/Delete team members & member roles.

"""
import logging

from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie

from edxmako.shortcuts import render_to_response
from student.roles import studio_login_required


log = logging.getLogger(__name__)


class ProgramTeamMembers(View):
    """Progream Team management page view.
    """
    TEMPLATE_PATH = r'program_team_members.html'

    @method_decorator(studio_login_required)
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        """Show program team members management page.
        """
        return render_to_response(
            self.TEMPLATE_PATH,
            {
                'program_uuid': request.GET['program_uuid'],
                'language_code': request.LANGUAGE_CODE,
            }
        )
