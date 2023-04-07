"""
Fragments for rendering programs.
"""
import json

from django.http import Http404
from django.template.loader import render_to_string
from django.utils.translation import get_language_bidi
from django.urls import reverse

from web_fragments.fragment import Fragment

from lms.djangoapps.commerce.utils import EcommerceService
from lms.djangoapps.learner_dashboard.utils import FAKE_COURSE_KEY, strip_course_id
from lms.djangoapps.program_enrollments.persistance.programs import PartialProgram
from lms.djangoapps.program_enrollments.persistance.programs_statistics import ProgramsCompletionStatistics
from openedx.core.djangoapps.credentials.utils import get_credentials_records_url
from openedx.core.djangoapps.plugin_api.views import EdxFragmentView
from openedx.core.djangoapps.programs.models import ProgramsApiConfig
from openedx.core.djangoapps.programs.utils import (
    ProgramDataExtender,
    ProgramProgressMeter,
    get_certificates,
    get_program_marketing_url
)
from openedx.core.djangoapps.user_api.preferences.api import get_user_preferences
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from django.conf import settings
from common.djangoapps.student.triboo_groups import CATALOG_DENIED_GROUP

class ProgramsFragmentView(EdxFragmentView):
    """
    A fragment to program listing.
    """
    def render_to_fragment(self, request, **kwargs):
        """
        Render the program listing fragment.
        """
        user = request.user

        if not ProgramsApiConfig.is_student_dashboard_enabled() or not user.is_authenticated:
            return None

        programs_config = kwargs.get('programs_config') or ProgramsApiConfig.current()
        programs_stat = ProgramsCompletionStatistics(
            request.user,
            sorted_by_enrollment_date=True
        )
        programs = programs_stat.engaged_programs[:4]
        progress = programs_stat.progress
        catalog_enabled = configuration_helpers.get_value(
            'COURSES_ARE_BROWSABLE',
            settings.FEATURES.get('COURSES_ARE_BROWSABLE', False)
        ) and CATALOG_DENIED_GROUP not in [group.name for group in user.groups.all()]

        context = {
            'marketing_url': get_program_marketing_url(programs_config),
            'programs': programs,
            'progress': progress,
            'catalog_enabled': catalog_enabled,
        }
        html = render_to_string('learner_dashboard/programs_fragment.html', context)
        programs_fragment = Fragment(html)
        self.add_fragment_resource_urls(programs_fragment)

        return programs_fragment

    def css_dependencies(self):
        """
        Returns list of CSS files that this view depends on.

        The helper function that it uses to obtain the list of CSS files
        works in conjunction with the Django pipeline to ensure that in development mode
        the files are loaded individually, but in production just the single bundle is loaded.
        """
        if get_language_bidi():
            return self.get_css_dependencies('style-learner-dashboard-rtl')
        else:
            return self.get_css_dependencies('style-learner-dashboard')


class ProgramDetailsFragmentView(EdxFragmentView):
    """
    Render the program details fragment.
    """
    def render_to_fragment(self, request, program_uuid, **kwargs):
        """View details about a specific program."""
        if not ProgramsApiConfig.is_student_dashboard_enabled() or not request.user.is_authenticated:
            return None

        # programs_config = kwargs.get('programs_config') or ProgramsApiConfig.current()
        meter = ProgramProgressMeter(request.site, request.user, uuid=program_uuid)
        program_data = meter.programs[0]

        if not program_data:
            raise Http404

        try:
            mobile_only = json.loads(request.GET.get('mobile_only', 'false'))
        except ValueError:
            mobile_only = False

        program_data = ProgramDataExtender(program_data, request.user, mobile_only=mobile_only).extend()
        course_data = meter.progress(programs=[program_data], count_only=False)[0]
        certificate_data = get_certificates(request.user, program_data)

        program_data.pop('courses')
        skus = program_data.get('skus')
        ecommerce_service = EcommerceService()

        # TODO: Don't have business logic of course-certificate==record-available here in LMS.
        # Eventually, the UI should ask Credentials if there is a record available and get a URL from it.
        # But this is here for now so that we can gate this URL behind both this business logic and
        # a waffle flag. This feature is in active developoment.
        program_record_url = get_credentials_records_url(program_uuid=program_uuid)
        if not certificate_data:
            program_record_url = None

        urls = {
            'program_listing_url': reverse('program_listing_view'),
            'track_selection_url': strip_course_id(
                reverse('course_modes_choose', kwargs={'course_id': FAKE_COURSE_KEY})
            ),
            'commerce_api_url': reverse('commerce_api:v0:baskets:create'),
            'buy_button_url': ecommerce_service.get_checkout_page_url(*skus),
            'program_record_url': program_record_url,
        }

        context = {
            'urls': urls,
            'user_preferences': get_user_preferences(request.user),
            'program_data': program_data,
            'course_data': course_data,
            'certificate_data': certificate_data
        }

        html = render_to_string('learner_dashboard/program_details_fragment.html', context)
        program_details_fragment = Fragment(html)
        self.add_fragment_resource_urls(program_details_fragment)
        return program_details_fragment

    def css_dependencies(self):
        """
        Returns list of CSS files that this view depends on.

        The helper function that it uses to obtain the list of CSS files
        works in conjunction with the Django pipeline to ensure that in development mode
        the files are loaded individually, but in production just the single bundle is loaded.
        """
        if get_language_bidi():
            return self.get_css_dependencies('style-learner-dashboard-rtl')
        else:
            return self.get_css_dependencies('style-learner-dashboard')
