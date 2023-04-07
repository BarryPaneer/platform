# -*- coding: utf-8 -*-
"""
Courseware views functions
"""
from __future__ import unicode_literals
import json
import logging
import urllib
from collections import OrderedDict, namedtuple, defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from dateutil import relativedelta

import analytics
from completion.models import BlockCompletion
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.db import transaction
from django.db.models import Q, signals
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect
from django.template.context_processors import csrf
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import urlquote_plus
from django.utils.text import slugify
from django.utils.translation import ugettext as _, ungettext
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.generic import View
from django_countries import countries
from eventtracking import tracker
from ipware.ip import get_ip
from markupsafe import escape
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey
from pytz import UTC, timezone as tz
from rest_framework import status
from six import text_type
from web_fragments.fragment import Fragment

import shoppingcart
import survey.views
from branding.api import get_logo_url
from lms.djangoapps.certificates import api as certs_api
from lms.djangoapps.certificates.models import (
    CertificateStatuses, GeneratedCertificate, CertificateGenerationCourseSetting)
from common.djangoapps.student.auth import STUDIO_EDIT_CONTENT
from course_modes.models import CourseMode, get_course_prices
from courseware.access import has_access, has_ccx_coach_role
from courseware.access_utils import check_course_open_for_learner
from courseware.courses import (
    can_self_enroll_in_course,
    course_open_for_self_enrollment,
    get_course,
    get_course_overview_with_access,
    get_course_with_access,
    get_courses,
    get_current_child,
    get_permission_for_course_about,
    get_studio_url,
    sort_by_announcement,
    sort_by_start_date
)
from courseware.masquerade import setup_masquerade
from courseware.model_data import FieldDataCache
from courseware.models import BaseStudentModuleHistory, StudentModule, XModuleUserStateSummaryField
from courseware.module_render import handle_xblock_callback
from courseware.url_helpers import get_redirect_url
from courseware.user_state_client import DjangoXBlockUserStateClient
from edxmako.shortcuts import marketing_link, render_to_response, render_to_string
from enrollment.api import add_enrollment
from lms.djangoapps.ccx.custom_exception import CCXLocatorValidationException
from lms.djangoapps.commerce.utils import EcommerceService
from lms.djangoapps.courseware.exceptions import CourseAccessRedirect, Redirect
from lms.djangoapps.experiments.utils import get_experiment_user_metadata_context
from lms.djangoapps.grades.config.models import PersistentGradesEnabledFlag
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from lms.djangoapps.grades.models import (
    PersistentCourseGrade,
    PersistentCourseProgress,
    PersistentSubsectionGrade,
    PersistentSubsectionGradeOverride
)
from lms.djangoapps.grades.signals.handlers import recalculate_course_completion_percentage
from lms.djangoapps.instructor.enrollment import (
    uses_shib, send_mail_to_student, get_user_email_language, get_email_params, render_message_to_string
)
from lms.djangoapps.instructor.views.api import require_global_staff
from lms.djangoapps.program_enrollments.api import get_program_course_enrollment
from lms.djangoapps.program_enrollments.persistance.programs import PartialProgram, DraftPartialProgram
from lms.djangoapps.program_enrollments.persistance.programs_statistics import ProgramsCompletionStatistics
from lms.djangoapps.verify_student.services import IDVerificationService
from lms.djangoapps.program_enrollments.api import get_program_enrollment
from lms.djangoapps.external_catalog.utils import get_external_catalog_url_by_user
import lms.lib.comment_client as cc
from lms.djangoapps.program_enrollments.models import ProgramEnrollment
from lms.djangoapps.teams.program_team_roles import ProgramRolesManager

from openedx.core.djangoapps.catalog.utils import get_programs_with_type
from openedx.core.djangoapps.certificates import api as auto_certs_api
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.credit.api import (
    get_credit_requirement_status,
    is_credit_course,
    is_user_eligible_for_credit
)
from openedx.core.djangoapps.models.course_details import CourseDetails
from openedx.core.djangoapps.monitoring_utils import set_custom_metrics_for_course_key
from openedx.core.djangoapps.plugin_api.views import EdxFragmentView
from openedx.core.djangoapps.programs.models import ProgramsApiConfig
from openedx.core.djangoapps.self_paced.models import SelfPacedConfiguration
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.core.djangoapps.util.user_messages import PageLevelMessages
from openedx.core.djangoapps.user_api.accounts.image_helpers import get_profile_image_urls_for_user
from openedx.core.djangolib.markup import HTML, Text
from openedx.features.course_experience import UNIFIED_COURSE_TAB_FLAG, course_home_url_name
from openedx.features.course_experience.course_tools import CourseToolsPluginManager
from openedx.features.course_experience.views.course_dates import CourseDatesFragmentView
from openedx.features.course_experience.views.course_outline import CourseOutlineFragmentView
from openedx.features.course_experience.waffle import waffle as course_experience_waffle
from openedx.features.course_experience.waffle import ENABLE_COURSE_ABOUT_SIDEBAR_HTML
from openedx.features.enterprise_support.api import data_sharing_consent_required
from openedx.core.djangoapps.theming.helpers import get_current_theme
from shoppingcart.utils import is_shopping_cart_enabled
from student.models import CourseAccessRole, CourseEnrollment, UserTestGroup, UserProfile
from student.roles import CourseInstructorRole
from student.helpers import cert_info
from util.cache import cache, cache_if_anonymous
from util.db import outer_atomic
from util.email_utils import send_mail_with_alias as send_mail
from util.json_request import JsonResponse
from util.milestones_helpers import get_prerequisite_courses_display
from util.views import _record_feedback_in_zendesk, ensure_valid_course_key, ensure_valid_usage_key
from util.string_utils import is_str_url
from xmodule import course_metadata_utils
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError, NoPathToItem
from xmodule.tabs import CourseTabList
from xmodule.x_module import STUDENT_VIEW

from ..entrance_exams import user_can_skip_entrance_exam
from ..module_render import get_module, get_module_by_usage_id, get_module_for_descriptor

log = logging.getLogger("edx.courseware")
ilt_log = logging.getLogger("edx.scripts.ilt_hotel_daily_check")
ilt_validation_log = logging.getLogger("edx.scripts.ilt_validation_daily_check")
reminder_log = logging.getLogger("edx.scripts.course_email_reminder")


# Only display the requirements on learner dashboard for
# credit and verified modes.
REQUIREMENTS_DISPLAY_MODES = CourseMode.CREDIT_MODES + [CourseMode.VERIFIED]

CertData = namedtuple(
    "CertData", ["cert_status", "title", "msg", "download_url", "cert_web_view_url"]
)

AUDIT_PASSING_CERT_DATA = CertData(
    CertificateStatuses.audit_passing,
    _('Your enrollment: Audit track'),
    _('You are enrolled in the audit track for this course. The audit track does not include a certificate.'),
    download_url=None,
    cert_web_view_url=None
)

HONOR_PASSING_CERT_DATA = CertData(
    CertificateStatuses.honor_passing,
    _('Your enrollment: Honor track'),
    _('You are enrolled in the honor track for this course. The honor track does not include a certificate.'),
    download_url=None,
    cert_web_view_url=None
)


def _generating_cert_data():
    return CertData(
        CertificateStatuses.generating,
        _("We're working on it..."),
        _(
            "We're creating your certificate. You can keep working in your courses and a link "
            "to it will appear here and on your Dashboard when it is ready."
        ),
        download_url=None,
        cert_web_view_url=None
    )


def _invalid_cert_data():
    return CertData(
        CertificateStatuses.invalidated,
        _('Your certificate has been invalidated'),
        _('Please contact your course team if you have any questions.'),
        download_url=None,
        cert_web_view_url=None
    )


def _requesting_cert_data():
    return CertData(
        CertificateStatuses.requesting,
        _('Congratulations, you qualified for a certificate!'),
        _("You've earned a certificate for this course."),
        download_url=None,
        cert_web_view_url=None
    )


def _instructor_paced_cert_data():
    return CertData(
        CertificateStatuses.unavailable,
        _('Certificate unavailable'),
        _('The certificate is not yet available because it’s an instructor-paced course.'),
        download_url=None,
        cert_web_view_url=None
    )


def _unverified_cert_data():
    return CertData(
        CertificateStatuses.unverified,
        _('Certificate unavailable'),
        _(
            'You have not received a certificate because you do not have a current {platform_name} '
            'verified identity.'
        ).format(platform_name=configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME)),
        download_url=None,
        cert_web_view_url=None
    )


def _not_passing_cert_data():
    return CertData(
        CertificateStatuses.notpassing,
        _('Certificate unavailable'),
        _('You haven’t passed the course.'),
        download_url=None,
        cert_web_view_url=None
    )


def _downloadable_cert_data(download_url=None, cert_web_view_url=None):
    return CertData(
        CertificateStatuses.downloadable,
        _('Your certificate is available'),
        _("You've earned a certificate for this course."),
        download_url=download_url,
        cert_web_view_url=cert_web_view_url
    )


def user_groups(user):
    """
    TODO (vshnayder): This is not used. When we have a new plan for groups, adjust appropriately.
    """
    if not user.is_authenticated:
        return []

    # TODO: Rewrite in Django
    key = 'user_group_names_{user.id}'.format(user=user)
    cache_expiration = 60 * 60  # one hour

    # Kill caching on dev machines -- we switch groups a lot
    group_names = cache.get(key)  # pylint: disable=no-member
    if settings.DEBUG:
        group_names = None

    if group_names is None:
        group_names = [u.name for u in UserTestGroup.objects.filter(users=user)]
        cache.set(key, group_names, cache_expiration)  # pylint: disable=no-member

    return group_names


@ensure_csrf_cookie
@cache_if_anonymous()
def courses(request):
    """
    Render "find courses" page.  The course selection work is done in courseware.courses.

    Logic:
        if [edflex catalog enable + edflex API config set] + user signed in:
           if [crehana catalog enable + crehana API config set]:
               => 3 tabs + we redirect to "All"
           else:
               => no tabs + we display the Edflex catalog
        else:
           if [crehana catalog enable + crehana API config set] + user signed in:
               => no tabs + we display the Crehana catalog
           else:
               => no external catalog
    """

    courses_list = []
    course_discovery_meanings = getattr(settings, 'COURSE_DISCOVERY_MEANINGS', {})
    if not settings.FEATURES.get('ENABLE_COURSE_DISCOVERY'):
        courses_list = get_courses(request.user)

        if configuration_helpers.get_value("ENABLE_COURSE_SORTING_BY_START_DATE",
                                           settings.FEATURES["ENABLE_COURSE_SORTING_BY_START_DATE"]):
            courses_list = sort_by_start_date(courses_list)
        else:
            courses_list = sort_by_announcement(courses_list)

    # Add marketable programs to the context.
    programs_list = get_programs_with_type(request.site, include_hidden=False)
    trans_for_tags = configuration_helpers.get_value('COURSE_TAGS', {})

    student_enrollments_dict = {}
    if not isinstance(request.user, AnonymousUser):
        enrollments = CourseEnrollment.objects.filter(user=request.user, is_active=True)

        for enrollment in enrollments:
            course_id = "%s" % enrollment.course_id
            if enrollment.completed:
                student_enrollments_dict[course_id] = {
                    'completed' : True,
                    'cert_info' : cert_info(request.user, enrollment.course_overview)
                }
            else:
                student_enrollments_dict[course_id] = {
                    'completed' : False,
                    'cert_info' : {}
                }

    return render_to_response(
        "courseware/courses.html",
        {
            'is_program_enabled': ProgramsApiConfig.is_student_dashboard_enabled() and PartialProgram.count_published_only(),
            'courses': courses_list,
            'course_discovery_meanings': course_discovery_meanings,
            'programs_list': programs_list,
            'show_dashboard_tabs': True,
            'trans_for_tags': trans_for_tags,
            'external_button_url': get_external_catalog_url_by_user(request.user),
            'student_enrollments_dict': student_enrollments_dict
        }
    )


@ensure_csrf_cookie
@ensure_valid_course_key
def jump_to_id(request, course_id, module_id):
    """
    This entry point allows for a shorter version of a jump to where just the id of the element is
    passed in. This assumes that id is unique within the course_id namespace
    """
    course_key = CourseKey.from_string(course_id)
    items = modulestore().get_items(course_key, qualifiers={'name': module_id})

    if len(items) == 0:
        raise Http404(
            u"Could not find id: {0} in course_id: {1}. Referer: {2}".format(
                module_id, course_id, request.META.get("HTTP_REFERER", "")
            ))
    if len(items) > 1:
        log.warning(
            u"Multiple items found with id: %s in course_id: %s. Referer: %s. Using first: %s",
            module_id,
            course_id,
            request.META.get("HTTP_REFERER", ""),
            text_type(items[0].location)
        )

    return jump_to(request, course_id, text_type(items[0].location))


@ensure_csrf_cookie
def jump_to(_request, course_id, location):
    """
    Show the page that contains a specific location.

    If the location is invalid or not in any class, return a 404.

    Otherwise, delegates to the index view to figure out whether this user
    has access, and what they should see.
    """
    try:
        course_key = CourseKey.from_string(course_id)
        usage_key = UsageKey.from_string(location).replace(course_key=course_key)
    except InvalidKeyError:
        log.exception("Invalid course_key: %s, or convert to usage_key from location: %s", course_id, location)
        raise Http404(u"Invalid course_key or usage_key")
    try:
        redirect_url = get_redirect_url(course_key, usage_key)
    except ItemNotFoundError:
        log.warning("Can't find item %s for %s, redirect to course home page", usage_key, course_key)
        return redirect('openedx.course_experience.course_home',
                        course_id=course_id)
    except NoPathToItem:
        log.exception("Can't find any path for the item: %s", usage_key)
        raise Http404(u"This location is not in any class: {0}".format(usage_key))

    return redirect(redirect_url)


# def get_resume_course_url(request, course):
#     resume_course_url = reverse(course_home_url_name(course.id), args=[text_type(course.id)])
#     if not isinstance(request.user, AnonymousUser):
#         course_outline_root_block = get_course_outline_block_tree(request, text_type(course.id))
#         resume_block = get_resume_block(course_outline_root_block) if course_outline_root_block else None
#         if resume_block:
#             resume_course_url = resume_block['lms_web_url']
#         elif course_outline_root_block:
#             resume_course_url = course_outline_root_block['lms_web_url']
#     return resume_course_url


def get_last_accessed_courseware(request, course, user=None):
    """
    Returns the courseware module URL that the user last accessed, or None if it cannot be found.
    """
    user = user if user else request.user
    field_data_cache = FieldDataCache.cache_for_descriptor_descendents(
        course.id, user, course, depth=2
    )
    course_module = get_module_for_descriptor(
        user, request, course, field_data_cache, course.id, course=course
    )
    chapter_module = get_current_child(course_module)
    if chapter_module is not None:
        section_module = get_current_child(chapter_module)
        if section_module is not None:
            url = reverse('courseware_section', kwargs={
                'course_id': text_type(course.id),
                'chapter': chapter_module.url_name,
                'section': section_module.url_name
            })
            return url
    return reverse(course_home_url_name(course.id), args=[text_type(course.id)])


