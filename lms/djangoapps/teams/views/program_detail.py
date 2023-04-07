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
from util.json_request import JsonResponse


log = logging.getLogger(__name__)


class ProgramDetail(View):
    """Progream Team management page view.
    """
    TEMPLATE_PATH = r'program_detail.html'

    @method_decorator(studio_login_required)
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        """Show program team members management page.
        """
        # check user permission who can delete the course, only platform staff can delete course
        enable_delete_program = request.user.is_staff or request.user.is_superuser

        return render_to_response(
            self.TEMPLATE_PATH,
            {
                'enable_delete_program': JsonResponse(enable_delete_program).getvalue()
            }
        )