@ensure_csrf_cookie
@ensure_valid_course_key
@data_sharing_consent_required
def course_info(request, course_id):
    """
    Display the course's info.html, or 404 if there is no such course.

    Assumes the course_id is in a valid format.
    """

    course_key = CourseKey.from_string(course_id)

    # If the unified course experience is enabled, redirect to the "Course" tab
    if UNIFIED_COURSE_TAB_FLAG.is_enabled(course_key):
        return redirect(reverse(course_home_url_name(course_key), args=[course_id]))

    with modulestore().bulk_operations(course_key):
        course = get_course_with_access(request.user, 'load', course_key)

        staff_access = has_access(request.user, 'staff', course)
        masquerade, user = setup_masquerade(request, course_key, staff_access, reset_masquerade_data=True)

        # LEARNER-612: CCX redirect handled by new Course Home (DONE)
        # LEARNER-1697: Transition banner messages to new Course Home (DONE)
        # if user is not enrolled in a course then app will show enroll/get register link inside course info page.
        user_is_enrolled = CourseEnrollment.is_enrolled(user, course.id)
        show_enroll_banner = request.user.is_authenticated and not user_is_enrolled

        # If the user is not enrolled but this is a course that does not support
        # direct enrollment then redirect them to the dashboard.
        if not user_is_enrolled and not can_self_enroll_in_course(course_key):
            return redirect(reverse('dashboard'))

        # LEARNER-170: Entrance exam is handled by new Course Outline. (DONE)
        # If the user needs to take an entrance exam to access this course, then we'll need
        # to send them to that specific course module before allowing them into other areas
        if not user_can_skip_entrance_exam(user, course):
            return redirect(reverse('courseware', args=[text_type(course.id)]))

        # TODO: LEARNER-611: Remove deprecated course.bypass_home.
        # If the user is coming from the dashboard and bypass_home setting is set,
        # redirect them straight to the courseware page.
        is_from_dashboard = reverse('dashboard') in request.META.get('HTTP_REFERER', [])
        if course.bypass_home and is_from_dashboard:
            return redirect(reverse('courseware', args=[course_id]))

        # Construct the dates fragment
        dates_fragment = None

        if request.user.is_authenticated:
            # TODO: LEARNER-611: Remove enable_course_home_improvements
            if SelfPacedConfiguration.current().enable_course_home_improvements:
                # Shared code with the new Course Home (DONE)
                dates_fragment = CourseDatesFragmentView().render_to_fragment(request, course_id=course_id)

        # This local import is due to the circularity of lms and openedx references.
        # This may be resolved by using stevedore to allow web fragments to be used
        # as plugins, and to avoid the direct import.
        from openedx.features.course_experience.views.course_reviews import CourseReviewsModuleFragmentView

        # Shared code with the new Course Home (DONE)
        # Get the course tools enabled for this user and course
        course_tools = CourseToolsPluginManager.get_enabled_course_tools(request, course_key)

        course_homepage_invert_title =\
            configuration_helpers.get_value(
                'COURSE_HOMEPAGE_INVERT_TITLE',
                False
            )

        course_homepage_show_subtitle =\
            configuration_helpers.get_value(
                'COURSE_HOMEPAGE_SHOW_SUBTITLE',
                True
            )

        course_homepage_show_org =\
            configuration_helpers.get_value('COURSE_HOMEPAGE_SHOW_ORG', True)

        course_title = course.display_number_with_default
        course_subtitle = course.display_name_with_default
        if course_homepage_invert_title:
            course_title = course.display_name_with_default
            course_subtitle = course.display_number_with_default

        context = {
            'request': request,
            'masquerade_user': user,
            'course_id': text_type(course_key),
            'url_to_enroll': CourseTabView.url_to_enroll(course_key),
            'cache': None,
            'course': course,
            'course_title': course_title,
            'course_subtitle': course_subtitle,
            'show_subtitle': course_homepage_show_subtitle,
            'show_org': course_homepage_show_org,
            'staff_access': staff_access,
            'masquerade': masquerade,
            'supports_preview_menu': True,
            'studio_url': get_studio_url(course, 'course_info'),
            'show_enroll_banner': show_enroll_banner,
            'user_is_enrolled': user_is_enrolled,
            'dates_fragment': dates_fragment,
            'course_tools': course_tools,
        }
        context.update(
            get_experiment_user_metadata_context(
                course,
                user,
            )
        )

        # Get the URL of the user's last position in order to display the 'where you were last' message
        context['resume_course_url'] = None
        # TODO: LEARNER-611: Remove enable_course_home_improvements
        if SelfPacedConfiguration.current().enable_course_home_improvements:
            context['resume_course_url'] = get_last_accessed_courseware(request, course, user=user)

        if not check_course_open_for_learner(user, course):
            # Disable student view button if user is staff and
            # course is not yet visible to students.
            context['disable_student_access'] = True
            context['supports_preview_menu'] = False

        return render_to_response('courseware/info.html', context)


class StaticCourseTabView(EdxFragmentView):
    """
    View that displays a static course tab with a given name.
    """
    @method_decorator(ensure_csrf_cookie)
    @method_decorator(ensure_valid_course_key)
    def get(self, request, course_id, tab_slug, **kwargs):
        """
        Displays a static course tab page with a given name
        """
        course_key = CourseKey.from_string(course_id)
        course = get_course_with_access(request.user, 'load', course_key)
        tab = CourseTabList.get_tab_by_slug(course.tabs, tab_slug)
        if tab is None:
            raise Http404

        # Show warnings if the user has limited access
        CourseTabView.register_user_access_warning_messages(request, course_key)

        return super(StaticCourseTabView, self).get(request, course=course, tab=tab, **kwargs)

    def render_to_fragment(self, request, course=None, tab=None, **kwargs):
        """
        Renders the static tab to a fragment.
        """
        return get_static_tab_fragment(request, course, tab)

    def render_standalone_response(self, request, fragment, course=None, tab=None, **kwargs):
        """
        Renders this static tab's fragment to HTML for a standalone page.
        """

        show_courseware_link = False
        resume_course_url = None
        progress = None
        if course:
            show_courseware_link = bool(
                has_access(request.user, 'load', course)
                or settings.FEATURES.get('ENABLE_LMS_MIGRATION')
            )

            if show_courseware_link:
                resume_course_url = get_last_accessed_courseware(request, course)

                if not isinstance(request.user, AnonymousUser):
                    progress = CourseGradeFactory().get_course_completion_percentage(
                                        request.user, course.id)
                    progress = int(progress * 100)

        return render_to_response('courseware/static_tab.html', {
            'course': course,
            'active_page': 'static_tab_{0}'.format(tab['url_slug']),
            'tab': tab,
            'fragment': fragment,
            'uses_pattern_library': False,
            'disable_courseware_js': True,
            'registered': registered_for_course(course, request.user),
            'show_courseware_link': show_courseware_link,
            'resume_course_url': resume_course_url,
            'progress': progress
        })


class CourseTabView(EdxFragmentView):
    """
    View that displays a course tab page.
    """
    @method_decorator(ensure_csrf_cookie)
    @method_decorator(ensure_valid_course_key)
    @method_decorator(data_sharing_consent_required)
    def get(self, request, course_id, tab_type, **kwargs):
        """
        Displays a course tab page that contains a web fragment.
        """
        course_key = CourseKey.from_string(course_id)
        with modulestore().bulk_operations(course_key):
            course = get_course_with_access(request.user, 'load', course_key)
            try:
                # Render the page
                tab = CourseTabList.get_tab_by_type(course.tabs, tab_type)
                page_context = self.create_page_context(request, course=course, tab=tab, **kwargs)

                # Show warnings if the user has limited access
                # Must come after masquerading on creation of page context
                self.register_user_access_warning_messages(request, course_key)

                set_custom_metrics_for_course_key(course_key)
                return super(CourseTabView, self).get(request, course=course, page_context=page_context, **kwargs)
            except Exception as exception:  # pylint: disable=broad-except
                return CourseTabView.handle_exceptions(request, course, exception)

    @staticmethod
    def url_to_enroll(course_key):
        """
        Returns the URL to use to enroll in the specified course.
        """
        url_to_enroll = reverse('about_course', args=[text_type(course_key)])
        if settings.FEATURES.get('ENABLE_MKTG_SITE'):
            url_to_enroll = marketing_link('COURSES')
        return url_to_enroll

    @staticmethod
    def register_user_access_warning_messages(request, course_key):
        """
        Register messages to be shown to the user if they have limited access.
        """
        if request.user.is_anonymous:
            PageLevelMessages.register_warning_message(
                request,
                Text(_("To see course content, {sign_in_link} or {register_link}.")).format(
                    sign_in_link=HTML('<a href="/login?next={current_url}">{sign_in_label}</a>').format(
                        sign_in_label=_("sign in"),
                        current_url=urlquote_plus(request.path),
                    ),
                    register_link=HTML('<a href="/register?next={current_url}">{register_label}</a>').format(
                        register_label=_("register"),
                        current_url=urlquote_plus(request.path),
                    ),
                )
            )
        else:
            if not CourseEnrollment.is_enrolled(request.user, course_key):
                # Only show enroll button if course is open for enrollment.
                if course_open_for_self_enrollment(course_key):
                    enroll_message = _('You must be enrolled in the course to see course content. \
                            {enroll_link_start}Enroll now{enroll_link_end}.')
                    PageLevelMessages.register_warning_message(
                        request,
                        Text(enroll_message).format(
                            enroll_link_start=HTML('<button class="enroll-btn btn-link">'),
                            enroll_link_end=HTML('</button>')
                        )
                    )
                else:
                    PageLevelMessages.register_warning_message(
                        request,
                        Text(_('You must be enrolled in the course to see course content.'))
                    )

    @staticmethod
    def handle_exceptions(request, course, exception):
        """
        Handle exceptions raised when rendering a view.
        """
        if isinstance(exception, Redirect) or isinstance(exception, Http404):
            raise
        if isinstance(exception, UnicodeEncodeError):
            raise Http404("URL contains Unicode characters")
        if settings.DEBUG:
            raise
        user = request.user
        log.exception(
            u"Error in %s: user=%s, effective_user=%s, course=%s",
            request.path,
            getattr(user, 'real_user', user),
            user,
            text_type(course.id),
        )
        try:
            return render_to_response(
                'courseware/courseware-error.html',
                {
                    'staff_access': has_access(user, 'staff', course),
                    'course': course,
                },
                status=500,
            )
        except:
            # Let the exception propagate, relying on global config to
            # at least return a nice error message
            log.exception("Error while rendering courseware-error page")
            raise

    def uses_bootstrap(self, request, course, tab):
        """
        Returns true if this view uses Bootstrap.
        """
        return tab.uses_bootstrap

    def create_page_context(self, request, course=None, tab=None, **kwargs):
        """
        Creates the context for the fragment's template.
        """
        staff_access = has_access(request.user, 'staff', course)
        supports_preview_menu = tab.get('supports_preview_menu', False)
        uses_bootstrap = False
        if supports_preview_menu:
            masquerade, masquerade_user = setup_masquerade(request, course.id, staff_access, reset_masquerade_data=True)
            request.user = masquerade_user
        else:
            masquerade = None

        if course and not check_course_open_for_learner(request.user, course):
            # Disable student view button if user is staff and
            # course is not yet visible to students.
            supports_preview_menu = False

        show_courseware_link = False
        resume_course_url = None
        progress = None
        if course:
            show_courseware_link = bool(
                has_access(request.user, 'load', course)
                or settings.FEATURES.get('ENABLE_LMS_MIGRATION')
            )

            if show_courseware_link:
                resume_course_url = get_last_accessed_courseware(request, course)

                if not isinstance(request.user, AnonymousUser):
                    progress = CourseGradeFactory().update_course_completion_percentage(
                        course.id, request.user, force_update_grade=True)
                    progress = int(progress * 100)

        context = {
            'course': course,
            'tab': tab,
            'active_page': tab.get('type', None),
            'staff_access': staff_access,
            'masquerade': masquerade,
            'supports_preview_menu': supports_preview_menu,
            'uses_bootstrap': uses_bootstrap,
            'uses_pattern_library': not uses_bootstrap,
            'disable_courseware_js': True,
            'registered': registered_for_course(course, request.user),
            'show_courseware_link': show_courseware_link,
            'resume_course_url': resume_course_url,
            'progress': progress
        }
        context.update(
            get_experiment_user_metadata_context(
                course,
                request.user,
            )
        )
        return context

    def render_to_fragment(self, request, course=None, page_context=None, **kwargs):
        """
        Renders the course tab to a fragment.
        """
        tab = page_context['tab']
        return tab.render_to_fragment(request, course, **kwargs)

    def render_standalone_response(self, request, fragment, course=None, tab=None, page_context=None, **kwargs):
        """
        Renders this course tab's fragment to HTML for a standalone page.
        """
        if not page_context:
            page_context = self.create_page_context(request, course=course, tab=tab, **kwargs)
        tab = page_context['tab']
        page_context['fragment'] = fragment
        if self.uses_bootstrap(request, course, tab=tab):
            return render_to_response('courseware/tab-view.html', page_context)
        else:
            return render_to_response('courseware/tab-view-v2.html', page_context)


@ensure_csrf_cookie
@ensure_valid_course_key
def syllabus(request, course_id):
    """
    Display the course's syllabus.html, or 404 if there is no such course.

    Assumes the course_id is in a valid format.
    """

    course_key = CourseKey.from_string(course_id)

    course = get_course_with_access(request.user, 'load', course_key)
    staff_access = bool(has_access(request.user, 'staff', course))

    return render_to_response('courseware/syllabus.html', {
        'course': course,
        'staff_access': staff_access,
    })


def registered_for_course(course, user):
    """
    Return True if user is registered for course, else False
    """
    if user is None:
        return False
    if user.is_authenticated:
        return CourseEnrollment.is_enrolled(user, course.id)
    else:
        return False


class EnrollStaffView(View):
    """
    Displays view for registering in the course to a global staff user.

    User can either choose to 'Enroll' or 'Don't Enroll' in the course.
      Enroll: Enrolls user in course and redirects to the courseware.
      Don't Enroll: Redirects user to course about page.

    Arguments:
     - request    : HTTP request
     - course_id  : course id

    Returns:
     - RedirectResponse
    """
    template_name = 'enroll_staff.html'

    @method_decorator(require_global_staff)
    @method_decorator(ensure_valid_course_key)
    def get(self, request, course_id):
        """
        Display enroll staff view to global staff user with `Enroll` and `Don't Enroll` options.
        """
        user = request.user
        course_key = CourseKey.from_string(course_id)
        with modulestore().bulk_operations(course_key):
            course = get_course_with_access(user, 'load', course_key)
            if not registered_for_course(course, user):
                context = {
                    'course': course,
                    'csrftoken': csrf(request)["csrf_token"]
                }
                return render_to_response(self.template_name, context)

    @method_decorator(require_global_staff)
    @method_decorator(ensure_valid_course_key)
    def post(self, request, course_id):
        """
        Either enrolls the user in course or redirects user to course about page
        depending upon the option (Enroll, Don't Enroll) chosen by the user.
        """
        _next = urllib.quote_plus(request.GET.get('next', 'info'), safe='/:?=')
        course_key = CourseKey.from_string(course_id)
        enroll = 'enroll' in request.POST
        if enroll:
            add_enrollment(request.user.username, course_id)
            log.info(
                u"User %s enrolled in %s via `enroll_staff` view",
                request.user.username,
                course_id
            )
            return redirect(_next)

        # In any other case redirect to the course about page.
        return redirect(reverse('about_course', args=[text_type(course_key)]))


@ensure_csrf_cookie
@ensure_valid_course_key
@cache_if_anonymous()
def course_about(request, course_id):
    """
    Display the course's about page.
    """
    course_key = CourseKey.from_string(course_id)

    # If a user is not able to enroll in a course then redirect
    # them away from the about page to the dashboard.
    # if not can_self_enroll_in_course(course_key):
    #     return redirect(reverse('dashboard'))

    with modulestore().bulk_operations(course_key):
        permission = get_permission_for_course_about()

        if permission != "see_about_page" and not request.user.is_authenticated:
            redirect_to = '/login?next={}'.format(reverse('about_course', args=[unicode(course_id)]).replace('+', '%2B'))
            return redirect(redirect_to)

        course = get_course_with_access(request.user, permission, course_key)
        course_details = CourseDetails.populate(course)
        modes = CourseMode.modes_for_course_dict(course_key)

        if configuration_helpers.get_value('ENABLE_MKTG_SITE', settings.FEATURES.get('ENABLE_MKTG_SITE', False)):
            return redirect(reverse(course_home_url_name(course.id), args=[text_type(course.id)]))

        registered = registered_for_course(course, request.user)

        staff_access = bool(has_access(request.user, 'staff', course))
        studio_url = get_studio_url(course, 'settings/details')

        if has_access(request.user, 'load', course):
            course_target = get_last_accessed_courseware(request, course)
        else:
            course_target = reverse('about_course', args=[text_type(course.id)])

        show_courseware_link = bool(
            (
                has_access(request.user, 'load', course)
            ) or settings.FEATURES.get('ENABLE_LMS_MIGRATION')
        )

        # Note: this is a flow for payment for course registration, not the Verified Certificate flow.
        in_cart = False
        reg_then_add_to_cart_link = ""

        _is_shopping_cart_enabled = is_shopping_cart_enabled()
        if _is_shopping_cart_enabled:
            if request.user.is_authenticated:
                cart = shoppingcart.models.Order.get_cart_for_user(request.user)
                in_cart = shoppingcart.models.PaidCourseRegistration.contained_in_order(cart, course_key) or \
                    shoppingcart.models.CourseRegCodeItem.contained_in_order(cart, course_key)

            reg_then_add_to_cart_link = "{reg_url}?course_id={course_id}&enrollment_action=add_to_cart".format(
                reg_url=reverse('register_user'), course_id=urllib.quote(str(course_id))
            )

        # If the ecommerce checkout flow is enabled and the mode of the course is
        # professional or no id professional, we construct links for the enrollment
        # button to add the course to the ecommerce basket.
        ecomm_service = EcommerceService()
        ecommerce_checkout = ecomm_service.is_enabled(request.user)
        ecommerce_checkout_link = ''
        ecommerce_bulk_checkout_link = ''
        professional_mode = None
        is_professional_mode = CourseMode.PROFESSIONAL in modes or CourseMode.NO_ID_PROFESSIONAL_MODE in modes
        if ecommerce_checkout and is_professional_mode:
            professional_mode = modes.get(CourseMode.PROFESSIONAL, '') or \
                modes.get(CourseMode.NO_ID_PROFESSIONAL_MODE, '')
            if professional_mode.sku:
                ecommerce_checkout_link = ecomm_service.get_checkout_page_url(professional_mode.sku)
            if professional_mode.bulk_sku:
                ecommerce_bulk_checkout_link = ecomm_service.get_checkout_page_url(professional_mode.bulk_sku)

        registration_price, course_price = get_course_prices(course)

        # Determine which checkout workflow to use -- LMS shoppingcart or Otto basket
        can_add_course_to_cart = _is_shopping_cart_enabled and registration_price and not ecommerce_checkout_link

        # Used to provide context to message to student if enrollment not allowed
        can_enroll = bool(has_access(request.user, 'enroll', course))
        invitation_only = course.invitation_only
        is_course_full = CourseEnrollment.objects.is_course_full(course)

        # Register button should be disabled if one of the following is true:
        # - Student is already registered for course
        # - Course is already full
        # - Student cannot enroll in course
        active_reg_button = not (registered or is_course_full or not can_enroll)

        is_shib_course = uses_shib(course)

        # get prerequisite courses display names
        pre_requisite_courses = get_prerequisite_courses_display(course)

        # Overview
        overview = CourseOverview.get_from_id(course.id)

        sidebar_html_enabled = course_experience_waffle().is_enabled(ENABLE_COURSE_ABOUT_SIDEBAR_HTML)

        # This local import is due to the circularity of lms and openedx references.
        # This may be resolved by using stevedore to allow web fragments to be used
        # as plugins, and to avoid the direct import.
        from openedx.features.course_experience.views.course_reviews import CourseReviewsModuleFragmentView

        # Embed the course reviews tool
        reviews_fragment_view = CourseReviewsModuleFragmentView().render_to_fragment(request, course=course)

        outline_fragment = None
        # hide course outline if course has not started yet
        if request.user.is_authenticated and course.has_started():
            outline_fragment = CourseOutlineFragmentView().render_to_fragment(
                request,
                course_id=course_id,
                check_access=False
            )

        program_uuid = request.GET.get('program_uuid')

        context = {
            'request': request,
            'program_uuid': program_uuid,
            'course': course,
            'course_details': course_details,
            'staff_access': staff_access,
            'studio_url': studio_url,
            'registered': registered,
            'course_target': course_target,
            'is_cosmetic_price_enabled': settings.FEATURES.get('ENABLE_COSMETIC_DISPLAY_PRICE'),
            'course_price': course_price,
            'in_cart': in_cart,
            'ecommerce_checkout': ecommerce_checkout,
            'ecommerce_checkout_link': ecommerce_checkout_link,
            'ecommerce_bulk_checkout_link': ecommerce_bulk_checkout_link,
            'professional_mode': professional_mode,
            'reg_then_add_to_cart_link': reg_then_add_to_cart_link,
            'show_courseware_link': show_courseware_link,
            'is_course_full': is_course_full,
            'can_enroll': can_enroll,
            'invitation_only': invitation_only,
            'active_reg_button': active_reg_button,
            'is_shib_course': is_shib_course,
            # We do not want to display the internal courseware header, which is used when the course is found in the
            # context. This value is therefor explicitly set to render the appropriate header.
            'disable_courseware_header': True,
            'can_add_course_to_cart': can_add_course_to_cart,
            'cart_link': reverse('shoppingcart.views.show_cart'),
            'pre_requisite_courses': pre_requisite_courses,
            'course_image_urls': overview.image_urls,
            'reviews_fragment_view': reviews_fragment_view,
            'sidebar_html_enabled': sidebar_html_enabled,
            'user': request.user,
            'show_dashboard_tabs': True,
            'outline_fragment': outline_fragment,
            'progress': None,
            'nb_talks': 0,
            'nb_trophies_earned': 0,
            'nb_trophies_possible': 0,
            'progress_url': reverse('progress', kwargs={'course_id': course.id}),
            'discussion_url': '/courses/{course_id}/discussion/forum/'.format(course_id=unicode(course.id))
        }

        if request.user.is_authenticated:
            if program_uuid:
                _filter = {
                    'courses.course_runs.key': course_id,
                    'visibility': {'$in': (PartialProgram.DEF_VISIBILITY_FULL_PUBLIC, None)}
                }
                def _gen_program_info(program):
                    program = program.to_dict()
                    return {'title': program['title'], 'uuid': program['uuid']}

                context['programs_tags'] = [
                    _gen_program_info(program)
                    for program in PartialProgram.query(
                        _filter, limit=5,
                        loading_policy=PartialProgram.POLICY_LOAD_LP_ONLY
                    )
                ]
            else:
                context['programs_tags'] = ()

            progress_summary = CourseGradeFactory().get_progress(request.user, course)
            context['nb_trophies_earned'] = progress_summary['nb_trophies_earned']
            context['nb_trophies_possible'] = progress_summary['nb_trophies_possible']
            try:
                cc_user = cc.User.from_django_user(request.user)
                cc_user.course_id = course.id
                cc_user.retrieve(complete=False)
                context['nb_talks'] = cc_user['threads_count'] + cc_user['comments_count']
            except:
                pass

        return render_to_response('courseware/course_about.html', context)


@ensure_csrf_cookie
@ensure_valid_course_key
@cache_if_anonymous()
def course_print(request, course_id):
    """
    Display the course's print page.
    """
    course_key = CourseKey.from_string(course_id)

    # If a user is not able to enroll in a course then redirect
    # them away from the print page to the dashboard.
    # if not can_self_enroll_in_course(course_key):
    #     return redirect(reverse('dashboard'))

    with modulestore().bulk_operations(course_key):
        permission = get_permission_for_course_about()

        course = get_course_with_access(request.user, permission, course_key)
        course_details = CourseDetails.populate(course)
        modes = CourseMode.modes_for_course_dict(course_key)

        if configuration_helpers.get_value('ENABLE_MKTG_SITE', settings.FEATURES.get('ENABLE_MKTG_SITE', False)):
            return redirect(reverse(course_home_url_name(course.id), args=[text_type(course.id)]))

        registered = registered_for_course(course, request.user)

        staff_access = bool(has_access(request.user, 'staff', course))
        studio_url = get_studio_url(course, 'settings/details')

        if has_access(request.user, 'load', course):
            course_target = get_last_accessed_courseware(request, course)
        else:
            course_target = reverse('about_course', args=[text_type(course.id)])

        show_courseware_link = bool(
            (
                has_access(request.user, 'load', course)
            ) or settings.FEATURES.get('ENABLE_LMS_MIGRATION')
        )

        # Note: this is a flow for payment for course registration, not the Verified Certificate flow.
        in_cart = False
        reg_then_add_to_cart_link = ""

        _is_shopping_cart_enabled = is_shopping_cart_enabled()
        if _is_shopping_cart_enabled:
            if request.user.is_authenticated:
                cart = shoppingcart.models.Order.get_cart_for_user(request.user)
                in_cart = shoppingcart.models.PaidCourseRegistration.contained_in_order(cart, course_key) or \
                    shoppingcart.models.CourseRegCodeItem.contained_in_order(cart, course_key)

            reg_then_add_to_cart_link = "{reg_url}?course_id={course_id}&enrollment_action=add_to_cart".format(
                reg_url=reverse('register_user'), course_id=urllib.quote(str(course_id))
            )

        # If the ecommerce checkout flow is enabled and the mode of the course is
        # professional or no id professional, we construct links for the enrollment
        # button to add the course to the ecommerce basket.
        ecomm_service = EcommerceService()
        ecommerce_checkout = ecomm_service.is_enabled(request.user)
        ecommerce_checkout_link = ''
        ecommerce_bulk_checkout_link = ''
        professional_mode = None
        is_professional_mode = CourseMode.PROFESSIONAL in modes or CourseMode.NO_ID_PROFESSIONAL_MODE in modes
        if ecommerce_checkout and is_professional_mode:
            professional_mode = modes.get(CourseMode.PROFESSIONAL, '') or \
                modes.get(CourseMode.NO_ID_PROFESSIONAL_MODE, '')
            if professional_mode.sku:
                ecommerce_checkout_link = ecomm_service.get_checkout_page_url(professional_mode.sku)
            if professional_mode.bulk_sku:
                ecommerce_bulk_checkout_link = ecomm_service.get_checkout_page_url(professional_mode.bulk_sku)

        registration_price, course_price = get_course_prices(course)

        # Determine which checkout workflow to use -- LMS shoppingcart or Otto basket
        can_add_course_to_cart = _is_shopping_cart_enabled and registration_price and not ecommerce_checkout_link

        # Used to provide context to message to student if enrollment not allowed
        can_enroll = bool(has_access(request.user, 'enroll', course))
        invitation_only = course.invitation_only
        is_course_full = CourseEnrollment.objects.is_course_full(course)

        # Register button should be disabled if one of the following is true:
        # - Student is already registered for course
        # - Course is already full
        # - Student cannot enroll in course
        active_reg_button = not (registered or is_course_full or not can_enroll)

        is_shib_course = uses_shib(course)

        # get prerequisite courses display names
        pre_requisite_courses = get_prerequisite_courses_display(course)

        # Overview
        overview = CourseOverview.get_from_id(course.id)

        sidebar_html_enabled = course_experience_waffle().is_enabled(ENABLE_COURSE_ABOUT_SIDEBAR_HTML)

        # This local import is due to the circularity of lms and openedx references.
        # This may be resolved by using stevedore to allow web fragments to be used
        # as plugins, and to avoid the direct import.
        from openedx.features.course_experience.views.course_reviews import CourseReviewsModuleFragmentView

        # Embed the course reviews tool
        reviews_fragment_view = CourseReviewsModuleFragmentView().render_to_fragment(request, course=course)

        outline_fragment = None
        if request.user.is_authenticated:
            outline_fragment = CourseOutlineFragmentView().render_to_fragment(
                                    request, course_id=course_id, check_access=False)

        context = {
            'course': course,
            'course_details': course_details,
            'staff_access': staff_access,
            'studio_url': studio_url,
            'registered': registered,
            'course_target': course_target,
            'is_cosmetic_price_enabled': settings.FEATURES.get('ENABLE_COSMETIC_DISPLAY_PRICE'),
            'course_price': course_price,
            'in_cart': in_cart,
            'ecommerce_checkout': ecommerce_checkout,
            'ecommerce_checkout_link': ecommerce_checkout_link,
            'ecommerce_bulk_checkout_link': ecommerce_bulk_checkout_link,
            'professional_mode': professional_mode,
            'reg_then_add_to_cart_link': reg_then_add_to_cart_link,
            'show_courseware_link': show_courseware_link,
            'is_course_full': is_course_full,
            'can_enroll': can_enroll,
            'invitation_only': invitation_only,
            'active_reg_button': active_reg_button,
            'is_shib_course': is_shib_course,
            # We do not want to display the internal courseware header, which is used when the course is found in the
            # context. This value is therefor explicitly set to render the appropriate header.
            'disable_courseware_header': True,
            'can_add_course_to_cart': can_add_course_to_cart,
            'cart_link': reverse('shoppingcart.views.show_cart'),
            'pre_requisite_courses': pre_requisite_courses,
            'course_image_urls': overview.image_urls,
            'reviews_fragment_view': reviews_fragment_view,
            'sidebar_html_enabled': sidebar_html_enabled,
            'user': request.user,
            'show_dashboard_tabs': True,
            'outline_fragment': outline_fragment,
            'progress': None
        }
        return render_to_response('courseware/course_print.html', context)


@ensure_csrf_cookie
@cache_if_anonymous()
def program_marketing(request, program_uuid):
    """Display the program marketing page & list all courses in program"""
    if not request.user.is_authenticated:
        redirect_to = '/login?next={}'.format(
            reverse('program_marketing_view', args=[program_uuid])
        )
        return redirect(redirect_to)

    program_data = PartialProgram.query_one(
        {'_id': program_uuid}
    )
    user_has_edit_permission = bool(
        ProgramRolesManager.get_permissions(
            request.user, program_uuid
        ) & STUDIO_EDIT_CONTENT
    )
    is_preview_mode = request.GET.get('viewtype', '') == 'preview'

    if is_preview_mode:
        draft_program_data = DraftPartialProgram.query_one(
            {'_id': program_uuid}
        )

        if (not program_data and not draft_program_data) or not user_has_edit_permission:
            raise Http404

        if program_data:
            program = program_data.to_dict()
            program['courses'] = draft_program_data['courses']
        else:
            program_data = draft_program_data
            program = program_data.to_dict()
    else:
        if not program_data:
            raise Http404

        program = program_data.to_dict()

    theme = get_current_theme()
    context = {
        'program_uuid': program_uuid,
        'username': request.user.username,
        'theme_dir_name': 'hawthorn' if not theme else theme.theme_dir_name
    }

    try:
        context['enrollment_status'] = get_program_enrollment(program_uuid, request.user).status
    except ObjectDoesNotExist:
        context['enrollment_status'] = 'none'

    program_progress = ProgramsCompletionStatistics(
        user=request.user,
        count_only=False,
        program_uuid=program_uuid
    ).progress

    for course in program['courses']:
        course['image']['src'] = course['image']['src'].replace('http://127.0.0.1:8000', '')
        sorted_course_runs = sorted(course['course_runs'], key=lambda run: run['start'])
        open_course_runs = [run for run in sorted_course_runs if run.get('is_enrollment_open', True)]
        course_run = open_course_runs[0] if open_course_runs else sorted_course_runs[-1]
        course['start'] = course_run['start']
        course['non_started'] = not course_metadata_utils.has_course_started(
            datetime.strptime(course['start'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)
        )
        course['course_about_url'] = reverse('about_course', args=[course_run['key']]) + '?program_uuid=' + program_uuid
        course_id = CourseKey.from_string(course_run['key'])
        course['course_id'] = course_id
        course_duration = course_run['duration']
        course['course_duration'] = course_duration
        course['course_detail_description'] = course['description']
        try:
            # Program Course Enrollment status: `active` / `inactive`: ProgramCourseEnrollmentStatuses.INACTIVE/ACTIVE
            course_enrollment = get_program_course_enrollment(program_uuid=program_uuid, course_key=course_id, user=request.user)
            course['course_enrollment_status'] = course_enrollment.status
        except ObjectDoesNotExist:
            course['course_enrollment_status'] = None
        duration_availability = False
        if course_duration:
            duration_context = course_duration.strip().split(' ')
            duration_availability = len(duration_context) == 2
        if duration_availability:
            course['duration'] = float(duration_context[0]) if '.' in duration_context[0] else int(duration_context[0])
            course['duration_unit'] = duration_context[1]
        course['duration_availability'] = duration_availability
        course_descriptor = modulestore().get_course(course_id)
        if course_descriptor:
            course['badges'] = CourseGradeFactory().get_nb_trophies_possible(course_descriptor)
        else:
            course['badges'] = 0
        if course_descriptor:
            user_has_access = has_access(request.user, 'load', course_descriptor)
            course['user_has_access'] = True if user_has_access else False
        else:
            course['user_has_access'] = False
        course['program_enrollment_status'] = context['enrollment_status']  # 'enrolled' or 'none'
        course['course_completed'] = any(
            [
                course_run['key'] in {
                    run['key']
                    for run in progress['course_runs']
                }
                for progress in program_progress[0][r'completed']
            ]
        ) \
            if program_progress else False

    if program['start'] == 'is_null':
        program['non_started'] = False
    elif type(program['start']) in (unicode, str):
        try:
            program_start = datetime.strptime(program['start'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)
            program['non_started'] = not course_metadata_utils.has_course_started(program_start)
        except Exception as e:
            program['non_started'] = False
    else:
        program['non_started'] = not course_metadata_utils.has_course_started(program['start'])
    context['program'] = program
    context['uses_bootstrap'] = True

    is_super_or_platform_admin = True \
        if request.user.is_superuser or request.user.is_staff \
        else False

    if is_super_or_platform_admin:
        context['has_edit_permission'] = True
    else:
        context['has_edit_permission'] = user_has_edit_permission

    # This LP is "Private" + the login user has "No permission" for editing
    # Raise Exception here.
    if program['visibility'] == PartialProgram.DEF_VISIBILITY_PRIVATE and \
            not context['has_edit_permission'] and not ProgramEnrollment.is_enrolled(request.user, program_uuid):
        return redirect('dashboard')

    if program_progress and not is_preview_mode:
        program_progress = program_progress[0]
        context['program_courses_completed'] = len(program_progress[r'completed'])
        context['program_courses_total'] = len(program_progress[r'in_progress']) + len(
            program_progress[r'not_started']) + len(program_progress[r'completed'])
    else:
        context['program_courses_completed'] = 0
        context['program_courses_total'] = 0 \
            if not is_preview_mode \
            else len(program['courses'])

    return render_to_response('courseware/program_marketing2.html', context)


@ensure_csrf_cookie
@cache_if_anonymous()
def program_marketing2(request, program_uuid):
    context = {}
    return render_to_response('courseware/program_marketing2.html', context)


@transaction.non_atomic_requests
@login_required
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@ensure_valid_course_key
@data_sharing_consent_required
def progress(request, course_id, student_id=None):
    """ Display the progress page. """
    course_key = CourseKey.from_string(course_id)

    with modulestore().bulk_operations(course_key):
        return _progress(request, course_key, student_id)


def _progress(request, course_key, student_id):
    """
    Unwrapped version of "progress".

    User progress. We show the grade bar and every problem score.

    Course staff are allowed to see the progress of students in their class.
    """

    if student_id is not None:
        try:
            student_id = int(student_id)
        # Check for ValueError if 'student_id' cannot be converted to integer.
        except ValueError:
            raise Http404

    course = get_course_with_access(request.user, 'load', course_key)

    staff_access = bool(has_access(request.user, 'staff', course))

    masquerade = None
    if student_id is None or student_id == request.user.id:
        # This will be a no-op for non-staff users, returning request.user
        masquerade, student = setup_masquerade(request, course_key, staff_access, reset_masquerade_data=True)
    else:
        try:
            coach_access = has_ccx_coach_role(request.user, course_key)
        except CCXLocatorValidationException:
            coach_access = False

        has_access_on_students_profiles = staff_access or coach_access
        # Requesting access to a different student's profile
        if not has_access_on_students_profiles:
            raise Http404
        try:
            student = User.objects.get(id=student_id)
        except User.DoesNotExist:
            raise Http404

    # NOTE: To make sure impersonation by instructor works, use
    # student instead of request.user in the rest of the function.

    # The pre-fetching of groups is done to make auth checks not require an
    # additional DB lookup (this kills the Progress page in particular).
    student = User.objects.prefetch_related("groups").get(id=student.id)
    if request.user.id != student.id:
        # refetch the course as the assumed student
        course = get_course_with_access(student, 'load', course_key, check_if_enrolled=True)

    # NOTE: To make sure impersonation by instructor works, use
    # student instead of request.user in the rest of the function.

    course_grade = CourseGradeFactory().read(student, course)
    progress_summary = CourseGradeFactory().get_progress(student, course, grade_summary=course_grade)
    progress_badges_section = _get_badges_section(progress_summary)

    studio_url = get_studio_url(course, 'settings/grading')
    # checking certificate generation configuration
    enrollment_mode, _ = CourseEnrollment.enrollment_mode_for_user(student, course_key)

    show_courseware_link = bool(
        (
            has_access(request.user, 'load', course)
        ) or settings.FEATURES.get('ENABLE_LMS_MIGRATION')
    )

    if has_access(request.user, 'load', course):
        course_target = get_last_accessed_courseware(request, course)
    else:
        course_target = reverse('about_course', args=[text_type(course.id)])

    context = {
        'course': course,
        'studio_url': studio_url,
        'grade_summary': course_grade.summary,
        'staff_access': staff_access,
        'masquerade': masquerade,
        'supports_preview_menu': True,
        'student': student,
        'credit_course_requirements': _credit_course_requirements(course_key, student),
        'certificate_data': _get_cert_data(student, course, enrollment_mode, course_grade),
        'show_dashboard_tabs': True,
        'supports_preview_menu': False,
        'show_courseware_link': show_courseware_link,
        'user': request.user,
        'registered': registered_for_course(course, request.user),
        'course_target': course_target,
        #'progress_summary': progress_summary,
        'progress_badges_section': progress_badges_section,
        'progress': int(progress_summary['progress']*100)
    }
    context.update(
        get_experiment_user_metadata_context(
            course,
            student,
        )
    )

    with outer_atomic():
        response = render_to_response('courseware/progress_badges.html', context)

    return response


def _get_badges_section(progress_summary):
    """get badges and divide into different section

    Sections for obtained, not obtained and not started, divided into to avoid front page to calculate for multi loop, optimal page performance.

    Args:
        progress_summary: dict object contains each chapter's trophies.

    Returns:
        A dict mapping different sections to individual badges
    """
    badges_section = defaultdict(list)
    for chapter in progress_summary['trophies_by_chapter']:
        for trophy in chapter['trophies']:
            trophy['url'] = chapter['url']
            if trophy['passed']:
                badges_section['obtained'].append(trophy)
            elif trophy['attempted']:
                badges_section['not-obtained'].append(trophy)
            else:
                badges_section['not-started'].append(trophy)
    return badges_section


def _downloadable_certificate_message(course, cert_downloadable_status):
    if certs_api.has_html_certificates_enabled(course):
        if certs_api.get_active_web_certificate(course) is not None:
            return _downloadable_cert_data(
                download_url=None,
                cert_web_view_url=certs_api.get_certificate_url(
                    course_id=course.id, uuid=cert_downloadable_status['uuid']
                )
            )
        elif not cert_downloadable_status['download_url']:
            return _generating_cert_data()

    return _downloadable_cert_data(download_url=cert_downloadable_status['download_url'])


def _missing_required_verification(student, enrollment_mode):
    return (
        enrollment_mode in CourseMode.VERIFIED_MODES and not IDVerificationService.user_is_verified(student)
    )


def _certificate_message(student, course, course_grade, enrollment_mode):
    cert_downloadable_status = certs_api.certificate_downloadable_status(student, course.id)
    enrollment = CourseEnrollment.get_enrollment(student, course.id)
    self_cert_enabled = CertificateGenerationCourseSetting.is_self_generation_enabled_for_course(course.id)

    # self paced course or instructor paced course with student_generate_certificate enabled
    if self_cert_enabled or course.self_paced:
        if enrollment.completed and course_grade.passed:
            if cert_downloadable_status['is_downloadable']:
                return _downloadable_certificate_message(course, cert_downloadable_status)
            elif cert_downloadable_status['is_generating']:
                return _generating_cert_data()
            else:
                return _requesting_cert_data()
        else:
            return None

    if certs_api.is_certificate_invalid(student, course.id):
        message = _invalid_cert_data()

    elif cert_downloadable_status['is_generating']:
        message = _generating_cert_data()

    elif cert_downloadable_status['is_unverified'] or _missing_required_verification(student, enrollment_mode):
        message = _unverified_cert_data()

    elif cert_downloadable_status['is_downloadable']:
        message = _downloadable_certificate_message(course, cert_downloadable_status)

    elif cert_downloadable_status['not_passing']:
        message = _not_passing_cert_data()

    else:
        message = _instructor_paced_cert_data()

    if course.certificates_display_behavior == 'end' and not course.has_ended():
        return None

    if course.certificates_display_behavior == 'end' and course.has_ended() \
            or course.certificates_display_behavior == 'early_with_info':
        return message

    if course.certificates_display_behavior == 'early_no_info':
        if cert_downloadable_status['is_downloadable']:
            return message
        return None


def _get_cert_data(student, course, enrollment_mode, course_grade=None):
    """Returns students course certificate related data.

    Arguments:
        student (User): Student for whom certificate to retrieve.
        course (Course): Course object for which certificate data to retrieve.
        enrollment_mode (String): Course mode in which student is enrolled.
        course_grade (CourseGrade): Student's course grade record.

    Returns:
        returns dict if course certificate is available else None.
    """
    if not CourseMode.is_eligible_for_certificate(enrollment_mode):
        return AUDIT_PASSING_CERT_DATA

    certificates_enabled_for_course = certs_api.cert_generation_enabled(course.id)
    if course_grade is None:
        course_grade = CourseGradeFactory().read(student, course)

    if not auto_certs_api.can_show_certificate_message(course, student, course_grade, certificates_enabled_for_course):
        cert_downloadable_status = certs_api.certificate_downloadable_status(student, course.id)
        if cert_downloadable_status['is_downloadable']:
            return _downloadable_certificate_message(course, cert_downloadable_status)
        return None

    return _certificate_message(student, course, course_grade, enrollment_mode)


def _credit_course_requirements(course_key, student):
    """Return information about which credit requirements a user has satisfied.

    Arguments:
        course_key (CourseKey): Identifier for the course.
        student (User): Currently logged in user.

    Returns: dict if the credit eligibility enabled and it is a credit course
    and the user is enrolled in either verified or credit mode, and None otherwise.

    """
    # If credit eligibility is not enabled or this is not a credit course,
    # short-circuit and return `None`.  This indicates that credit requirements
    # should NOT be displayed on the progress page.
    if not (settings.FEATURES.get("ENABLE_CREDIT_ELIGIBILITY", False) and is_credit_course(course_key)):
        return None

    # This indicates that credit requirements should NOT be displayed on the progress page.
    enrollment = CourseEnrollment.get_enrollment(student, course_key)
    if enrollment and enrollment.mode not in REQUIREMENTS_DISPLAY_MODES:
        return None

    # Credit requirement statuses for which user does not remain eligible to get credit.
    non_eligible_statuses = ['failed', 'declined']

    # Retrieve the status of the user for each eligibility requirement in the course.
    # For each requirement, the user's status is either "satisfied", "failed", or None.
    # In this context, `None` means that we don't know the user's status, either because
    # the user hasn't done something (for example, submitting photos for verification)
    # or we're waiting on more information (for example, a response from the photo
    # verification service).
    requirement_statuses = get_credit_requirement_status(course_key, student.username)

    # If the user has been marked as "eligible", then they are *always* eligible
    # unless someone manually intervenes.  This could lead to some strange behavior
    # if the requirements change post-launch.  For example, if the user was marked as eligible
    # for credit, then a new requirement was added, the user will see that they're eligible
    # AND that one of the requirements is still pending.
    # We're assuming here that (a) we can mitigate this by properly training course teams,
    # and (b) it's a better user experience to allow students who were at one time
    # marked as eligible to continue to be eligible.
    # If we need to, we can always manually move students back to ineligible by
    # deleting CreditEligibility records in the database.
    if is_user_eligible_for_credit(student.username, course_key):
        eligibility_status = "eligible"

    # If the user has *failed* any requirements (for example, if a photo verification is denied),
    # then the user is NOT eligible for credit.
    elif any(requirement['status'] in non_eligible_statuses for requirement in requirement_statuses):
        eligibility_status = "not_eligible"

    # Otherwise, the user may be eligible for credit, but the user has not
    # yet completed all the requirements.
    else:
        eligibility_status = "partial_eligible"

    return {
        'eligibility_status': eligibility_status,
        'requirements': requirement_statuses,
    }


@login_required
@ensure_valid_course_key
def submission_history(request, course_id, student_username, location):
    """Render an HTML fragment (meant for inclusion elsewhere) that renders a
    history of all state changes made by this user for this problem location.
    Right now this only works for problems because that's all
    StudentModuleHistory records.
    """

    course_key = CourseKey.from_string(course_id)

    try:
        usage_key = UsageKey.from_string(location).map_into_course(course_key)
    except (InvalidKeyError, AssertionError):
        return HttpResponse(escape(_(u'Invalid location.')))

    course = get_course_overview_with_access(request.user, 'load', course_key)
    staff_access = bool(has_access(request.user, 'staff', course))

    # Permission Denied if they don't have staff access and are trying to see
    # somebody else's submission history.
    if (student_username != request.user.username) and (not staff_access):
        raise PermissionDenied

    user_state_client = DjangoXBlockUserStateClient()
    try:
        history_entries = list(user_state_client.get_history(student_username, usage_key))
    except DjangoXBlockUserStateClient.DoesNotExist:
        return HttpResponse(escape(_(u'User {username} has never accessed problem {location}').format(
            username=student_username,
            location=location
        )))

    # This is ugly, but until we have a proper submissions API that we can use to provide
    # the scores instead, it will have to do.
    csm = StudentModule.objects.filter(
        module_state_key=usage_key,
        student__username=student_username,
        course_id=course_key)

    scores = BaseStudentModuleHistory.get_history(csm)

    if len(scores) != len(history_entries):
        log.warning(
            "Mismatch when fetching scores for student "
            "history for course %s, user %s, xblock %s. "
            "%d scores were found, and %d history entries were found. "
            "Matching scores to history entries by date for display.",
            course_id,
            student_username,
            location,
            len(scores),
            len(history_entries),
        )
        scores_by_date = {
            score.created: score
            for score in scores
        }
        scores = [
            scores_by_date[history.updated]
            for history in history_entries
        ]

    context = {
        'history_entries': history_entries,
        'scores': scores,
        'username': student_username,
        'location': location,
        'course_id': text_type(course_key)
    }

    return render_to_response('courseware/submission_history.html', context)


def get_static_tab_fragment(request, course, tab):
    """
    Returns the fragment for the given static tab
    """
    loc = course.id.make_usage_key(
        tab.type,
        tab.url_slug,
    )
    field_data_cache = FieldDataCache.cache_for_descriptor_descendents(
        course.id, request.user, modulestore().get_item(loc), depth=0
    )
    tab_module = get_module(
        request.user, request, loc, field_data_cache, static_asset_path=course.static_asset_path, course=course
    )

    logging.debug('course_module = %s', tab_module)

    fragment = Fragment()
    if tab_module is not None:
        try:
            fragment = tab_module.render(STUDENT_VIEW, {})
        except Exception:  # pylint: disable=broad-except
            fragment.content = render_to_string('courseware/error-message.html', None)
            log.exception(
                u"Error rendering course=%s, tab=%s", course, tab['url_slug']
            )

    return fragment


@require_GET
@ensure_valid_course_key
def get_course_lti_endpoints(request, course_id):
    """
    View that, given a course_id, returns the a JSON object that enumerates all of the LTI endpoints for that course.

    The LTI 2.0 result service spec at
    http://www.imsglobal.org/lti/ltiv2p0/uml/purl.imsglobal.org/vocab/lis/v2/outcomes/Result/service.html
    says "This specification document does not prescribe a method for discovering the endpoint URLs."  This view
    function implements one way of discovering these endpoints, returning a JSON array when accessed.

    Arguments:
        request (django request object):  the HTTP request object that triggered this view function
        course_id (unicode):  id associated with the course

    Returns:
        (django response object):  HTTP response.  404 if course is not found, otherwise 200 with JSON body.
    """

    course_key = CourseKey.from_string(course_id)

    try:
        course = get_course(course_key, depth=2)
    except ValueError:
        return HttpResponse(status=404)

    anonymous_user = AnonymousUser()
    anonymous_user.known = False  # make these "noauth" requests like module_render.handle_xblock_callback_noauth
    lti_descriptors = modulestore().get_items(course.id, qualifiers={'category': 'lti'})
    lti_descriptors.extend(modulestore().get_items(course.id, qualifiers={'category': 'lti_consumer'}))

    lti_noauth_modules = [
        get_module_for_descriptor(
            anonymous_user,
            request,
            descriptor,
            FieldDataCache.cache_for_descriptor_descendents(
                course_key,
                anonymous_user,
                descriptor
            ),
            course_key,
            course=course
        )
        for descriptor in lti_descriptors
    ]

    endpoints = [
        {
            'display_name': module.display_name,
            'lti_2_0_result_service_json_endpoint': module.get_outcome_service_url(
                service_name='lti_2_0_result_rest_handler') + "/user/{anon_user_id}",
            'lti_1_1_result_service_xml_endpoint': module.get_outcome_service_url(
                service_name='grade_handler'),
        }
        for module in lti_noauth_modules
    ]

    return HttpResponse(json.dumps(endpoints), content_type='application/json')


@login_required
def course_survey(request, course_id):
    """
    URL endpoint to present a survey that is associated with a course_id
    Note that the actual implementation of course survey is handled in the
    views.py file in the Survey Djangoapp
    """

    course_key = CourseKey.from_string(course_id)
    course = get_course_with_access(request.user, 'load', course_key, check_survey_complete=False)

    redirect_url = reverse(course_home_url_name(course.id), args=[course_id])

    # if there is no Survey associated with this course,
    # then redirect to the course instead
    if not course.course_survey_name:
        return redirect(redirect_url)

    return survey.views.view_student_survey(
        request.user,
        course.course_survey_name,
        course=course,
        redirect_url=redirect_url,
        is_required=course.course_survey_required,
    )


def is_course_passed(student, course, course_grade=None):
    """
    check user's course passing status. return True if passed

    Arguments:
        student : user object
        course : course object
        course_grade (CourseGrade) : contains student grade details.

    Returns:
        returns bool value
    """
    if course_grade is None:
        course_grade = CourseGradeFactory().read(student, course)
    return course_grade.passed


# Grades can potentially be written - if so, let grading manage the transaction.
@transaction.non_atomic_requests
@require_POST
def generate_user_cert(request, course_id):
    """Start generating a new certificate for the user.

    Certificate generation is allowed if:
    * The user has passed & completed the course, and
    * The user does not already have a pending/completed certificate.

    Note that if an error occurs during certificate generation
    (for example, if the queue is down), then we simply mark the
    certificate generation task status as "error" and re-run
    the task with a management command.  To students, the certificate
    will appear to be "generating" until it is re-run.

    Args:
        request (HttpRequest): The POST request to this view.
        course_id (unicode): The identifier for the course.

    Returns:
        HttpResponse: 200 on success, 400 if a new certificate cannot be generated.

    """

    if not request.user.is_authenticated:
        log.info(u"Anon user trying to generate certificate for %s", course_id)
        return HttpResponseBadRequest(
            _('You must be signed in to {platform_name} to create a certificate.').format(
                platform_name=configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME)
            )
        )

    student = request.user
    course_key = CourseKey.from_string(course_id)

    course = modulestore().get_course(course_key, depth=2)
    if not course:
        return HttpResponseBadRequest(_("Course is not valid"))

    if not is_course_passed(student, course):
        log.info(u"User %s has not passed the course: %s", student.username, course_id)
        return HttpResponseBadRequest(_("Your certificate will be available when you pass the course."))

    certificate_status = certs_api.certificate_downloadable_status(student, course.id)

    log.info(
        u"User %s has requested for certificate in %s, current status: is_downloadable: %s, is_generating: %s",
        student.username,
        course_id,
        certificate_status["is_downloadable"],
        certificate_status["is_generating"],
    )

    if certificate_status["is_downloadable"]:
        return HttpResponseBadRequest(_("Certificate has already been created."))
    elif certificate_status["is_generating"]:
        return HttpResponseBadRequest(_("Certificate is being created."))
    else:
        # If the certificate is not already in-process or completed,
        # then create a new certificate generation task.
        # If the certificate cannot be added to the queue, this will
        # mark the certificate with "error" status, so it can be re-run
        # with a management command.  From the user's perspective,
        # it will appear that the certificate task was submitted successfully.
        certs_api.generate_user_certificates(
            student, course.id, course=course, generation_mode='self', site=request.site)
        _track_successful_certificate_generation(student.id, course.id)
        return HttpResponse()


def _track_successful_certificate_generation(user_id, course_id):  # pylint: disable=invalid-name
    """
    Track a successful certificate generation event.

    Arguments:
        user_id (str): The ID of the user generating the certificate.
        course_id (CourseKey): Identifier for the course.
    Returns:
        None

    """
    if settings.LMS_SEGMENT_KEY:
        event_name = 'edx.bi.user.certificate.generate'
        tracking_context = tracker.get_tracker().resolve_context()

        analytics.track(
            user_id,
            event_name,
            {
                'category': 'certificates',
                'label': text_type(course_id)
            },
            context={
                'ip': tracking_context.get('ip'),
                'Google Analytics': {
                    'clientId': tracking_context.get('client_id')
                }
            }
        )


@require_http_methods(["GET", "POST"])
@ensure_valid_usage_key
def render_xblock(request, usage_key_string, check_if_enrolled=True):
    """
    Returns an HttpResponse with HTML content for the xBlock with the given usage_key.
    The returned HTML is a chromeless rendering of the xBlock (excluding content of the containing courseware).
    """
    usage_key = UsageKey.from_string(usage_key_string)

    usage_key = usage_key.replace(course_key=modulestore().fill_in_run(usage_key.course_key))
    course_key = usage_key.course_key

    requested_view = request.GET.get('view', 'student_view')
    if requested_view != 'student_view':
        return HttpResponseBadRequest("Rendering of the xblock view '{}' is not supported.".format(requested_view))

    with modulestore().bulk_operations(course_key):
        # verify the user has access to the course, including enrollment check
        try:
            course = get_course_with_access(request.user, 'load', course_key, check_if_enrolled=check_if_enrolled)
        except CourseAccessRedirect:
            raise Http404("Course not found.")

        # get the block, which verifies whether the user has access to the block.
        block, _ = get_module_by_usage_id(
            request, text_type(course_key), text_type(usage_key), disable_staff_debug_info=True, course=course
        )

        student_view_context = request.GET.dict()
        student_view_context['show_bookmark_button'] = False

        enable_completion_on_view_service = False
        completion_service = block.runtime.service(block, 'completion')
        if completion_service and completion_service.completion_tracking_enabled():
            if completion_service.blocks_to_mark_complete_on_view({block}):
                enable_completion_on_view_service = True
                student_view_context['wrap_xblock_data'] = {
                    'mark-completed-on-view-after-delay': completion_service.get_complete_on_view_delay_ms()
                }

        context = {
            'fragment': block.render('student_view', context=student_view_context),
            'course': course,
            'disable_accordion': True,
            'allow_iframing': True,
            'disable_header': True,
            'disable_footer': True,
            'disable_window_wrap': True,
            'enable_completion_on_view_service': enable_completion_on_view_service,
            'staff_access': bool(has_access(request.user, 'staff', course)),
            'xqa_server': settings.FEATURES.get('XQA_SERVER', 'http://your_xqa_server.com'),
        }
        return render_to_response('courseware/courseware-chromeless.html', context)


# Translators: "percent_sign" is the symbol "%". "platform_name" is a
# string identifying the name of this installation, such as "edX".
FINANCIAL_ASSISTANCE_HEADER = _(
    '{platform_name} now offers financial assistance for learners who want to earn Verified Certificates but'
    ' who may not be able to pay the Verified Certificate fee. Eligible learners may receive up to 90{percent_sign} off'
    ' the Verified Certificate fee for a course.\nTo apply for financial assistance, enroll in the'
    ' audit track for a course that offers Verified Certificates, and then complete this application.'
    ' Note that you must complete a separate application for each course you take.\n We plan to use this'
    ' information to evaluate your application for financial assistance and to further develop our'
    ' financial assistance program.'
).format(
    percent_sign="%",
    platform_name=configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME)
).split('\n')


FA_INCOME_LABEL = _('Annual Household Income')
FA_REASON_FOR_APPLYING_LABEL = _(
    'Tell us about your current financial situation. Why do you need assistance?'
)
FA_GOALS_LABEL = _(
    'Tell us about your learning or professional goals. How will a Verified Certificate in'
    ' this course help you achieve these goals?'
)
FA_EFFORT_LABEL = _(
    'Tell us about your plans for this course. What steps will you take to help you complete'
    ' the course work and receive a certificate?'
)
FA_SHORT_ANSWER_INSTRUCTIONS = _('Use between 250 and 500 words or so in your response.')


@login_required
def financial_assistance(_request):
    """Render the initial financial assistance page."""
    return render_to_response('financial-assistance/financial-assistance.html', {
        'header_text': FINANCIAL_ASSISTANCE_HEADER
    })


@login_required
@require_POST
def financial_assistance_request(request):
    """Submit a request for financial assistance to Zendesk."""
    try:
        data = json.loads(request.body)
        # Simple sanity check that the session belongs to the user
        # submitting an FA request
        username = data['username']
        if request.user.username != username:
            return HttpResponseForbidden()

        course_id = data['course']
        course = modulestore().get_course(CourseKey.from_string(course_id))
        legal_name = data['name']
        email = data['email']
        country = data['country']
        income = data['income']
        reason_for_applying = data['reason_for_applying']
        goals = data['goals']
        effort = data['effort']
        marketing_permission = data['mktg-permission']
        ip_address = get_ip(request)
    except ValueError:
        # Thrown if JSON parsing fails
        return HttpResponseBadRequest(u'Could not parse request JSON.')
    except InvalidKeyError:
        # Thrown if course key parsing fails
        return HttpResponseBadRequest(u'Could not parse request course key.')
    except KeyError as err:
        # Thrown if fields are missing
        return HttpResponseBadRequest(u'The field {} is required.'.format(text_type(err)))

    zendesk_submitted = _record_feedback_in_zendesk(
        legal_name,
        email,
        u'Financial assistance request for learner {username} in course {course_name}'.format(
            username=username,
            course_name=course.display_name
        ),
        u'Financial Assistance Request',
        {'course_id': course_id},
        # Send the application as additional info on the ticket so
        # that it is not shown when support replies. This uses
        # OrderedDict so that information is presented in the right
        # order.
        OrderedDict((
            ('Username', username),
            ('Full Name', legal_name),
            ('Course ID', course_id),
            ('Annual Household Income', income),
            ('Country', country),
            ('Allowed for marketing purposes', 'Yes' if marketing_permission else 'No'),
            (FA_REASON_FOR_APPLYING_LABEL, '\n' + reason_for_applying + '\n\n'),
            (FA_GOALS_LABEL, '\n' + goals + '\n\n'),
            (FA_EFFORT_LABEL, '\n' + effort + '\n\n'),
            ('Client IP', ip_address),
        )),
        group_name='Financial Assistance',
        require_update=True
    )

    if not zendesk_submitted:
        # The call to Zendesk failed. The frontend will display a
        # message to the user.
        return HttpResponse(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return HttpResponse(status=status.HTTP_204_NO_CONTENT)


@login_required
def financial_assistance_form(request):
    """Render the financial assistance application form page."""
    user = request.user
    enrolled_courses = get_financial_aid_courses(user)
    incomes = ['Less than $5,000', '$5,000 - $10,000', '$10,000 - $15,000', '$15,000 - $20,000', '$20,000 - $25,000']
    annual_incomes = [
        {'name': _(income), 'value': income} for income in incomes  # pylint: disable=translation-of-non-string
    ]
    return render_to_response('financial-assistance/apply.html', {
        'header_text': FINANCIAL_ASSISTANCE_HEADER,
        'student_faq_url': marketing_link('FAQ'),
        'dashboard_url': reverse('dashboard'),
        'account_settings_url': reverse('account_settings'),
        'platform_name': configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME),
        'user_details': {
            'email': user.email,
            'username': user.username,
            'name': user.profile.name,
            'country': text_type(user.profile.country.name),
        },
        'submit_url': reverse('submit_financial_assistance_request'),
        'fields': [
            {
                'name': 'course',
                'type': 'select',
                'label': ungettext('Course', 'Courses', 1),
                'placeholder': '',
                'defaultValue': '',
                'required': True,
                'options': enrolled_courses,
                'instructions': _(
                    'Select the course for which you want to earn a verified certificate. If'
                    ' the course does not appear in the list, make sure that you have enrolled'
                    ' in the audit track for the course.'
                )
            },
            {
                'name': 'income',
                'type': 'select',
                'label': FA_INCOME_LABEL,
                'placeholder': '',
                'defaultValue': '',
                'required': True,
                'options': annual_incomes,
                'instructions': _('Specify your annual household income in US Dollars.')
            },
            {
                'name': 'reason_for_applying',
                'type': 'textarea',
                'label': FA_REASON_FOR_APPLYING_LABEL,
                'placeholder': '',
                'defaultValue': '',
                'required': True,
                'restrictions': {
                    'min_length': settings.FINANCIAL_ASSISTANCE_MIN_LENGTH,
                    'max_length': settings.FINANCIAL_ASSISTANCE_MAX_LENGTH
                },
                'instructions': FA_SHORT_ANSWER_INSTRUCTIONS
            },
            {
                'name': 'goals',
                'type': 'textarea',
                'label': FA_GOALS_LABEL,
                'placeholder': '',
                'defaultValue': '',
                'required': True,
                'restrictions': {
                    'min_length': settings.FINANCIAL_ASSISTANCE_MIN_LENGTH,
                    'max_length': settings.FINANCIAL_ASSISTANCE_MAX_LENGTH
                },
                'instructions': FA_SHORT_ANSWER_INSTRUCTIONS
            },
            {
                'name': 'effort',
                'type': 'textarea',
                'label': FA_EFFORT_LABEL,
                'placeholder': '',
                'defaultValue': '',
                'required': True,
                'restrictions': {
                    'min_length': settings.FINANCIAL_ASSISTANCE_MIN_LENGTH,
                    'max_length': settings.FINANCIAL_ASSISTANCE_MAX_LENGTH
                },
                'instructions': FA_SHORT_ANSWER_INSTRUCTIONS
            },
            {
                'placeholder': '',
                'name': 'mktg-permission',
                'label': _(
                    'I allow edX to use the information provided in this application '
                    '(except for financial information) for edX marketing purposes.'
                ),
                'defaultValue': '',
                'type': 'checkbox',
                'required': False,
                'instructions': '',
                'restrictions': {}
            }
        ],
    })


def get_financial_aid_courses(user):
    """ Retrieve the courses eligible for financial assistance. """
    financial_aid_courses = []
    for enrollment in CourseEnrollment.enrollments_for_user(user).order_by('-created'):

        if enrollment.mode != CourseMode.VERIFIED and \
                enrollment.course_overview and \
                enrollment.course_overview.eligible_for_financial_aid and \
                CourseMode.objects.filter(
                    Q(_expiration_datetime__isnull=True) | Q(_expiration_datetime__gt=datetime.now(UTC)),
                    course_id=enrollment.course_id,
                    mode_slug=CourseMode.VERIFIED).exists():

            financial_aid_courses.append(
                {
                    'name': enrollment.course_overview.display_name,
                    'value': text_type(enrollment.course_id)
                }
            )

    return financial_aid_courses


def decode_datetime(dts):
    try:
        return datetime.strptime(dts, '%Y-%m-%dT%H:%M')
    except Exception as e:
        return datetime.strptime(dts, '%d-%m-%YT%H:%M')


def convert_datetime(date_str, date_format=None):
    if not date_format:
        date_format = configuration_helpers.get_value("ILT_DATE_FORMAT", "YYYY-MM-DD HH:mm")
    date_format = date_format.replace("YYYY", "%Y").replace("DD", "%d").replace(
        "MM", "%m"
    ).replace("HH", "%H").replace("mm", "%M")

    return decode_datetime(date_str).strftime(date_format)


@login_required
def ilt_validation_list(request):
    ilt_follow_up_enabled = configuration_helpers.get_value('ILT_FOLLOW_UP_ENABLED', False)
    if not ilt_follow_up_enabled:
        raise Http404
    user = request.user
    supervised_learners = UserProfile.objects.filter(lt_ilt_supervisor=user.email)
    if not supervised_learners:
        raise Http404
    return render_to_response("courseware/ilt_all_validations_page.html")


@login_required
@csrf_exempt
def ilt_batch_enroll(request):
    """
    batch enroll, this will bypass validation
    """
    data = json.loads(request.body)
    usage_id = data['usage_key']
    learners_id = data['learners']
    session_nb = data['session_nb']
    course_name = data['course_name']
    module_name = data['module_name']
    session_info = data['session_info']
    session_info['start_at'] = convert_datetime(session_info['start_at'])
    session_info['end_at'] = convert_datetime(session_info['end_at'])
    usage_key = UsageKey.from_string(usage_id)
    info = {
        "status": "confirmed",
        "accommodation": "no",
        "comment": "",
        "number_of_one_way": 1,
        "number_of_return": 1,
        "hotel": ""
    }
    user_info_dict = {user_id: info for user_id in learners_id}
    enrolled_users = XModuleUserStateSummaryField.objects.filter(
        usage_id=usage_key, field_name="enrolled_users"
    )
    if enrolled_users.exists():
        enrolled_users = enrolled_users.first()
        value = json.loads(enrolled_users.value)
        if session_nb in value:
            value[session_nb].update(user_info_dict)
        else:
            value[session_nb] = user_info_dict
        enrolled_users.value = json.dumps(value)
        enrolled_users.save()
    else:
        enrolled_users = XModuleUserStateSummaryField.objects.create(
            usage_id=usage_key, field_name="enrolled_users", value=json.dumps({session_nb: user_info_dict})
        )
    ilt_block = modulestore().get_item(usage_key)
    section_id = ilt_block.get_parent().parent.block_id
    chapter_id = ilt_block.get_parent().get_parent().parent.block_id
    url = reverse('courseware_section', args=[ilt_block.course_id, chapter_id, section_id])
    url = request.build_absolute_uri(url)
    for user_id in learners_id:
        learner = User.objects.get(id=user_id)
        if settings.LEARNER_NO_EMAIL and learner.email.endswith(settings.LEARNER_NO_EMAIL):
            email = learner.profile.lt_ilt_supervisor
        else:
            email = learner.email
        params = {'message': 'ilt_confirmed',
                  'name': learner.profile.name or learner.username,
                  'ilt_link': url, 'site_name': None,
                  'ilt_name': module_name,
                  'course_name': course_name,
                  'session_info': session_info}
        send_mail_to_student(email, params, language=get_user_email_language(request.user))
    return JsonResponse(status=200)


def get_ilt_module_info(ilt_module, deadline=None):
    sessions_info = json.loads(ilt_module.value)
    sessions = sessions_info.items()
    for k, v in sessions[:]:
        if k == 'counter':
            sessions.remove((k, v))
        else:
            v['available_seats'] = v['total_seats']
    sessions.sort(key=lambda itm: decode_datetime(itm[1]['start_at']))

    default_format = "{start_at} - {end_at} | {timezone} | location: {location} | #{nb}"
    custom_format = configuration_helpers.get_value("ILT_DROPDOWN_LIST_FORMAT", "")
    if not custom_format:
        custom_format = default_format

    date_format = configuration_helpers.get_value("ILT_DATE_FORMAT", "")
    if date_format:
        date_format = date_format.replace("YYYY", "%Y").replace("DD", "%d").replace(
            "MM", "%m"
        ).replace("HH", "%H").replace("mm", "%M")

    dropdown_list = []

    if deadline is None:
        deadline = 0
    for k, session in sessions[:]:
        class_list = []
        if datetime.now() - decode_datetime(session['start_at']) > timedelta(days=1):
            class_list.append('expire-for-student')
            sessions.remove((k, session))
        if datetime.now() - decode_datetime(session['end_at']) > timedelta(days=180):
            class_list.append('expire-for-admin')
        if decode_datetime(session['start_at']) - datetime.now() < timedelta(days=deadline):
            class_list.append('within-deadline')
            session['within_deadline'] = True
        else:
            session['within_deadline'] = False

        extra_class = " ".join(class_list)
        if date_format:
            start_at = decode_datetime(session['start_at']).strftime(date_format)
            end_at = decode_datetime(session['end_at']).strftime(date_format)
        else:
            start_at = session['start_at'].replace("T", " ")
            end_at = session['end_at'].replace("T", " ")
        session_data = {
            "start_at": start_at,
            "end_at": end_at,
            "duration": session.get("duration", ""),
            "instructor": session.get("instructor", ""),
            "area_region": session.get("area_region", ""),
            "address": session.get("address", ""),
            "zip_code": session.get("zip_code", ""),
            "city": session.get("city", ""),
            "location_id": session.get("location_id", ""),
            "location": session.get("location", ""),
            "timezone": session.get("timezone", ""),
            "nb": k
        }
        dropdown_list.append([custom_format.format(**session_data), extra_class, k])

    return {"sessions": sessions, "dropdown_list": dropdown_list, "raw": sessions_info}


@login_required
@csrf_exempt
def ilt_validation_request_data(request):
    """
    This is the api for ILT Follow-up page. return JSON format data
    We retreive the data in courseware/ilt_all_validations_page.html
    by ajax call
    """
    learner_no_email = settings.LEARNER_NO_EMAIL
    accommodation = configuration_helpers.get_value("ILT_ACCOMMODATION_ENABLED", False)
    if request.method == "POST":
        data = json.loads(request.body)
        usage_id = data['usage_key']
        course_id = data['course_key']
        learner_id = data['user_id']
        learner = User.objects.get(id=learner_id)
        session_id = data['session_id']
        action = data.get('action', None)
        info = data.get('info', {})
        usage_key = UsageKey.from_string(usage_id)
        ilt_block = modulestore().get_item(usage_key)
        course_key = CourseKey.from_string(course_id)
        course = modulestore().get_course(course_key)
        summary = XModuleUserStateSummaryField.objects.get(usage_id=usage_key, field_name="enrolled_users")
        sessions = XModuleUserStateSummaryField.objects.get(usage_id=usage_key, field_name="sessions")
        session_data = json.loads(sessions.value)
        session_info = session_data[session_id]
        session_info['start_at'] = convert_datetime(session_info['start_at'])
        session_info['end_at'] = convert_datetime(session_info['end_at'])
        enrolled_users = json.loads(summary.value)
        section_id = ilt_block.get_parent().parent.block_id
        chapter_id = ilt_block.get_parent().get_parent().parent.block_id

        for k, v in enrolled_users.items():
            if str(learner_id) in v:
                registered_session = k

        if action == 'approved':
            if accommodation and info['accommodation'] == 'yes':
                info['status'] = 'accepted'
            else:
                url = reverse('courseware_section', args=[course_key, chapter_id, section_id])
                url = request.build_absolute_uri(url)
                info['status'] = 'confirmed'
                params = {'message': 'ilt_confirmed',
                          'name': learner.profile.name or learner.username,
                          'ilt_link': url, 'site_name': None,
                          'ilt_name': ilt_block.display_name,
                          'course_name': course.display_name,
                          'session_info': session_info}

                email = learner.email
                if learner_no_email and email.endswith(learner_no_email):
                    email = learner.profile.lt_ilt_supervisor
                send_mail_to_student(email, params, language=get_user_email_language(request.user))
        elif action == 'refused':
            info['status'] = 'refused'
            url = reverse('courseware_section', args=[course_key, chapter_id, section_id])
            url = request.build_absolute_uri(url)
            params = {'message': 'ilt_refused',
                      'name': learner.profile.name or learner.username,
                      'ilt_link': url, 'site_name': None,
                      'ilt_name': ilt_block.display_name,
                      'course_name': course.display_name,
                      'session_info': session_info}

            email = learner.email
            if learner_no_email and email.endswith(learner_no_email):
                email = learner.profile.lt_ilt_supervisor
            send_mail_to_student(email, params, language=get_user_email_language(request.user))

        # in case ILT supervisor altered learner's request session number
        if session_id != registered_session:
            old_info = enrolled_users[registered_session].pop(str(learner_id))
            if session_id in enrolled_users:
                enrolled_users[session_id][str(learner_id)] = old_info
            else:
                enrolled_users[session_id] = {str(learner_id): old_info}

        old_info = enrolled_users[session_id][str(learner_id)]
        if old_info['status'] in ['confirmed', 'accepted']:
            hotel_reservation = []
            updated = False
            for k, v in old_info.items():
                if k in ['status', 'hotel']:
                    continue
                if v != info[k]:
                    updated = True

                    if k == 'accommodation' and v == 'yes':
                        if old_info.get('hotel'):
                            hotel_info = "Name: {user_name}, Hotel Booked: {hotel_booked}".format(
                                user_name=learner.profile.name,
                                hotel_booked=old_info.get('hotel')
                            )
                            hotel_reservation.append(hotel_info)
                            old_info['hotel'] = ''
                        else:
                            old_info['status'] = 'confirmed'
                    if k == 'accommodation' and v == 'no':
                        old_info['status'] = 'accepted'

                    old_info[k] = info[k]
            if updated:
                url = reverse('courseware_section', args=[course_key, chapter_id, section_id])
                url = request.build_absolute_uri(url)
                params = {'message': 'ilt_request_updated',
                          'name': learner.profile.name or learner.username,
                          'ilt_link': url, 'site_name': None,
                          'ilt_name': ilt_block.display_name,
                          'course_name': course.display_name,
                          'session_info': session_info,
                          'request_info': old_info}
                email = learner.email
                if learner_no_email and email.endswith(learner_no_email):
                    email = learner.profile.lt_ilt_supervisor
                info = old_info
                send_mail_to_student(email, params, language=get_user_email_language(request.user))

                if hotel_reservation:
                    params = {
                        'name': '',
                        'ilt_link': url,
                        'ilt_name': ilt_block.display_name,
                        'site_name': None,
                        'hotel_info': hotel_reservation,
                        'message': 'ilt_hotel_cancel',
                        'action': 'ilt_hotel_cancel',
                        'course_name': course.display_name,
                        'session_info': session_info
                    }
                    course_admins = CourseInstructorRole(course_key).users_with_role()
                    for u in course_admins:
                        params['name'] = u.profile.name or u.username
                        send_mail_to_student(u.email, params, language=get_user_email_language(request.user))

        enrolled_users[session_id][str(learner_id)].update(info)
        summary.value = json.dumps(enrolled_users)
        summary.save()
        return JsonResponse(status=200)

    user = request.user
    learners = User.objects.filter(profile__lt_ilt_supervisor=user.email, is_active=True).select_related(
        "profile").only('id', 'username', 'profile__name', 'profile__lt_employee_id',
                        'profile__profile_image_uploaded_at')
    learners_id = [i.id for i in learners]
    course_enrollments = CourseEnrollment.objects.filter(user__in=learners, is_active=True).select_related(
        'user__profile'
    ).only("course_id", "user__is_staff", "user__username", "user__profile__name")
    course_keys = list(set([i.course_id for i in course_enrollments]))
    date_format = configuration_helpers.get_value("ILT_DATE_FORMAT", "YYYY-MM-DD HH:mm")
    result = {"pending_all": [], "approved_all": [], "declined_all": [], "session_info": {},
              "accommodation": accommodation, "date_format": date_format}
    course_module_dict = {}
    module_course_dict = {}
    ilt_modules_info = {}
    for course_key in course_keys:
        try:
            ilt_blocks = modulestore().get_items(course_key, qualifiers={'category': 'ilt'})
            course_name = modulestore().get_items(course_key, qualifiers={'category': 'course'})[0].display_name
        except ItemNotFoundError:
            continue
        if not ilt_blocks:
            continue

        course_module_dict[unicode(course_key)] = {
            'course_name': course_name,
            'modules': []
        }
        enrollment = course_enrollments.filter(course_id=course_key)
        enrollment_user_list = {str(i.user.id): {
            'user_name': i.user.username,
            'full_name': i.user.profile.name,
            'checked': False,
            'is_staff': i.user.is_staff
        } for i in enrollment}
        for i in ilt_blocks:
            module_name = i.display_name
            ilt_modules_info[i.location] = {
                "deadline": i.deadline, "sessions": [], "enrollment_user_list": enrollment_user_list.copy(),
                "module_name": module_name
            }
            visible_to_staff_only = i.visible_to_staff_only
            module_course_dict[unicode(i.location)] = (module_name, unicode(course_key), visible_to_staff_only)
            course_module_dict[unicode(course_key)]['modules'].append(
                (module_name, unicode(i.location), ilt_modules_info[i.location]['sessions'],
                 ilt_modules_info[i.location]['enrollment_user_list'])
            )

    all_ilt_modules = XModuleUserStateSummaryField.objects.filter(
        field_name="sessions", usage_id__in=ilt_modules_info
    ).only("value", "usage_id")
    all_ilt_enrollments = XModuleUserStateSummaryField.objects.filter(
        field_name="enrolled_users", usage_id__in=ilt_modules_info
    ).only("value", "usage_id")

    for module in all_ilt_modules:
        course_id = module.usage_id.course_key
        deadline = ilt_modules_info[module.usage_id]['deadline']
        info = get_ilt_module_info(module, deadline)
        ilt_modules_info[module.usage_id]['sessions'].extend(info['sessions'])
        ilt_modules_info[module.usage_id]['dropdown_list'] = info['dropdown_list']
        ilt_modules_info[module.usage_id]['raw'] = info['raw']
        if unicode(course_id) in result["session_info"]:
            result["session_info"][unicode(course_id)][unicode(module.usage_id)] = info['raw']
        else:
            result["session_info"][unicode(course_id)] = {unicode(module.usage_id): info['raw']}

    for ilt_enrollment in all_ilt_enrollments:
        data = json.loads(ilt_enrollment.value)
        course_id = ilt_enrollment.usage_id.course_key
        module_info = ilt_modules_info[ilt_enrollment.usage_id]
        user_list = module_info['enrollment_user_list']
        sessions_info = ilt_modules_info[ilt_enrollment.usage_id]['raw']
        for k, v in data.items():
            start_at = sessions_info[k]['start_at']
            available_seats = sessions_info[k]['available_seats']
            expired = datetime.now() - decode_datetime(start_at) > timedelta(days=1)
            if expired:
                continue

            for user_id, request_info in v.items():
                if request_info['status'] != 'refused':
                    available_seats -= 1
                if user_id in user_list:
                    if request_info['status'] != 'refused':
                        user_list.pop(user_id, None)
                    learner = learners.get(id=user_id)
                    request_info.update({
                        "start": start_at,
                        "employee_id": learner.profile.lt_employee_id,
                        "learner_name": learner.profile.name,
                        "user_name": learner.username,
                        "user_id": learner.id,
                        "avatar": get_profile_image_urls_for_user(learner, request=request)["medium"],
                        "module": module_info['module_name'],
                        "course": course_module_dict[unicode(course_id)]['course_name'],
                        "dropdown_list": module_info['dropdown_list'],
                        "usage_key": unicode(ilt_enrollment.usage_id),
                        "course_key": unicode(course_id),
                        "session_id": k,
                        "is_editing": False,
                        "action": None
                    })
                    if request_info['status'] == "pending":
                        result["pending_all"].append(request_info)
                    elif request_info['status'] == "refused":
                        result["declined_all"].append(request_info)
                    else:
                        result["approved_all"].append(request_info)
                else:
                    continue

            sessions_info[k]['available_seats'] = available_seats

    result.update({
        'course_module_dict': course_module_dict,
        'module_course_dict': module_course_dict
    })
    result["pending_all"].sort(key=lambda x: decode_datetime(x['start']))
    result["approved_all"].sort(key=lambda x: decode_datetime(x['start']))
    result["declined_all"].sort(key=lambda x: decode_datetime(x['start']))

    return JsonResponse(result, status=200)


def ilt_registration_validation(request, course_id, usage_id, user_id):
    """
    This is the individual validation page, deprecated soon
    """
    usage_key = UsageKey.from_string(usage_id)
    learner_no_email = settings.LEARNER_NO_EMAIL
    try:
        user = User.objects.get(id=user_id)
        request.user = user
        summary = XModuleUserStateSummaryField.objects.get(usage_id=usage_key, field_name="enrolled_users")
        sessions = XModuleUserStateSummaryField.objects.get(usage_id=usage_key, field_name="sessions")
        data = json.loads(summary.value)
        session_data = json.loads(sessions.value)
        registration_info = None
        registered_session = ""
        for k, v in data.items():
            if str(user_id) in v:
                registration_info = v[str(user_id)]
                registered_session = k
        if not registration_info:
            log.info("ILT request does not exist. User: {user_id}, Usage_id: {usage_id}".format(
                user_id=user_id,
                usage_id=usage_id
            ))
            raise Http404
        if registered_session not in session_data:
            log.info("Invalid session id: {session_id}".format(
                session_id=registered_session
            ))
            raise Http404

    except Exception as e:
        log.error(e)
        raise Http404

    course_key = CourseKey.from_string(course_id)
    course = modulestore().get_course(course_key)
    ilt_block = modulestore().get_item(usage_key)
    if request.method == "GET":
        if registration_info['status'] == "pending":
            msg = ''
        elif registration_info['status'] == "refused":
            msg = _("Enrollment refused")
        else:
            msg = _("Enrollment accepted. If a hotel request has been done, "
                    "you will receive a confirmation as soon as it is processed.")
        enrollment = [registered_session, registration_info]
        response = handle_xblock_callback(
            request,
            course_id,
            usage_id,
            'student_handler'
        )
        student_data = json.loads(response.content)
        student_data['enrollment'] = enrollment
        student_data['disable_footer'] = True
        student_data['user'] = user
        student_data['msg'] = msg
        student_data['course_name'] = course.display_name
        student_data['session_name'] = ilt_block.display_name

        for idx, val in enumerate(student_data['sessions']):
            if val[0] == registered_session:
                student_data["selected_index"] = idx
        return render_to_response(
            'courseware/ilt_validation.html',
            student_data
        )

    if request.method == "POST":
        action = request.POST.get("action")
        session_number = request.POST.get("session_number")
        session_info = deepcopy(session_data[session_number])
        if 'start_at' in session_info and 'end_at' in session_info:
            session_info['start_at'] = convert_datetime(session_info['start_at'])
            session_info['end_at'] = convert_datetime(session_info['end_at'])
        if action == 'accept':

            msg = _("Enrollment accepted. If a hotel request has been done, "
                    "you will receive a confirmation as soon as it is processed.")
            for k in registration_info:
                if k in request.POST:
                    registration_info[k] = request.POST.get(k)

            number_of_one_way = registration_info['number_of_one_way']
            number_of_return = registration_info['number_of_return']
            try:
                registration_info['number_of_one_way'] = int(number_of_one_way)
            except Exception as e:
                registration_info['number_of_one_way'] = 0
            try:
                registration_info['number_of_return'] = int(number_of_return)
            except Exception as e:
                registration_info['number_of_return'] = 0
            accommodation = configuration_helpers.get_value("ILT_ACCOMMODATION_ENABLED", False)
            if accommodation and registration_info['accommodation'] == 'yes':
                registration_info['status'] = 'accepted'
            else:
                section_id = ilt_block.get_parent().parent.block_id
                chapter_id = ilt_block.get_parent().get_parent().parent.block_id
                url = reverse('courseware_section', args=[course_id, chapter_id, section_id])
                url = request.build_absolute_uri(url)
                registration_info['status'] = 'confirmed'
                params = {'message': 'ilt_confirmed',
                          'name': user.profile.name or user.username,
                          'ilt_link': url, 'site_name': None,
                          'ilt_name': ilt_block.display_name,
                          'course_name': course.display_name,
                          'session_info': session_info}

                email = user.email
                if learner_no_email and email.endswith(learner_no_email):
                    email = user.profile.lt_ilt_supervisor
                send_mail_to_student(email, params, language=get_user_email_language(user))

            # in case ILT supervisor altered learner's request session number
            if session_number != registered_session:
                data[registered_session].pop(str(user_id), None)
                if session_number in data:
                    data[session_number][str(user_id)] = registration_info
                else:
                    data[session_number] = {str(user_id): registration_info}
            else:
                data[registered_session][str(user_id)] = registration_info
        else:
            registration_info['status'] = 'refused'
            data[registered_session][str(user_id)] = registration_info
            ilt_block = modulestore().get_item(usage_key)
            section_id = ilt_block.get_parent().parent.block_id
            chapter_id = ilt_block.get_parent().get_parent().parent.block_id
            url = reverse('courseware_section', args=[course_id, chapter_id, section_id])
            url = request.build_absolute_uri(url)
            params = {'message': 'ilt_refused',
                      'name': user.profile.name or user.username,
                      'ilt_link': url, 'site_name': None,
                      'ilt_name': ilt_block.display_name,
                      'course_name': course.display_name,
                      'session_info': session_info}

            email = user.email
            if learner_no_email and email.endswith(learner_no_email):
                email = user.profile.lt_ilt_supervisor
            send_mail_to_student(email, params, language=get_user_email_language(user))
            msg = _("Enrollment refused")
        summary.value = json.dumps(data)
        summary.save()
        return JsonResponse({"msg": msg}, status=200)


def ilt_attendance_sheet(request, course_id, usage_id, sess_key):

    course_key = CourseKey.from_string(course_id)
    usage_key = UsageKey.from_string(usage_id)
    try:
        summary = XModuleUserStateSummaryField.objects.get(usage_id=usage_key, field_name="enrolled_users")
        enrolled_data = json.loads(summary.value)
        enrolled_user_ids = [key for key in enrolled_data.get(sess_key, {})
                             if enrolled_data[sess_key][key]['status'] in ("accepted", "confirmed")]
        enrolled_users = User.objects.filter(id__in=enrolled_user_ids).select_related("profile")
    except Exception as e:
        enrolled_users = []

    sessions = XModuleUserStateSummaryField.objects.get(usage_id=usage_key, field_name="sessions")
    session_data = json.loads(sessions.value)
    course = modulestore().get_course(course_key)
    ilt_block = modulestore().get_item(usage_key)

    session = session_data[sess_key]

    date_format = configuration_helpers.get_value("ILT_DATE_FORMAT", "")
    if date_format:
        date_format = date_format.replace("YYYY", "%Y").replace("DD", "%d").replace(
            "MM", "%m"
        ).replace("HH", "%H").replace("mm", "%M")
        start_at = decode_datetime(session['start_at']).strftime(date_format)
        end_at = decode_datetime(session['end_at']).strftime(date_format)
    else:
        start_at = session['start_at'].replace("T", " ")
        end_at = session['end_at'].replace("T", " ")
    context = {
        'course_name': course.display_name,
        'session_name': ilt_block.display_name,
        'start_at': start_at,
        'end_at': end_at,
        'duration': session.get('duration', ''),
        'location_name': session.get('location', ''),
        'location_id': session.get('location_id'),
        'address': session.get('address', ''),
        'city': session.get('city', ''),
        'zip_code': session.get('zip_code', ''),
        'disable_footer': True,
        'is_secure': request.is_secure(),
        'enrolled_users': enrolled_users
    }
    return render_to_response('courseware/ilt_attendance_sheet.html', context)


def session_to_str(session_info, session_number):
    default_format = "{start_at} - {end_at} | {timezone} | location: {location} | #{nb}"
    custom_format = configuration_helpers.get_value("ILT_DROPDOWN_LIST_FORMAT", "")
    if not custom_format:
        custom_format = default_format

    session_info['start_at'] = convert_datetime(session_info['start_at'])
    session_info['end_at'] = convert_datetime(session_info['end_at'])
    session_info['nb'] = session_number
    return custom_format.format(**session_info)


# ilt ILT: daily script for hotel booking
def group_courses_by_admin():

    summaries = XModuleUserStateSummaryField.objects.filter(field_name='enrolled_users')
    admin_course_dict = {}
    course_session_dict = {}
    for s in summaries:
        try:
            usage_id = s.usage_id
            ilt_block = modulestore().get_item(usage_id)
            course_id = ilt_block.course_id
            enrolled_user_info = json.loads(s.value)
            sessions = XModuleUserStateSummaryField.objects.get(usage_id=usage_id, field_name="sessions")
            sessions_info = json.loads(sessions.value)
            remind_session_list = []
            for session_id, users in enrolled_user_info.items():
                for v in users.values():
                    info = sessions_info[session_id]
                    expired = datetime.now() - decode_datetime(info['start_at']) > timedelta(days=1)
                    if v.get('accommodation') == 'yes' and v.get('status') == 'accepted' and not expired:
                        remind_session_list.append(session_to_str(info, session_id))
                        break
            if not remind_session_list:
                continue
            remind_session_list.sort()
            if course_id in course_session_dict:
                course_session_dict[course_id][ilt_block] = remind_session_list
            else:
                course_session_dict[course_id] = {ilt_block: remind_session_list}

        except ItemNotFoundError:
            ilt_log.error("ilt block: {usage_id} does not exist.".format(usage_id=usage_id))

    course_id_list = list(course_session_dict)
    for c in course_id_list:
        try:

            course_admins = CourseInstructorRole(c).users_with_role()
            for admin in course_admins:
                if admin in admin_course_dict:
                    admin_course_dict[admin].append(c)
                else:
                    admin_course_dict[admin] = [c]
        except Exception as e:
            ilt_log.error(e.message)

    return admin_course_dict, course_session_dict


def process_ilt_hotel_check_email():

    admin_course_dict, course_session_dict = group_courses_by_admin()
    stripped_site_name = configuration_helpers.get_value(
        'SITE_NAME',
        settings.SITE_NAME
    )
    logo_url = u'{proto}://{site}{path}'.format(
        proto="https",
        site=stripped_site_name,
        path=get_logo_url()
    )
    for admin, courses in admin_course_dict.items():
        email = admin.email
        params = {"course_list": [], "message": "ilt_hotel_booking_check", "site_name": None, "logo_url": logo_url}
        for c in courses:
            course = modulestore().get_course(c)
            course_name = course.display_name
            temp = {"course_name": course_name, "modules": []}
            block_sessions = course_session_dict[c]
            for ilt_block, sessions in block_sessions.items():
                module_name = ilt_block.display_name
                section_id = ilt_block.get_parent().parent.block_id
                chapter_id = ilt_block.get_parent().get_parent().parent.block_id
                url = u'{proto}://{site}{path}'.format(
                    proto="https",
                    site=stripped_site_name,
                    path=reverse('courseware_section', args=[unicode(c), chapter_id, section_id])
                )
                x = {"module_name": module_name, "sessions": sessions, 'link': url}
                temp["modules"].append(x)
            params["course_list"].append(temp)

        ilt_log.info("sending notification email to {email}, courses: {course_ids}".format(
            email=email,
            course_ids=params["course_list"]
        ))
        send_mail_to_student(email, params, language=get_user_email_language(admin))


def process_ilt_validation_check_email():
    """
    ILT validation daily check
    Unenroll users who are inactive or whose enrollment is inactive already
    """
    summaries = XModuleUserStateSummaryField.objects.filter(field_name='enrolled_users')
    ilt_supervisor_list = []
    stripped_site_name = configuration_helpers.get_value(
        'SITE_NAME',
        settings.SITE_NAME
    )
    for s in summaries:
        try:
            usage_id = s.usage_id
            course_key = usage_id.course_key
            course = modulestore().get_course(course_key)
            ilt_block = modulestore().get_item(usage_id)
            section_id = ilt_block.get_parent().parent.block_id
            chapter_id = ilt_block.get_parent().get_parent().parent.block_id
            sessions_summary = XModuleUserStateSummaryField.objects.get(field_name="sessions", usage_id=usage_id)
            url = reverse('courseware_section', args=[course_key, chapter_id, section_id])
            url = u'{proto}://{site}{path}'.format(
                proto="https",
                site=stripped_site_name,
                path=url
            )
            sessions_info = json.loads(sessions_summary.value)
            enrolled_user_info = json.loads(s.value)
            require_save = False
            hotel_reservation = []
            unenrolled_users = []
            for session_id, users in enrolled_user_info.items():
                end_at = sessions_info[session_id]['end_at']
                expired = datetime.now() > decode_datetime(end_at)
                if expired:
                    for user_id, v in users.items():
                        if v['status'] == 'pending':
                            v['status'] = 'refused'
                            require_save = True
                else:
                    enrollments = CourseEnrollment.objects.filter(
                        Q(is_active=False) | Q(user__is_active=False),
                        user_id__in=users,
                        course_id=course_key
                    ).only("user", "user__profile")
                    for enrollment in enrollments:
                        user_info = users.pop(str(enrollment.user.id))
                        unenrolled_users.append(enrollment.user.id)
                        if user_info.get('status') == 'confirmed' and\
                                user_info.get('accommodation') == 'yes' and user_info.get('hotel'):
                            hotel_info = "Name: {user_name}, Hotel Booked: {hotel_booked}".format(
                                user_name=enrollment.user.profile.name,
                                hotel_booked=user_info.get('hotel')
                            )
                            hotel_reservation.append(hotel_info)
                        require_save = True
                    for user_id, v in users.items():
                        if v['status'] == 'pending':
                            user = User.objects.get(id=user_id)
                            email = user.profile.lt_ilt_supervisor
                            if email and email not in ilt_supervisor_list:
                                ilt_supervisor_list.append(email)

            if unenrolled_users:
                ilt_validation_log.info(
                    "ILT batch unenrollment from Daily script, course: {}, block: {}, users: {}".format(
                        course_key, usage_id, unenrolled_users
                    )
                )
            if require_save:
                s.value = json.dumps(enrolled_user_info)
                s.save()
            if hotel_reservation:
                params = {
                    'name': '',
                    'ilt_link': url,
                    'ilt_name': ilt_block.display_name,
                    'site_name': None,
                    'hotel_info': hotel_reservation,
                    'message': 'ilt_hotel_cancel',
                    'action': 'ilt_hotel_cancel',
                    'course_name': course.display_name
                }
                course_admins = CourseInstructorRole(course_key).users_with_role()
                for u in course_admins:
                    params['name'] = u.profile.name or u.username
                    send_mail_to_student(u.email, params, language=get_user_email_language(u))
        except ItemNotFoundError:
            ilt_validation_log.error("ilt block: {usage_id} does not exist.".format(usage_id=usage_id))

    url = u'{proto}://{site}{path}'.format(
        proto="https",
        site=stripped_site_name,
        path=reverse("ilt_validation_list")
    )
    params = {"message": "ilt_follow_up", "link": url, "site_name": None}
    for i in ilt_supervisor_list:
        try:
            supervisor = User.objects.get(email=i)
            lang = get_user_email_language(supervisor)
        except User.DoesNotExist:
            lang = None

        ilt_log.info("sending ILT validation daily email to {}".format(i))
        send_mail_to_student(i, param_dict=params, language=lang)


def process_virtual_session_check_email(time_mode='hourly'):
    log_file = "edx.scripts.ilt_virtual_session_check"
    ilt_virtual_session_log = logging.getLogger(log_file)
    summaries = XModuleUserStateSummaryField.objects.filter(field_name='enrolled_users')
    student_email_info_dict = {}
    stripped_site_name = configuration_helpers.get_value(
        'SITE_NAME',
        settings.SITE_NAME
    )
    if not settings.FEATURES.get('ENABLE_ILT_VIRTUAL_SESSION_REMINDER', False):
        ilt_virtual_session_log.info("ILT virtual session reminder is not enabled.")
        return
    for s in summaries:
        try:
            usage_id = s.usage_id
            ilt_block = modulestore().get_item(usage_id)
            sessions_summary = XModuleUserStateSummaryField.objects.get(field_name="sessions", usage_id=usage_id)
            sessions_info = json.loads(sessions_summary.value)
            enrolled_user_info = json.loads(s.value)
            for session_id, users in enrolled_user_info.items():
                session = sessions_info[session_id]
                location = session.get("location", "")
                session_timezone = tz(session.get("timezone", "UTC"))
                if not is_str_url(location):
                    continue
                start_time = session_timezone.localize(decode_datetime(session['start_at']))
                end_time = session_timezone.localize(decode_datetime(session['end_at']))
                now_time = datetime.now(tz=session_timezone)
                send_email = False
                if time_mode == 'daily':
                    time_diff = start_time.date() - now_time.date()
                    if time_diff.days == 1:
                        send_email = True
                elif time_mode == 'hourly':
                    # now_time - timedelta(0, 60) to avoid that 9:00:00 - 8:00:05(exact time now) < 1 (hour)
                    time_diff = start_time - (now_time - timedelta(0, 60))
                    if time_diff.total_seconds() // 3600 == 1:
                        send_email = True
                if send_email:
                    for user_id, v in users.items():
                        user = User.objects.get(id=user_id)
                        email = user.email
                        if email and email not in student_email_info_dict.keys():
                            course_id = ilt_block.course_id
                            section_id = ilt_block.get_parent().parent.block_id
                            chapter_id = ilt_block.get_parent().get_parent().parent.block_id
                            unit_url = u'{proto}://{site}{path}'.format(
                                proto="https",
                                site=stripped_site_name,
                                path=reverse('courseware_section', args=[unicode(course_id), chapter_id, section_id])
                            )
                            user_name = user.username
                            if user.first_name and user.last_name:
                                user_name = "{} {}".format(user.first_name, user.last_name)
                            message_type = "ilt_virtual_session_{}_reminder".format(time_mode)
                            start_hour_time = "{h}:{min}".format(h=start_time.hour, min=start_time.minute)
                            end_hour_time = "{h}:{min}".format(h=end_time.hour, min=end_time.minute)
                            email_params = dict(
                                user_name=user_name,
                                start_date=str(start_time.date()),
                                start_hour=start_hour_time,
                                end_date=str(end_time.date()),
                                end_hour=end_hour_time,
                                timezone=session.get("timezone", "UTC"),
                                duration_time=session.get("duration", ""),
                                location=session.get("location", ""),
                                unit_url=unit_url,
                                message=message_type,
                                time_mode=time_mode,
                                usage_id=usage_id,
                                site_name=None,
                            )
                            student_email_info_dict[email] = email_params
        except ItemNotFoundError:
            ilt_virtual_session_log.error("ILT block: {usage_id} does not exist.".format(usage_id=usage_id))
    for email, params in student_email_info_dict.items():
        student = User.objects.get(email=email)
        ilt_virtual_session_log.info("Sending ILT virtual session {time_mode} email to {user_email} (ILT block: {usage_id}, begins on {start_date} at {start_hour} {timezone})".format(
            time_mode=params['time_mode'],
            user_email=email,
            usage_id=params['usage_id'],
            start_date=params['start_date'],
            start_hour=params['start_hour'],
            timezone=params['timezone']
        ))
        send_mail_to_student(email, param_dict=params, language=get_user_email_language(student))


# course reminder
class CourseReminder():

    TIME_NOW = timezone.now()

    def set_time(self, timez):
        """
        for testing
        """
        self.TIME_NOW = timez

    def course_filter(self, course_id):
        descriptor = modulestore().get_course(course_id)
        if descriptor:
            return len(descriptor.reminder_info) > 0 or descriptor.periodic_reminder_day
        return False

    def get_course_with_reminders(self):
        """
        get all the courses' ID that have course email reminders
        """

        # filter the course that not end yet or doesn't have end date
        overviews = CourseOverview.objects.all().filter(Q(end__gte=self.TIME_NOW) | Q(end=None))
        course_ids = [c.id for c in overviews if self.course_filter(c.id) and c.has_started()]
        return course_ids

    def get_course_enrollment(self):
        """
        return a dict including unfinished course_enrollment
        and finished course_enrollment
        """
        unfinished = CourseEnrollment.objects.filter(
            course_id__in=self.get_course_with_reminders(),
            is_active=True,
            completed__isnull=True,
            user__is_active=True
        ).select_related('user')

        finished = CourseEnrollment.objects.filter(
            is_active=True,
            completed__isnull=False,
            user__is_active=True
        ).select_related('user')
        return {
            "unfinished": unfinished,
            "finished": finished
        }

    def course_re_enroll(self, course_enrollment):
        """
        re-enroll a student in the course, reset the enrollment date and completed day
        and delete the student state
        """
        course_enrollment.created = timezone.now()
        course_enrollment.completed = None
        course_enrollment.gradebook_edit = None
        course_enrollment.save()
        student_modules = StudentModule.objects.filter(
            course_id=course_enrollment.course_id,
            student=course_enrollment.user
        )
        student_modules.delete()
        cert = GeneratedCertificate.objects.filter(user=course_enrollment.user, course_id=course_enrollment.course_id)
        if cert.exists():
            cert.delete()

        if PersistentGradesEnabledFlag(course_enrollment.course_id):
            try:
                grade = PersistentCourseGrade.read(course_enrollment.user_id, course_enrollment.course_id)
                grade.delete()
                reminder_log.info("reset course grade for user: {user_name}, course_id: {course_id}".format(
                    user_name=course_enrollment.user.username,
                    course_id=course_enrollment.course_id
                ))
            except Exception as e:
                reminder_log.error("failed to reset course grade for user: {user_name}, course_id: {course_id}, "
                             "reason: {reason}".format(user_name=course_enrollment.user.username,
                                                       course_id=course_enrollment.course_id,
                                                       reason=e
                                                       ))

            try:
                progress = PersistentCourseProgress.read(course_enrollment.user_id, course_enrollment.course_id)
                progress.percent_progress = 0
                progress.save()
                reminder_log.info("reset course progress for user: {user_name}, course_id: {course_id}".format(
                    user_name=course_enrollment.user.username,
                    course_id=course_enrollment.course_id
                ))
            except Exception as e:
                reminder_log.error("failed to reset course progress for user: {user_name}, course_id: {course_id}, "
                             "reason: {reason}".format(user_name=course_enrollment.user.username,
                                                       course_id=course_enrollment.course_id,
                                                       reason=e
                                                       ))

            try:
                completions = BlockCompletion.user_course_completion_queryset(
                    course_enrollment.user, course_enrollment.course_id
                )
                completions.update(completion=0)
                reminder_log.info("reset course page completions for user: {user_name}, course_id: {course_id}".format(
                    user_name=course_enrollment.user.username,
                    course_id=course_enrollment.course_id
                ))
            except Exception as e:
                reminder_log.error("failed to reset course page completions for user: {user_name}, course_id: {course_id}, "
                             "reason: {reason}".format(user_name=course_enrollment.user.username,
                                                       course_id=course_enrollment.course_id,
                                                       reason=e
                                                       ))

            try:
                subsection_grades = PersistentSubsectionGrade.bulk_read_grades(
                    course_enrollment.user_id, course_enrollment.course_id
                )
                for i in subsection_grades:
                    i.earned_all = 0
                    i.earned_graded = 0
                    i.first_attempted = None
                    i.save()
                    try:
                        override = PersistentSubsectionGradeOverride.objects.get(grade=i)
                        override.delete()
                    except PersistentSubsectionGradeOverride.DoesNotExist:
                        pass

                reminder_log.info("reset course subsection grade for user: {user_name}, course_id: {course_id}".format(
                    user_name=course_enrollment.user.username,
                    course_id=course_enrollment.course_id
                ))
            except Exception as e:
                reminder_log.error("failed to reset course subsection grade for user: {user_name}, course_id: {course_id}, "
                             "reason: {reason}".format(user_name=course_enrollment.user.username,
                                                       course_id=course_enrollment.course_id,
                                                       reason=e
                                                       ))

    @transaction.atomic
    def send_re_enroll_email(self, course_enrollment):
        """
        send email to student who is automatically re-enrolled in the course
        """
        descriptor = modulestore().get_course(course_enrollment.course_id)

        # in case course does not exist any more
        if not descriptor:
            return
        re_enroll_time = descriptor.course_re_enroll_time

        # if the course doesn't have a automatically re-enroll time, just pass
        if not re_enroll_time:
            pass
        else:
            print(course_enrollment.id)
            time_unit = descriptor.re_enroll_time_unit or 'month'
            completed = course_enrollment.completed
            r = relativedelta.relativedelta(self.TIME_NOW, completed)
            sending_mail = False
            if time_unit == 'month' and r.years * 12 + r.months >= re_enroll_time:
                sending_mail = True
            elif time_unit == 'year' and r.years >= re_enroll_time:
                sending_mail = True

            if sending_mail:
                # sending_mail is true means we have to re-enroll the student in the course
                self.course_re_enroll(course_enrollment)
                course = course_enrollment.course_overview
                username = course_enrollment.user.first_name or course_enrollment.user.profile.name \
                           or course_enrollment.user.username
                params = get_email_params(course, True)
                params['finish_days'] = descriptor.course_finish_days
                params['username'] = username
                params['re_enroll_time'] = descriptor.course_re_enroll_time
                params['time_unit'] = time_unit
                params['email_address'] = course_enrollment.user.email
                subject, message = render_message_to_string(
                    'emails/course_re_enroll_email_subject.txt',
                    'emails/course_re_enroll_email_message.txt',
                    params,
                    language=get_user_email_language(course_enrollment.user)
                )
                subject = subject.strip('\n')
                try:
                    send_mail(subject, message, settings.CONTACT_EMAIL, [course_enrollment.user.email],
                              fail_silently=False)
                    reminder_log.info("send re_enroll_email to username: {username}, id: {user_id}, "
                                "email: {email}, course_id: {course_id}".format(
                        username=course_enrollment.user.username,
                        user_id=course_enrollment.user.id,
                        email=course_enrollment.user.email,
                        course_id=course_enrollment.course_id
                    ))
                except Exception:
                    reminder_log.exception(Exception)

    def send_reminder_email(self, course_enrollment):
        """
        send reminder email to student, to reminder him/her the deadline of the course
        """
        descriptor = modulestore().get_course(course_enrollment.course_id)

        # in case course does not exist any more
        if not descriptor:
            return
        finish_days = descriptor.course_finish_days

        # if the course is required to finish within certain days, we check the reminder info,
        # otherwise do nothing
        if not finish_days:
            return

        created = course_enrollment.created
        delta = self.TIME_NOW - created
        send = False

        if descriptor.periodic_reminder_day:
            if delta.days > 0 and delta.days % descriptor.periodic_reminder_day == 0:
                send = True
        elif delta.days in descriptor.reminder_info:
            send = True

        if send:
            if delta.days > finish_days:
                overdue = True
                days_left = delta.days - finish_days
            else:
                overdue = False
                days_left = finish_days - delta.days
            time_unit = descriptor.re_enroll_time_unit or 'month'
            course = course_enrollment.course_overview
            username = course_enrollment.user.first_name or course_enrollment.user.profile.name \
                       or course_enrollment.user.username
            params = get_email_params(course, True)
            params['username'] = username
            params['overdue'] = overdue
            params['days_left'] = days_left
            params['finish_days'] = finish_days
            params['re_enroll_time'] = descriptor.course_re_enroll_time
            params['time_unit'] = time_unit
            params['email_address'] = course_enrollment.user.email
            subject, message = render_message_to_string(
                'emails/course_reminder_email_subject.txt',
                'emails/course_reminder_email_message.txt',
                params,
                language=get_user_email_language(course_enrollment.user)
            )
            subject = subject.strip('\n')
            try:
                send_mail(subject, message, settings.CONTACT_EMAIL, [course_enrollment.user.email], fail_silently=False)
                reminder_log.info("send reminder_email to username: {username}, id: {user_id}, "
                            "email: {email}, course_id: {course_id}".format(
                    username=course_enrollment.user.username,
                    user_id=course_enrollment.user.id,
                    email=course_enrollment.user.email,
                    course_id=course_enrollment.course_id
                ))
            except Exception:
                reminder_log.exception(Exception)

    def process_email(self):
        """
        send email to students
        """
        course_enrollment_all = self.get_course_enrollment()

        for enrollment in course_enrollment_all['finished']:
            try:
                self.send_re_enroll_email(enrollment)
            except Exception as e:
                reminder_log.info("course re-enroll failed for user: {user_id}, course_id: {course_id}".format(
                    user_id=enrollment.user_id,
                    course_id=enrollment.course_id
                ))
        for enrollment in course_enrollment_all['unfinished']:
            self.send_reminder_email(enrollment)


@require_POST
def batch_completion(request, course_id):
    course_key = CourseKey.from_string(course_id)
    keys = json.loads(request.body)['blocks']
    # exclude unexpected problem blocks
    blocks_to_complete = [(UsageKey.from_string(i), 1.0) for i in keys if "problem" not in i]

    if blocks_to_complete:
        signals.post_save.disconnect(receiver=recalculate_course_completion_percentage, sender=BlockCompletion)
        BlockCompletion.objects.submit_batch_completion(
            request.user, course_key, blocks_to_complete
        )
        course_progress = CourseGradeFactory().update_course_completion_percentage(course_key, request.user)
        signals.post_save.connect(receiver=recalculate_course_completion_percentage, sender=BlockCompletion)
        return JsonResponse({'progress': course_progress}, status=200)
    else:
        return JsonResponse(status=200)
