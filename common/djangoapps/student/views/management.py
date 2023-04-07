"""
Student Views
"""

import csv
import datetime
import json
import logging
import sys
import uuid
from collections import namedtuple

import analytics
import dogstats_wrapper as dog_stats_api
import third_party_auth
import track.views
import warnings
from bulk_email.models import Optout
from course_modes.models import CourseMode
from courseware.courses import get_courses, sort_by_announcement, sort_by_start_date, get_course_by_id
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as django_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import password_reset_confirm, password_reset_complete
from django.core.validators import ValidationError, validate_email
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import Signal, receiver
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect
from django.template.context_processors import csrf
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.encoding import force_bytes, force_text, DjangoUnicodeDecodeError
from django.utils.html import strip_tags
from django.utils.http import base36_to_int, urlsafe_base64_encode, int_to_base36
from django.utils.translation import get_language
from django.utils.translation import ugettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from edxmako.shortcuts import render_to_response, render_to_string
from entitlements.models import CourseEntitlement
from eventtracking import tracker
from ipware.ip import get_ip
# Note that this lives in LMS, so this dependency should be refactored.
from notification_prefs.views import enable_notifications
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from pytz import UTC
from requests import HTTPError
from six import text_type, iteritems
from social_core.exceptions import AuthAlreadyAssociated, AuthException
from social_django import utils as social_utils
from student.cookies import set_logged_in_cookies
from student.forms import (
    AccountCreationForm,
    PasswordResetFormNoActive,
    get_registration_extension_form,
    AdminPanelAccountCreation,
    PasswordCreateResetFormNoActive,
)
from student.helpers import (
    DISABLE_UNENROLL_CERT_STATES,
    AccountValidationError,
    auth_pipeline_urls,
    authenticate_new_user,
    cert_info,
    create_or_set_user_attribute_created_on_site,
    destroy_oauth_tokens,
    do_create_account,
    generate_activation_email_context,
    get_next_url_for_login_page,
)
from student.models import (
    PasswordHistory,
    PendingEmailChange,
    RegistrationCookieConfiguration,
    UserAttribute,
    UserSignupSource,
    UserStanding,
    create_comments_service_user,
    email_exists_or_retired,
    ALLOWEDTOENROLL_TO_ENROLLED,
    ALLOWEDTOENROLL_TO_UNENROLLED,
    DEFAULT_TRANSITION_STATE,
    ENROLLED_TO_ENROLLED,
    ENROLLED_TO_UNENROLLED,
    UNENROLLED_TO_ALLOWEDTOENROLL,
    UNENROLLED_TO_ENROLLED,
    UNENROLLED_TO_UNENROLLED,
    CourseEnrollment,
    ManualEnrollmentAudit,
    Registration,
    UserProfile,
    is_email_retired,
    is_username_retired,
)
from student.signals import REFUND_ORDER
from student.tasks import send_activation_email
from student.text_me_the_app import TextMeTheAppFragmentView
from third_party_auth import pipeline, provider
from third_party_auth.saml import SAP_SUCCESSFACTORS_SAML_KEY
from util.bad_request_rate_limiter import BadRequestRateLimiter
from util.db import outer_atomic
from util.email_utils import send_mail_with_alias as send_mail
from util.json_request import JsonResponse
from util.password_policy_validators import validate_password
from xmodule.modulestore.django import modulestore

import openedx.core.djangoapps.external_auth.views
from common.djangoapps.util.views import require_global_staff
from lms.djangoapps.instructor.enrollment import (
    enroll_email,
    enroll_user,
    get_email_params,
    get_email_params_for_program,
    get_user_email_language,
    unenroll_email,
    unenroll_user,
    program_enroll_email,
    program_unenroll_email,
)
from lms.djangoapps.instructor.views.api import (
    LT_CSV,
    csv_student_field_validation,
    lt_create_user_and_user_profile,
    require_post_params,
    _split_input_list,
    _get_boolean_param,
    _PartialUnenrollException,
    _register_and_enroll_students_precheck,
    _batch_update_student,
    _send_welcoming_email,
)
from lms.djangoapps.instructor.views.tools import get_student_from_identifier
from lms.djangoapps.program_enrollments.api import fetch_program_enrollments, write_program_enrollment, \
    write_program_courses_enrollments
from lms.djangoapps.program_enrollments.constants import ProgramEnrollmentStatuses, ProgramCourseEnrollmentStatuses
from lms.djangoapps.program_enrollments.models import ProgramEnrollment
from lms.djangoapps.program_enrollments.persistance.programs import PartialProgram
from openedx.core.djangoapps import monitoring_utils
from openedx.core.djangoapps.catalog.utils import get_programs_with_type
from openedx.core.djangoapps.embargo import api as embargo_api
from openedx.core.djangoapps.external_auth.login_and_register import register as external_auth_register
from openedx.core.djangoapps.lang_pref import LANGUAGE_KEY
from openedx.core.djangoapps.programs.models import ProgramsApiConfig
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.core.djangoapps.theming import helpers as theming_helpers
from openedx.core.djangoapps.user_api import accounts as accounts_settings
from openedx.core.djangoapps.user_api.accounts.utils import generate_password
from openedx.core.djangoapps.user_api.config.waffle import PREVENT_AUTH_USER_WRITES, SYSTEM_MAINTENANCE_MSG, waffle
from openedx.core.djangoapps.user_api.models import UserRetirementRequest
from openedx.core.djangoapps.user_api.preferences import api as preferences_api
from openedx.core.djangolib.markup import HTML, Text
from .admin_panel import get_date_format

log = logging.getLogger("edx.student")

AUDIT_LOG = logging.getLogger("audit")
ReverifyInfo = namedtuple(
    'ReverifyInfo',
    'course_id course_name course_number date status display'
)
SETTING_CHANGE_INITIATED = 'edx.user.settings.change_initiated'
# Used as the name of the user attribute for tracking affiliate registrations
REGISTRATION_AFFILIATE_ID = 'registration_affiliate_id'
REGISTRATION_UTM_PARAMETERS = {
    'utm_source': 'registration_utm_source',
    'utm_medium': 'registration_utm_medium',
    'utm_campaign': 'registration_utm_campaign',
    'utm_term': 'registration_utm_term',
    'utm_content': 'registration_utm_content',
}
REGISTRATION_UTM_CREATED_AT = 'registration_utm_created_at'
# used to announce a registration
REGISTER_USER = Signal(providing_args=["user", "registration"])
FULL_USER_PROFILE_FIELDS = [
    'name',
    'service_id',
    'language',
    'location',
    'year_of_birth',
    'gender',
    'level_of_education',
    'mailing_address',
    'city',
    'country',
    'goals',
    'bio',
    'org',
    'lt_custom_country',
    'lt_area',
    'lt_sub_area',
    'lt_address',
    'lt_address_2',
    'lt_phone_number',
    'lt_gdpr',
    'lt_company',
    'lt_employee_id',
    'lt_hire_date',
    'lt_level',
    'lt_job_code',
    'lt_job_description',
    'lt_department',
    'lt_supervisor',
    'lt_learning_group',
    'lt_exempt_status',
    'lt_comments',
    'lt_ilt_supervisor'
]


def csrf_token(context):
    """
    A csrf token that can be included in a form.
    """
    token = context.get('csrf_token', '')
    if token == 'NOTPROVIDED':
        return ''
    return (u'<div style="display:none"><input type="hidden"'
            ' name="csrfmiddlewaretoken" value="{}" /></div>'.format(token))


# NOTE: This view is not linked to directly--it is called from
# branding/views.py:index(), which is cached for anonymous users.
# This means that it should always return the same thing for anon
# users. (in particular, no switching based on query params allowed)
def index(request, extra_context=None, user=AnonymousUser()):
    """
    Render the edX main page.

    extra_context is used to allow immediate display of certain modal windows, eg signup,
    as used by external_auth.
    """
    if extra_context is None:
        extra_context = {}

    courses = get_courses(user)

    if configuration_helpers.get_value(
            "ENABLE_COURSE_SORTING_BY_START_DATE",
            settings.FEATURES["ENABLE_COURSE_SORTING_BY_START_DATE"],
    ):
        courses = sort_by_start_date(courses)
    else:
        courses = sort_by_announcement(courses)

    context = {'courses': courses}

    context['homepage_overlay_html'] = configuration_helpers.get_value('homepage_overlay_html')

    # This appears to be an unused context parameter, at least for the master templates...
    context['show_partners'] = configuration_helpers.get_value('show_partners', True)

    # TO DISPLAY A YOUTUBE WELCOME VIDEO
    # 1) Change False to True
    context['show_homepage_promo_video'] = configuration_helpers.get_value('show_homepage_promo_video', False)

    # Maximum number of courses to display on the homepage.
    context['homepage_course_max'] = configuration_helpers.get_value(
        'HOMEPAGE_COURSE_MAX', settings.HOMEPAGE_COURSE_MAX
    )

    # 2) Add your video's YouTube ID (11 chars, eg "123456789xX"), or specify via site configuration
    # Note: This value should be moved into a configuration setting and plumbed-through to the
    # context via the site configuration workflow, versus living here
    youtube_video_id = configuration_helpers.get_value('homepage_promo_video_youtube_id', "your-youtube-id")
    context['homepage_promo_video_youtube_id'] = youtube_video_id

    # allow for theme override of the courses list
    context['courses_list'] = theming_helpers.get_template_path('courses_list.html')

    # Insert additional context for use in the template
    context.update(extra_context)

    # Add marketable programs to the context.
    context['programs_list'] = get_programs_with_type(request.site, include_hidden=False)

    return render_to_response('index.html', context)


@ensure_csrf_cookie
def register_user(request, extra_context=None):
    """
    Deprecated. To be replaced by :class:`student_account.views.login_and_registration_form`.
    """
    # Determine the URL to redirect to following login:
    redirect_to = get_next_url_for_login_page(request)
    if request.user.is_authenticated:
        return redirect(redirect_to)

    external_auth_response = external_auth_register(request)
    if external_auth_response is not None:
        return external_auth_response

    context = {
        'login_redirect_url': redirect_to,  # This gets added to the query string of the "Sign In" button in the header
        'email': '',
        'name': '',
        'running_pipeline': None,
        'pipeline_urls': auth_pipeline_urls(pipeline.AUTH_ENTRY_REGISTER, redirect_url=redirect_to),
        'platform_name': configuration_helpers.get_value(
            'PLATFORM_NAME',
            settings.PLATFORM_NAME
        ),
        'selected_provider': '',
        'username': '',
    }

    if extra_context is not None:
        context.update(extra_context)

    if context.get("extauth_domain", '').startswith(
            openedx.core.djangoapps.external_auth.views.SHIBBOLETH_DOMAIN_PREFIX
    ):
        return render_to_response('register-shib.html', context)

    # If third-party auth is enabled, prepopulate the form with data from the
    # selected provider.
    if third_party_auth.is_enabled() and pipeline.running(request):
        running_pipeline = pipeline.get(request)
        current_provider = provider.Registry.get_from_pipeline(running_pipeline)
        if current_provider is not None:
            overrides = current_provider.get_register_form_data(running_pipeline.get('kwargs'))
            overrides['running_pipeline'] = running_pipeline
            overrides['selected_provider'] = current_provider.name
            context.update(overrides)

    return render_to_response('register.html', context)


def compose_and_send_activation_email(user, profile, user_registration=None):
    """
    Construct all the required params and send the activation email
    through celery task

    Arguments:
        user: current logged-in user
        profile: profile object of the current logged-in user
        user_registration: registration of the current logged-in user
    """
    dest_addr = user.email
    if user_registration is None:
        user_registration = Registration.objects.get(user=user)
    context = generate_activation_email_context(user, user_registration)
    subject = render_to_string('emails/activation_email_subject.txt', context)
    # Email subject *must not* contain newlines
    subject = ''.join(subject.splitlines())
    message_for_activation = render_to_string('emails/activation_email.txt', context)

    # for test
    if 'pytest' in sys.modules:
        html_message = None
    else:
        html_message = render_to_string('emails/activation_html_email.txt', context)
    from_alias = configuration_helpers.get_value('email_from_alias', settings.DEFAULT_FROM_EMAIL_ALIAS)
    from_address = configuration_helpers.get_value('email_from_address', settings.DEFAULT_FROM_EMAIL)
    from_address = configuration_helpers.get_value('ACTIVATION_EMAIL_FROM_ADDRESS', from_address)
    from_address = "{0} <{1}>".format(from_alias, from_address)
    if settings.FEATURES.get('REROUTE_ACTIVATION_EMAIL'):
        dest_addr = settings.FEATURES['REROUTE_ACTIVATION_EMAIL']
        message_for_activation = ("Activation for %s (%s): %s\n" % (user, user.email, profile.name) +
                                  '-' * 80 + '\n\n' + message_for_activation)
    send_activation_email.delay(subject, message_for_activation, from_address, dest_addr, html_message)


@login_required
def course_run_refund_status(request, course_id):
    """
    Get Refundable status for a course.

    Arguments:
        request: The request object.
        course_id (str): The unique identifier for the course.

    Returns:
        Json response.

    """

    try:
        course_key = CourseKey.from_string(course_id)
        course_enrollment = CourseEnrollment.get_enrollment(request.user, course_key)

    except InvalidKeyError:
        logging.exception("The course key used to get refund status caused InvalidKeyError during look up.")

        return JsonResponse({'course_refundable_status': ''}, status=406)

    refundable_status = course_enrollment.refundable()
    logging.info("Course refund status for course {0} is {1}".format(course_id, refundable_status))

    return JsonResponse({'course_refundable_status': refundable_status}, status=200)


def _update_email_opt_in(request, org):
    """
    Helper function used to hit the profile API if email opt-in is enabled.
    """

    email_opt_in = request.POST.get('email_opt_in')
    if email_opt_in is not None:
        email_opt_in_boolean = email_opt_in == 'true'
        preferences_api.update_email_opt_in(request.user, org, email_opt_in_boolean)


@transaction.non_atomic_requests
@require_POST
@outer_atomic(read_committed=True)
def change_enrollment(request, check_access=True):
    """
    Modify the enrollment status for the logged-in user.

    TODO: This is lms specific and does not belong in common code.

    The request parameter must be a POST request (other methods return 405)
    that specifies course_id and enrollment_action parameters. If course_id or
    enrollment_action is not specified, if course_id is not valid, if
    enrollment_action is something other than "enroll" or "unenroll", if
    enrollment_action is "enroll" and enrollment is closed for the course, or
    if enrollment_action is "unenroll" and the user is not enrolled in the
    course, a 400 error will be returned. If the user is not logged in, 403
    will be returned; it is important that only this case return 403 so the
    front end can redirect the user to a registration or login page when this
    happens. This function should only be called from an AJAX request, so
    the error messages in the responses should never actually be user-visible.

    Args:
        request (`Request`): The Django request object

    Keyword Args:
        check_access (boolean): If True, we check that an accessible course actually
            exists for the given course_key before we enroll the student.
            The default is set to False to avoid breaking legacy code or
            code with non-standard flows (ex. beta tester invitations), but
            for any standard enrollment flow you probably want this to be True.

    Returns:
        Response

    """
    # Get the user
    user = request.user

    # Ensure the user is authenticated
    if not user.is_authenticated:
        return HttpResponseForbidden()

    # Ensure we received a course_id
    action = request.POST.get("enrollment_action")
    if 'course_id' not in request.POST:
        return HttpResponseBadRequest(_("Course id not specified"))

    try:
        course_id = CourseKey.from_string(request.POST.get("course_id"))
    except InvalidKeyError:
        log.warning(
            u"User %s tried to %s with invalid course id: %s",
            user.username,
            action,
            request.POST.get("course_id"),
        )
        return HttpResponseBadRequest(_("Invalid course id"))

    # Allow us to monitor performance of this transaction on a per-course basis since we often roll-out features
    # on a per-course basis.
    monitoring_utils.set_custom_metric('course_id', text_type(course_id))

    if action == "enroll":
        # Make sure the course exists
        # We don't do this check on unenroll, or a bad course id can't be unenrolled from
        if not modulestore().has_course(course_id):
            log.warning(
                u"User %s tried to enroll in non-existent course %s",
                user.username,
                course_id
            )
            return HttpResponseBadRequest(_("Course id is invalid"))

        # Record the user's email opt-in preference
        if settings.FEATURES.get('ENABLE_MKTG_EMAIL_OPT_IN'):
            _update_email_opt_in(request, course_id.org)

        available_modes = CourseMode.modes_for_course_dict(course_id)

        # Check whether the user is blocked from enrolling in this course
        # This can occur if the user's IP is on a global blacklist
        # or if the user is enrolling in a country in which the course
        # is not available.
        redirect_url = embargo_api.redirect_if_blocked(
            course_id, user=user, ip_address=get_ip(request),
            url=request.path
        )
        if redirect_url:
            return HttpResponse(redirect_url)

        if CourseEntitlement.check_for_existing_entitlement_and_enroll(user=user, course_run_key=course_id):
            return HttpResponse(reverse('courseware', args=[unicode(course_id)]))

        # Check that auto enrollment is allowed for this course
        # (= the course is NOT behind a paywall)
        if CourseMode.can_auto_enroll(course_id):
            # Enroll the user using the default mode (audit)
            # We're assuming that users of the course enrollment table
            # will NOT try to look up the course enrollment model
            # by its slug.  If they do, it's possible (based on the state of the database)
            # for no such model to exist, even though we've set the enrollment type
            # to "audit".
            try:
                enroll_mode = CourseMode.auto_enroll_mode(course_id, available_modes)
                if enroll_mode:
                    CourseEnrollment.enroll(user, course_id, check_access=check_access, mode=enroll_mode)
            except Exception:  # pylint: disable=broad-except
                return HttpResponseBadRequest(_("Could not enroll"))

        # If we have more than one course mode or professional ed is enabled,
        # then send the user to the choose your track page.
        # (In the case of no-id-professional/professional ed, this will redirect to a page that
        # funnels users directly into the verification / payment flow)
        if CourseMode.has_verified_mode(available_modes) or CourseMode.has_professional_mode(available_modes):
            return HttpResponse(
                reverse("course_modes_choose", kwargs={'course_id': text_type(course_id)})
            )

        # Otherwise, there is only one mode available (the default)
        return HttpResponse()
    elif action == "unenroll":
        if ProgramsApiConfig.is_student_dashboard_enabled():
            # Activate checking while program is enabled
            _filter = {
                'courses.course_runs.key': str(course_id)
            }
            _programs_uuids = [
                program.to_dict()['uuid']
                for program in PartialProgram.query(
                    _filter,
                    loading_policy=PartialProgram.POLICY_LOAD_LP_ONLY
                )
            ]
            user_enrolled_programs_count = ProgramEnrollment.objects.filter(
                program_uuid__in=_programs_uuids,
                user_id=user.id,
                status=ProgramEnrollmentStatuses.ENROLLED
            ).count()
            if user_enrolled_programs_count > 0:
                return HttpResponseBadRequest(
                    _('The course ({}) are needed to unenroll from program(s) first.'.format(str(course_id)))
                )

        enrollment = CourseEnrollment.get_enrollment(user, course_id)
        if not enrollment:
            return HttpResponseBadRequest(_("You are not enrolled in this course"))

        certificate_info = cert_info(user, enrollment.course_overview)
        if certificate_info.get('status') in DISABLE_UNENROLL_CERT_STATES:
            return HttpResponseBadRequest(_("Your certificate prevents you from unenrolling from this course"))

        CourseEnrollment.unenroll(user, course_id)
        REFUND_ORDER.send(sender=None, course_enrollment=enrollment)
        return HttpResponse()
    else:
        return HttpResponseBadRequest(_("Enrollment action is invalid"))


@require_GET
@login_required
@ensure_csrf_cookie
def manage_user_standing(request):
    """
    Renders the view used to manage user standing. Also displays a table
    of user accounts that have been disabled and who disabled them.
    """
    if not request.user.is_staff:
        raise Http404
    all_disabled_accounts = UserStanding.objects.filter(
        account_status=UserStanding.ACCOUNT_DISABLED
    )

    all_disabled_users = [standing.user for standing in all_disabled_accounts]

    headers = ['username', 'account_changed_by']
    rows = []
    for user in all_disabled_users:
        row = [user.username, user.standing.changed_by]
        rows.append(row)

    context = {'headers': headers, 'rows': rows}

    return render_to_response("manage_user_standing.html", context)


@require_POST
@login_required
@ensure_csrf_cookie
def disable_account_ajax(request):
    """
    Ajax call to change user standing. Endpoint of the form
    in manage_user_standing.html
    """
    if not request.user.is_staff:
        raise Http404
    username = request.POST.get('username')
    context = {}
    if username is None or username.strip() == '':
        context['message'] = _('Please enter a username')
        return JsonResponse(context, status=400)

    account_action = request.POST.get('account_action')
    if account_action is None:
        context['message'] = _('Please choose an option')
        return JsonResponse(context, status=400)

    username = username.strip()
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        context['message'] = _("User with username {} does not exist").format(username)
        return JsonResponse(context, status=400)
    else:
        user_account, _success = UserStanding.objects.get_or_create(
            user=user, defaults={'changed_by': request.user},
        )
        if account_action == 'disable':
            user_account.account_status = UserStanding.ACCOUNT_DISABLED
            context['message'] = _("Successfully disabled {}'s account").format(username)
            log.info(u"%s disabled %s's account", request.user, username)
        elif account_action == 'reenable':
            user_account.account_status = UserStanding.ACCOUNT_ENABLED
            context['message'] = _("Successfully reenabled {}'s account").format(username)
            log.info(u"%s reenabled %s's account", request.user, username)
        else:
            context['message'] = _("Unexpected account status")
            return JsonResponse(context, status=400)
        user_account.changed_by = request.user
        user_account.standing_last_changed_at = datetime.datetime.now(UTC)
        user_account.save()

    return JsonResponse(context)


@login_required
@ensure_csrf_cookie
def change_setting(request):
    """
    JSON call to change a profile setting: Right now, location
    """
    # TODO (vshnayder): location is no longer used
    u_prof = UserProfile.objects.get(user=request.user)  # request.user.profile_cache
    if 'location' in request.POST:
        u_prof.location = request.POST['location']
    u_prof.save()

    return JsonResponse({
        "success": True,
        "location": u_prof.location,
    })


@receiver(post_save, sender=User)
def user_signup_handler(sender, **kwargs):  # pylint: disable=unused-argument
    """
    Handler that saves the user Signup Source when the user is created
    """
    if 'created' in kwargs and kwargs['created']:
        site = configuration_helpers.get_value('SITE_NAME')
        if site:
            user_signup_source = UserSignupSource(user=kwargs['instance'], site=site)
            user_signup_source.save()
            log.info(u'user {} originated from a white labeled "Microsite"'.format(kwargs['instance'].id))


@transaction.non_atomic_requests
def create_account_with_params(request, params):
    """
    Given a request and a dict of parameters (which may or may not have come
    from the request), create an account for the requesting user, including
    creating a comments service user object and sending an activation email.
    This also takes external/third-party auth into account, updates that as
    necessary, and authenticates the user for the request's session.

    Does not return anything.

    Raises AccountValidationError if an account with the username or email
    specified by params already exists, or ValidationError if any of the given
    parameters is invalid for any other reason.

    Issues with this code:
    * It is non-transactional except where explicitly wrapped in atomic to
      alleviate deadlocks and improve performance. This means failures at
      different places in registration can leave users in inconsistent
      states.
    * Third-party auth passwords are not verified. There is a comment that
      they are unused, but it would be helpful to have a sanity check that
      they are sane.
    * The user-facing text is rather unfriendly (e.g. "Username must be a
      minimum of two characters long" rather than "Please use a username of
      at least two characters").
    * Duplicate email raises a ValidationError (rather than the expected
      AccountValidationError). Duplicate username returns an inconsistent
      user message (i.e. "An account with the Public Username '{username}'
      already exists." rather than "It looks like {username} belongs to an
      existing account. Try again with a different username.") The two checks
      occur at different places in the code; as a result, registering with
      both a duplicate username and email raises only a ValidationError for
      email only.
    """
    # Copy params so we can modify it; we can't just do dict(params) because if
    # params is request.POST, that results in a dict containing lists of values
    params = dict(params.items())

    # allow to define custom set of required/optional/hidden fields via configuration
    extra_fields = configuration_helpers.get_value(
        'REGISTRATION_EXTRA_FIELDS',
        getattr(settings, 'REGISTRATION_EXTRA_FIELDS', {})
    )

    # registration via third party (Google, Facebook) using mobile application
    # doesn't use social auth pipeline (no redirect uri(s) etc involved).
    # In this case all related info (required for account linking)
    # is sent in params.
    # `third_party_auth_credentials_in_api` essentially means 'request
    # is made from mobile application'
    third_party_auth_credentials_in_api = 'provider' in params

    is_third_party_auth_enabled = third_party_auth.is_enabled()
    enforce_password_policy = True
    if is_third_party_auth_enabled and (pipeline.running(request) or third_party_auth_credentials_in_api):
        params["password"] = generate_password()
        enforce_password_policy = False

    # in case user is registering via third party (Google, Facebook) and pipeline has expired, show appropriate
    # error message
    if is_third_party_auth_enabled and ('social_auth_provider' in params and not pipeline.running(request)):
        raise ValidationError(
            {'session_expired': [
                _(u"Registration using {provider} has timed out.").format(
                    provider=params.get('social_auth_provider'))
            ]}
        )

    # if doing signup for an external authorization, then get email, password, name from the eamap
    # don't use the ones from the form, since the user could have hacked those
    # unless originally we didn't get a valid email or name from the external auth
    # TODO: We do not check whether these values meet all necessary criteria, such as email length
    do_external_auth = 'ExternalAuthMap' in request.session
    if do_external_auth:
        eamap = request.session['ExternalAuthMap']
        try:
            validate_email(eamap.external_email)
            params["email"] = eamap.external_email
        except ValidationError:
            pass
        if len(eamap.external_name.strip()) >= accounts_settings.NAME_MIN_LENGTH:
            params["name"] = eamap.external_name
        params["password"] = eamap.internal_password
        log.debug(u'In create_account with external_auth: user = %s, email=%s', params["name"], params["email"])

    extended_profile_fields = configuration_helpers.get_value('extended_profile_fields', [])
    enforce_password_policy = enforce_password_policy and not do_external_auth
    # Can't have terms of service for certain SHIB users, like at Stanford
    tos_required = (
        extra_fields.get('terms_of_service') != 'hidden' or
        extra_fields.get('honor_code') != 'hidden'
    ) and (
        not settings.FEATURES.get("AUTH_USE_SHIB") or
        not settings.FEATURES.get("SHIB_DISABLE_TOS") or
        not do_external_auth or
        not eamap.external_domain.startswith(openedx.core.djangoapps.external_auth.views.SHIBBOLETH_DOMAIN_PREFIX)
    )

    form = AccountCreationForm(
        data=params,
        extra_fields=extra_fields,
        extended_profile_fields=extended_profile_fields,
        enforce_password_policy=enforce_password_policy,
        tos_required=tos_required,
    )
    custom_form = get_registration_extension_form(data=params)

    third_party_provider = None
    running_pipeline = None
    new_user = None

    # Perform operations within a transaction that are critical to account creation
    with outer_atomic(read_committed=True):
        # first, create the account
        (user, profile, registration) = do_create_account(form, custom_form)

        # If a 3rd party auth provider and credentials were provided in the API, link the account with social auth
        # (If the user is using the normal register page, the social auth pipeline does the linking, not this code)

        # Note: this is orthogonal to the 3rd party authentication pipeline that occurs
        # when the account is created via the browser and redirect URLs.

        if is_third_party_auth_enabled and third_party_auth_credentials_in_api:
            backend_name = params['provider']
            request.social_strategy = social_utils.load_strategy(request)
            redirect_uri = reverse('social:complete', args=(backend_name, ))
            request.backend = social_utils.load_backend(request.social_strategy, backend_name, redirect_uri)
            social_access_token = params.get('access_token')
            if not social_access_token:
                raise ValidationError({
                    'access_token': [
                        _("An access_token is required when passing value ({}) for provider.").format(
                            params['provider']
                        )
                    ]
                })
            request.session[pipeline.AUTH_ENTRY_KEY] = pipeline.AUTH_ENTRY_REGISTER_API
            pipeline_user = None
            error_message = ""
            try:
                pipeline_user = request.backend.do_auth(social_access_token, user=user)
            except AuthAlreadyAssociated:
                error_message = _("The provided access_token is already associated with another user.")
            except (HTTPError, AuthException):
                error_message = _("The provided access_token is not valid.")
            if not pipeline_user or not isinstance(pipeline_user, User):
                # Ensure user does not re-enter the pipeline
                request.social_strategy.clean_partial_pipeline(social_access_token)
                raise ValidationError({'access_token': [error_message]})

        # If the user is registering via 3rd party auth, track which provider they use
        if is_third_party_auth_enabled and pipeline.running(request):
            running_pipeline = pipeline.get(request)
            third_party_provider = provider.Registry.get_from_pipeline(running_pipeline)

        new_user = authenticate_new_user(request, user.username, params['password'])
        django_login(request, new_user)
        request.session.set_expiry(0)

        if do_external_auth:
            eamap.user = new_user
            eamap.dtsignup = datetime.datetime.now(UTC)
            eamap.save()
            AUDIT_LOG.info(u"User registered with external_auth %s", new_user.username)
            AUDIT_LOG.info(u'Updated ExternalAuthMap for %s to be %s', new_user.username, eamap)

            if settings.FEATURES.get('BYPASS_ACTIVATION_EMAIL_FOR_EXTAUTH'):
                log.info('bypassing activation email')
                new_user.is_active = True
                new_user.save()
                AUDIT_LOG.info(
                    u"Login activated on extauth account - {0} ({1})".format(new_user.username, new_user.email))

    # Check if system is configured to skip activation email for the current user.
    skip_email = skip_activation_email(
        user, do_external_auth, running_pipeline, third_party_provider,
    )

    if skip_email:
        registration.activate()
    else:
        compose_and_send_activation_email(user, profile, registration)

    # Perform operations that are non-critical parts of account creation
    create_or_set_user_attribute_created_on_site(user, request.site)

    preferences_api.set_user_preference(user, LANGUAGE_KEY, get_language())

    if settings.FEATURES.get('ENABLE_DISCUSSION_EMAIL_DIGEST'):
        try:
            enable_notifications(user)
        except Exception:  # pylint: disable=broad-except
            log.exception("Enable discussion notifications failed for user {id}.".format(id=user.id))

    dog_stats_api.increment("common.student.account_created")

    # Track the user's registration
    if hasattr(settings, 'LMS_SEGMENT_KEY') and settings.LMS_SEGMENT_KEY:
        tracking_context = tracker.get_tracker().resolve_context()
        identity_args = [
            user.id,
            {
                'email': user.email,
                'username': user.username,
                'name': profile.name,
                # Mailchimp requires the age & yearOfBirth to be integers, we send a sane integer default if falsey.
                'age': profile.age or -1,
                'yearOfBirth': profile.year_of_birth or datetime.datetime.now(UTC).year,
                'education': profile.level_of_education_display,
                'address': profile.mailing_address,
                'gender': profile.gender_display,
                'country': text_type(profile.country),
            }
        ]

        if hasattr(settings, 'MAILCHIMP_NEW_USER_LIST_ID'):
            identity_args.append({
                "MailChimp": {
                    "listId": settings.MAILCHIMP_NEW_USER_LIST_ID
                }
            })

        analytics.identify(*identity_args)

        analytics.track(
            user.id,
            "edx.bi.user.account.registered",
            {
                'category': 'conversion',
                'label': params.get('course_id'),
                'provider': third_party_provider.name if third_party_provider else None
            },
            context={
                'ip': tracking_context.get('ip'),
                'Google Analytics': {
                    'clientId': tracking_context.get('client_id')
                }
            }
        )

    # Announce registration
    REGISTER_USER.send(sender=None, user=user, registration=registration)

    create_comments_service_user(user)

    try:
        record_registration_attributions(request, new_user)
    # Don't prevent a user from registering due to attribution errors.
    except Exception:   # pylint: disable=broad-except
        log.exception('Error while attributing cookies to user registration.')

    # TODO: there is no error checking here to see that the user actually logged in successfully,
    # and is not yet an active user.
    if new_user is not None:
        AUDIT_LOG.info(u"Login success on new account creation - {0}".format(new_user.username))

    return new_user


@transaction.non_atomic_requests
def admin_panel_account_creation(request, params):
    """
    Given a request and a dict of parameters (which may or may not have come
    from the request), create an account for the requesting user, including
    creating a comments service user object and sending an activation email.
    This also takes external/third-party auth into account, updates that as
    necessary, and authenticates the user for the request's session.

    Does not return anything.

    Raises AccountValidationError if an account with the username or email
    specified by params already exists, or ValidationError if any of the given
    parameters is invalid for any other reason.

    Issues with this code:
    * It is non-transactional except where explicitly wrapped in atomic to
      alleviate deadlocks and improve performance. This means failures at
      different places in registration can leave users in inconsistent
      states.
    * Third-party auth passwords are not verified. There is a comment that
      they are unused, but it would be helpful to have a sanity check that
      they are sane.
    * The user-facing text is rather unfriendly (e.g. "Username must be a
      minimum of two characters long" rather than "Please use a username of
      at least two characters").
    * Duplicate email raises a ValidationError (rather than the expected
      AccountValidationError). Duplicate username returns an inconsistent
      user message (i.e. "An account with the Public Username '{username}'
      already exists." rather than "It looks like {username} belongs to an
      existing account. Try again with a different username.") The two checks
      occur at different places in the code; as a result, registering with
      both a duplicate username and email raises only a ValidationError for
      email only.
    """
    # Copy params so we can modify it; we can't just do dict(params) because if
    # params is request.POST, that results in a dict containing lists of values
    params = dict(params.items())

    # Can't have terms of service for certain SHIB users, like at Stanford
    registration_fields = configuration_helpers.get_value(
        'REGISTRATION_EXTRA_FIELDS',
        getattr(settings, 'REGISTRATION_EXTRA_FIELDS', {})
    )
    tos_required = (
        registration_fields.get('terms_of_service') != 'hidden' or
        registration_fields.get('honor_code') != 'hidden'
    )

    form = AdminPanelAccountCreation(
        data=params,
        extra_fields={},
        extended_profile_fields=FULL_USER_PROFILE_FIELDS,
        enforce_password_policy=True,
        tos_required=tos_required,
    )

    third_party_provider = None

    # Perform operations within a transaction that are critical to account creation
    with outer_atomic(read_committed=True):
        # first, create the account
        errors = form.errors
        if errors:
            raise ValidationError(errors)
        user = User(
            username=form.cleaned_data["username"],
            email=form.cleaned_data["email"],
            is_active=True,
            first_name=params.get("first_name", ""),
            last_name=params.get("last_name", "")
        )
        user.set_password(form.cleaned_data["password"])
        user.save()

        profile_properties = {key: form.cleaned_data.get(key) for key in FULL_USER_PROFILE_FIELDS}
        if not form.cleaned_data.get("lt_hire_date"):
            profile_properties["lt_hire_date"] = None
        else:
            profile_properties['lt_hire_date'] = datetime.datetime.strptime(
                profile_properties['lt_hire_date'], get_date_format()[0]
            )
        client_service_id = configuration_helpers.get_value('CLIENT_SERVICE_ID', None)
        if client_service_id:
            profile_properties['service_id'] = client_service_id
        profile = UserProfile(
            user=user,
            **profile_properties
        )
        profile.save()
        registration = Registration()
        registration.register(user)
        registration.activate()

    # Perform operations that are non-critical parts of account creation
    create_or_set_user_attribute_created_on_site(user, request.site)
    preferences_api.set_user_preference(user, LANGUAGE_KEY, get_language())

    if settings.FEATURES.get('ENABLE_DISCUSSION_EMAIL_DIGEST'):
        try:
            enable_notifications(user)
        except Exception:  # pylint: disable=broad-except
            log.exception("Enable discussion notifications failed for user {id}.".format(id=user.id))

    dog_stats_api.increment("common.student.account_created")

    # Track the user's registration
    if hasattr(settings, 'LMS_SEGMENT_KEY') and settings.LMS_SEGMENT_KEY:
        tracking_context = tracker.get_tracker().resolve_context()
        identity_args = [
            user.id,
            {
                'email': user.email,
                'username': user.username,
                'name': profile.name,
                # Mailchimp requires the age & yearOfBirth to be integers, we send a sane integer default if falsey.
                'age': profile.age or -1,
                'yearOfBirth': profile.year_of_birth or datetime.datetime.now(UTC).year,
                'education': profile.level_of_education_display,
                'address': profile.mailing_address,
                'gender': profile.gender_display,
                'country': text_type(profile.country),
            }
        ]

        if hasattr(settings, 'MAILCHIMP_NEW_USER_LIST_ID'):
            identity_args.append({
                "MailChimp": {
                    "listId": settings.MAILCHIMP_NEW_USER_LIST_ID
                }
            })

        analytics.identify(*identity_args)

        analytics.track(
            user.id,
            "edx.bi.user.account.registered",
            {
                'category': 'conversion',
                'label': params.get('course_id'),
                'provider': third_party_provider.name if third_party_provider else None
            },
            context={
                'ip': tracking_context.get('ip'),
                'Google Analytics': {
                    'clientId': tracking_context.get('client_id')
                }
            }
        )

    # Announce registration
    REGISTER_USER.send(sender=None, user=user, registration=registration)

    create_comments_service_user(user)

    try:
        record_registration_attributions(request, user)
    # Don't prevent a user from registering due to attribution errors.
    except Exception:   # pylint: disable=broad-except
        log.exception('Error while attributing cookies to user registration.')

    return user


def skip_activation_email(user, do_external_auth, running_pipeline, third_party_provider):
    """
    Return `True` if activation email should be skipped.

    Skip email if we are:
        1. Doing load testing.
        2. Random user generation for other forms of testing.
        3. External auth bypassing activation.
        4. Have the platform configured to not require e-mail activation.
        5. Registering a new user using a trusted third party provider (with skip_email_verification=True)

    Note that this feature is only tested as a flag set one way or
    the other for *new* systems. we need to be careful about
    changing settings on a running system to make sure no users are
    left in an inconsistent state (or doing a migration if they are).

    Arguments:
        user (User): Django User object for the current user.
        do_external_auth (bool): True if external authentication is in progress.
        running_pipeline (dict): Dictionary containing user and pipeline data for third party authentication.
        third_party_provider (ProviderConfig): An instance of third party provider configuration.

    Returns:
        (bool): `True` if account activation email should be skipped, `False` if account activation email should be
            sent.
    """
    sso_pipeline_email = running_pipeline and running_pipeline['kwargs'].get('details', {}).get('email')

    # Email is valid if the SAML assertion email matches the user account email or
    # no email was provided in the SAML assertion. Some IdP's use a callback
    # to retrieve additional user account information (including email) after the
    # initial account creation.
    valid_email = (
        sso_pipeline_email == user.email or (
            sso_pipeline_email is None and
            third_party_provider and
            getattr(third_party_provider, "identity_provider_type", None) == SAP_SUCCESSFACTORS_SAML_KEY
        )
    )

    # log the cases where skip activation email flag is set, but email validity check fails
    if third_party_provider and third_party_provider.skip_email_verification and not valid_email:
        log.info(
            '[skip_email_verification=True][user=%s][pipeline-email=%s][identity_provider=%s][provider_type=%s] '
            'Account activation email sent as user\'s system email differs from SSO email.',
            user.email,
            sso_pipeline_email,
            getattr(third_party_provider, "provider_id", None),
            getattr(third_party_provider, "identity_provider_type", None)
        )

    return (
        settings.FEATURES.get('SKIP_EMAIL_VALIDATION', None) or
        settings.FEATURES.get('AUTOMATIC_AUTH_FOR_TESTING') or
        (settings.FEATURES.get('BYPASS_ACTIVATION_EMAIL_FOR_EXTAUTH') and do_external_auth) or
        (third_party_provider and third_party_provider.skip_email_verification and valid_email)
    )


def record_affiliate_registration_attribution(request, user):
    """
    Attribute this user's registration to the referring affiliate, if
    applicable.
    """
    affiliate_id = request.COOKIES.get(settings.AFFILIATE_COOKIE_NAME)
    if user and affiliate_id:
        UserAttribute.set_user_attribute(user, REGISTRATION_AFFILIATE_ID, affiliate_id)


def record_utm_registration_attribution(request, user):
    """
    Attribute this user's registration to the latest UTM referrer, if
    applicable.
    """
    utm_cookie_name = RegistrationCookieConfiguration.current().utm_cookie_name
    utm_cookie = request.COOKIES.get(utm_cookie_name)
    if user and utm_cookie:
        utm = json.loads(utm_cookie)
        for utm_parameter_name in REGISTRATION_UTM_PARAMETERS:
            utm_parameter = utm.get(utm_parameter_name)
            if utm_parameter:
                UserAttribute.set_user_attribute(
                    user,
                    REGISTRATION_UTM_PARAMETERS.get(utm_parameter_name),
                    utm_parameter
                )
        created_at_unixtime = utm.get('created_at')
        if created_at_unixtime:
            # We divide by 1000 here because the javascript timestamp generated is in milliseconds not seconds.
            # PYTHON: time.time()      => 1475590280.823698
            # JS: new Date().getTime() => 1475590280823
            created_at_datetime = datetime.datetime.fromtimestamp(int(created_at_unixtime) / float(1000), tz=UTC)
            UserAttribute.set_user_attribute(
                user,
                REGISTRATION_UTM_CREATED_AT,
                created_at_datetime
            )


def record_registration_attributions(request, user):
    """
    Attribute this user's registration based on referrer cookies.
    """
    record_affiliate_registration_attribution(request, user)
    record_utm_registration_attribution(request, user)


@csrf_exempt
@transaction.non_atomic_requests
def create_account(request, post_override=None):
    """
    JSON call to create new edX account.
    Used by form in signup_modal.html, which is included into header.html
    """
    # Check if ALLOW_PUBLIC_ACCOUNT_CREATION flag turned off to restrict user account creation
    if not configuration_helpers.get_value(
            'ALLOW_PUBLIC_ACCOUNT_CREATION',
            settings.FEATURES.get('ALLOW_PUBLIC_ACCOUNT_CREATION', True)
    ):
        return HttpResponseForbidden(_("Account creation not allowed."))

    if waffle().is_enabled(PREVENT_AUTH_USER_WRITES):
        return HttpResponseForbidden(SYSTEM_MAINTENANCE_MSG)

    warnings.warn("Please use RegistrationView instead.", DeprecationWarning)

    try:
        user = create_account_with_params(request, post_override or request.POST)
    except AccountValidationError as exc:
        return JsonResponse({'success': False, 'value': text_type(exc), 'field': exc.field}, status=400)
    except ValidationError as exc:
        field, error_list = next(iteritems(exc.message_dict))
        return JsonResponse(
            {
                "success": False,
                "field": field,
                "value": error_list[0],
            },
            status=400
        )

    redirect_url = None  # The AJAX method calling should know the default destination upon success

    # Resume the third-party-auth pipeline if necessary.
    if third_party_auth.is_enabled() and pipeline.running(request):
        running_pipeline = pipeline.get(request)
        redirect_url = pipeline.get_complete_url(running_pipeline['backend'])

    response = JsonResponse({
        'success': True,
        'redirect_url': redirect_url,
    })
    set_logged_in_cookies(request, response, user)
    return response


@ensure_csrf_cookie
def activate_account(request, key):
    """
    When link in activation e-mail is clicked
    """
    # If request is in Studio call the appropriate view
    if theming_helpers.get_project_root_name().lower() == u'cms':
        return activate_account_studio(request, key)

    try:
        registration = Registration.objects.get(activation_key=key)
    except (Registration.DoesNotExist, Registration.MultipleObjectsReturned):
        messages.error(
            request,
            HTML(_(
                '{html_start}Your account could not be activated{html_end}'
                'Something went wrong, please <a href="{support_url}">contact support</a> to resolve this issue.'
            )).format(
                support_url=configuration_helpers.get_value('SUPPORT_SITE_LINK', settings.SUPPORT_SITE_LINK),
                html_start=HTML('<p class="message-title">'),
                html_end=HTML('</p>'),
            ),
            extra_tags='account-activation aa-icon'
        )
    else:
        if registration.user.is_active:
            messages.info(
                request,
                HTML(_('{html_start}This account has already been activated.{html_end}')).format(
                    html_start=HTML('<p class="message-title">'),
                    html_end=HTML('</p>'),
                ),
                extra_tags='account-activation aa-icon',
            )
        elif waffle().is_enabled(PREVENT_AUTH_USER_WRITES):
            messages.error(
                request,
                HTML(u'{html_start}{message}{html_end}').format(
                    message=Text(SYSTEM_MAINTENANCE_MSG),
                    html_start=HTML('<p class="message-title">'),
                    html_end=HTML('</p>'),
                ),
                extra_tags='account-activation aa-icon',
            )
        else:
            registration.activate()
            # Success message for logged in users.
            message = _('{html_start}Success{html_end} You have activated your account.')

            if not request.user.is_authenticated:
                # Success message for logged out users
                message = _(
                    '{html_start}Success! You have activated your account.{html_end}'
                    'You will now receive email updates and alerts from us related to'
                    ' the courses you are enrolled in. Sign In to continue.'
                )

            # Add message for later use.
            messages.success(
                request,
                HTML(message).format(
                    html_start=HTML('<p class="message-title">'),
                    html_end=HTML('</p>'),
                ),
                extra_tags='account-activation aa-icon',
            )

    return redirect('dashboard')


@ensure_csrf_cookie
def activate_account_studio(request, key):
    """
    When link in activation e-mail is clicked and the link belongs to studio.
    """
    try:
        registration = Registration.objects.get(activation_key=key)
    except (Registration.DoesNotExist, Registration.MultipleObjectsReturned):
        return render_to_response(
            "registration/activation_invalid.html",
            {'csrf': csrf(request)['csrf_token']}
        )
    else:
        user_logged_in = request.user.is_authenticated
        already_active = True
        if not registration.user.is_active:
            if waffle().is_enabled(PREVENT_AUTH_USER_WRITES):
                return render_to_response('registration/activation_invalid.html',
                                          {'csrf': csrf(request)['csrf_token']})
            registration.activate()
            already_active = False

        return render_to_response(
            "registration/activation_complete.html",
            {
                'user_logged_in': user_logged_in,
                'already_active': already_active
            }
        )


@csrf_exempt
@require_POST
def password_reset(request):
    """
    Attempts to send a password reset e-mail.
    """
    # Add some rate limiting here by re-using the RateLimitMixin as a helper class
    limiter = BadRequestRateLimiter()
    if limiter.is_rate_limit_exceeded(request):
        AUDIT_LOG.warning("Rate limit exceeded in password_reset")
        return HttpResponseForbidden()

    form = PasswordResetFormNoActive(request.POST)
    if form.is_valid():
        form.save(use_https=request.is_secure(),
                  from_email=configuration_helpers.get_value('email_from_address', settings.DEFAULT_FROM_EMAIL),
                  request=request)
        # When password change is complete, a "edx.user.settings.changed" event will be emitted.
        # But because changing the password is multi-step, we also emit an event here so that we can
        # track where the request was initiated.
        tracker.emit(
            SETTING_CHANGE_INITIATED,
            {
                "setting": "password",
                "old": None,
                "new": None,
                "user_id": request.user.id,
            }
        )
        destroy_oauth_tokens(request.user)
    else:
        # bad user? tick the rate limiter counter
        AUDIT_LOG.info("Bad password_reset user passed in.")
        limiter.tick_bad_request_counter(request)

    return JsonResponse({
        'success': True,
        'value': render_to_string('registration/password_reset_done.html', {}),
    })


def uidb36_to_uidb64(uidb36):
    """
    Needed to support old password reset URLs that use base36-encoded user IDs
    https://github.com/django/django/commit/1184d077893ff1bc947e45b00a4d565f3df81776#diff-c571286052438b2e3190f8db8331a92bR231
    Args:
        uidb36: base36-encoded user ID

    Returns: base64-encoded user ID. Otherwise returns a dummy, invalid ID
    """
    try:
        uidb64 = force_text(urlsafe_base64_encode(force_bytes(base36_to_int(uidb36))))
    except ValueError:
        uidb64 = '1'  # dummy invalid ID (incorrect padding for base64)
    return uidb64


def admin_panel_user_password_reset(request, user_id):
    platform_name = {
        "platform_name": configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME)
    }

    user = User.objects.get(id=user_id)
    uidb36 = int_to_base36(int(user_id))
    uidb64 = uidb36_to_uidb64(uidb36)
    token = default_token_generator.make_token(user)
    post_reset_redirect = reverse("admin_panel_user_edit", kwargs={"user_id": user_id})
    if UserRetirementRequest.has_user_requested_retirement(user):
        # Refuse to reset the password of any user that has requested retirement.
        context = {
            'validlink': True,
            'form': None,
            'title': _('Password reset unsuccessful'),
            'err_msg': _('Error in resetting your password.'),
        }
        context.update(platform_name)
        return TemplateResponse(
            request, 'registration/password_reset_confirm.html', context
        )

    if waffle().is_enabled(PREVENT_AUTH_USER_WRITES):
        context = {
            'validlink': False,
            'form': None,
            'title': _('Password reset unsuccessful'),
            'err_msg': SYSTEM_MAINTENANCE_MSG,
        }
        context.update(platform_name)
        return TemplateResponse(
            request, 'registration/password_reset_confirm.html', context
        )

    if request.method == 'POST':
        password = request.POST['new_password1']

        try:
            validate_password(password, user=user)
        except ValidationError as err:
            # We have a password reset attempt which violates some security
            # policy, or any other validation. Use the existing Django template to communicate that
            # back to the user.
            context = {
                'validlink': True,
                'form': None,
                'title': _('Password reset unsuccessful'),
                'err_msg': err.message,
            }
            context.update(platform_name)
            return TemplateResponse(
                request, 'registration/password_reset_confirm.html', context
            )

        # remember what the old password hash is before we call down
        old_password_hash = user.password

        response = password_reset_confirm(
            request, uidb64=uidb64, token=token, post_reset_redirect=post_reset_redirect, extra_context=platform_name
        )

        # If password reset was unsuccessful a template response is returned (status_code 200).
        # Check if form is invalid then show an error to the user.
        # Note if password reset was successful we get response redirect (status_code 302).
        if response.status_code == 200:
            form_valid = response.context_data['form'].is_valid() if response.context_data['form'] else False
            if not form_valid:
                log.warning(
                    u'Unable to reset password for user [%s] because form is not valid. '
                    u'A possible cause is that the user had an invalid reset token',
                    user.username,
                )
                response.context_data['err_msg'] = _('Error in resetting your password. Please try again.')
                return response

        # get the updated user
        updated_user = User.objects.get(id=user_id)

        # did the password hash change, if so record it in the PasswordHistory
        if updated_user.password != old_password_hash:
            entry = PasswordHistory()
            entry.create(updated_user)

    else:
        response = password_reset_confirm(
            request, uidb64=uidb64, token=token, post_reset_redirect=post_reset_redirect, extra_context=platform_name
        )

        response_was_successful = response.context_data.get('validlink')
        if response_was_successful and not user.is_active:
            user.is_active = True
            user.save()

    return response


def password_reset_confirm_wrapper(request, uidb36=None, token=None):
    """
    A wrapper around django.contrib.auth.views.password_reset_confirm.
    Needed because we want to set the user as active at this step.
    We also optionally do some additional password policy checks.
    """
    # convert old-style base36-encoded user id to base64
    uidb64 = uidb36_to_uidb64(uidb36)
    platform_name = {
        "platform_name": configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME)
    }
    try:
        uid_int = base36_to_int(uidb36)
        user = User.objects.get(id=uid_int)
    except (ValueError, User.DoesNotExist):
        # if there's any error getting a user, just let django's
        # password_reset_confirm function handle it.
        return password_reset_confirm(
            request, uidb64=uidb64, token=token, extra_context=platform_name
        )

    if UserRetirementRequest.has_user_requested_retirement(user):
        # Refuse to reset the password of any user that has requested retirement.
        context = {
            'validlink': True,
            'form': None,
            'title': _('Password reset unsuccessful'),
            'err_msg': _('Error in resetting your password.'),
        }
        context.update(platform_name)
        return TemplateResponse(
            request, 'registration/password_reset_confirm.html', context
        )

    if waffle().is_enabled(PREVENT_AUTH_USER_WRITES):
        context = {
            'validlink': False,
            'form': None,
            'title': _('Password reset unsuccessful'),
            'err_msg': SYSTEM_MAINTENANCE_MSG,
        }
        context.update(platform_name)
        return TemplateResponse(
            request, 'registration/password_reset_confirm.html', context
        )

    if request.method == 'POST':
        password = request.POST['new_password1']

        try:
            validate_password(password, user=user)
        except ValidationError as err:
            # We have a password reset attempt which violates some security
            # policy, or any other validation. Use the existing Django template to communicate that
            # back to the user.
            context = {
                'validlink': True,
                'form': None,
                'title': _('Password reset unsuccessful'),
                'err_msg': err.message,
            }
            context.update(platform_name)
            return TemplateResponse(
                request, 'registration/password_reset_confirm.html', context
            )

        # remember what the old password hash is before we call down
        old_password_hash = user.password

        response = password_reset_confirm(
            request, uidb64=uidb64, token=token, extra_context=platform_name
        )

        # If password reset was unsuccessful a template response is returned (status_code 200).
        # Check if form is invalid then show an error to the user.
        # Note if password reset was successful we get response redirect (status_code 302).
        if response.status_code == 200:
            form_valid = response.context_data['form'].is_valid() if response.context_data['form'] else False
            if not form_valid:
                log.warning(
                    u'Unable to reset password for user [%s] because form is not valid. '
                    u'A possible cause is that the user had an invalid reset token',
                    user.username,
                )
                response.context_data['err_msg'] = _('Error in resetting your password. Please try again.')
                return response

        # get the updated user
        updated_user = User.objects.get(id=uid_int)

        # did the password hash change, if so record it in the PasswordHistory
        if updated_user.password != old_password_hash:
            entry = PasswordHistory()
            entry.create(updated_user)

    else:
        response = password_reset_confirm(
            request, uidb64=uidb64, token=token, extra_context=platform_name
        )

        response_was_successful = response.context_data.get('validlink')
        if response_was_successful and not user.is_active:
            user.is_active = True
            user.save()

    return response


def password_create_confirm_wrapper(request, uidb36=None, token=None):
    """
    Copy of password_reset_confirm_wrapper to allow users registered by bach to set their password.
    A wrapper around django.contrib.auth.views.password_reset_confirm.
    Needed because we want to set the user as active at this step.
    We also optionally do some additional password policy checks.
    """
    # convert old-style base36-encoded user id to base64
    uidb64 = uidb36_to_uidb64(uidb36)
    platform_name = {
        "platform_name": configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME)
    }
    try:
        uid_int = base36_to_int(uidb36)
        user = User.objects.get(id=uid_int)
    except (ValueError, User.DoesNotExist):
        # if there's any error getting a user, just let django's
        # password_reset_confirm function handle it.
        return password_reset_confirm(
            request, uidb64=uidb64, token=token, extra_context=platform_name
        )

    if request.method == 'POST':
        password = request.POST['new_password1']

        try:
            validate_password(password, user=user)
        except ValidationError as err:
            # We have a password reset attempt which violates some security
            # policy, or any other validation. Use the existing Django template to communicate that
            # back to the user.
            context = {
                'validlink': True,
                'form': None,
                'title': _('Password create unsuccessful'),
                'err_msg': err.message,
            }
            context.update(platform_name)
            return TemplateResponse(
                request, 'registration/password_create_confirm.html', context
            )

        # remember what the old password hash is before we call down
        old_password_hash = user.password

        response = password_reset_confirm(
            request, uidb64=uidb64, token=token, extra_context=platform_name,
            post_reset_redirect="password_create_complete"
        )

        # If password reset was unsuccessful a template response is returned (status_code 200).
        # Check if form is invalid then show an error to the user.
        # Note if password reset was successful we get response redirect (status_code 302).
        if response.status_code == 200:
            form_valid = response.context_data['form'].is_valid() if response.context_data['form'] else False
            if not form_valid:
                log.warning(
                    u'Unable to create password for user [%s] because form is not valid. '
                    u'A possible cause is that the user had an invalid reset token',
                    user.username,
                )
                response.context_data['err_msg'] = _('Error in creating your password. Please try again.')
                return response

        # get the updated user
        updated_user = User.objects.get(id=uid_int)

        # did the password hash change, if so record it in the PasswordHistory
        if updated_user.password != old_password_hash:
            entry = PasswordHistory()
            entry.create(updated_user)

    else:
        response = password_reset_confirm(
            request, uidb64=uidb64, token=token, extra_context=platform_name,
            template_name="registration/password_create_confirm.html",
            post_reset_redirect="password_create_complete"
        )

        response_was_successful = response.context_data.get('validlink')
        if response_was_successful and not user.is_active:
            user.is_active = True
            user.save()

    return response


def password_create_complete(request):
    return password_reset_complete(
        request, template_name="registration/password_create_complete.html"
    )


def validate_new_email(user, new_email):
    """
    Given a new email for a user, does some basic verification of the new address If any issues are encountered
    with verification a ValueError will be thrown.
    """
    try:
        validate_email(new_email)
    except ValidationError:
        raise ValueError(_('Valid e-mail address required.'))

    if new_email == user.email:
        raise ValueError(_('Old email is the same as the new email.'))

    if email_exists_or_retired(new_email):
        raise ValueError(_('An account with this e-mail already exists.'))


def do_email_change_request(user, new_email, activation_key=None):
    """
    Given a new email for a user, does some basic verification of the new address and sends an activation message
    to the new address. If any issues are encountered with verification or sending the message, a ValueError will
    be thrown.
    """
    pec_list = PendingEmailChange.objects.filter(user=user)
    if len(pec_list) == 0:
        pec = PendingEmailChange()
        pec.user = user
    else:
        pec = pec_list[0]

    # if activation_key is not passing as an argument, generate a random key
    if not activation_key:
        activation_key = uuid.uuid4().hex

    pec.new_email = new_email
    pec.activation_key = activation_key
    pec.save()

    context = {
        'key': pec.activation_key,
        'old_email': user.email,
        'new_email': pec.new_email
    }

    subject = render_to_string('emails/email_change_subject.txt', context)
    subject = ''.join(subject.splitlines())

    message = render_to_string('emails/email_change.txt', context)

    from_address = configuration_helpers.get_value(
        'email_from_address',
        settings.DEFAULT_FROM_EMAIL
    )
    try:
        send_mail(subject, message, from_address, [pec.new_email])
    except Exception:
        log.error(u'Unable to send email activation link to user from "%s"', from_address, exc_info=True)
        raise ValueError(_('Unable to send email activation link. Please try again later.'))

    # When the email address change is complete, a "edx.user.settings.changed" event will be emitted.
    # But because changing the email address is multi-step, we also emit an event here so that we can
    # track where the request was initiated.
    tracker.emit(
        SETTING_CHANGE_INITIATED,
        {
            "setting": "email",
            "old": context['old_email'],
            "new": context['new_email'],
            "user_id": user.id,
        }
    )


@ensure_csrf_cookie
def confirm_email_change(request, key):  # pylint: disable=unused-argument
    """
    User requested a new e-mail. This is called when the activation
    link is clicked. We confirm with the old e-mail, and update
    """
    if waffle().is_enabled(PREVENT_AUTH_USER_WRITES):
        return render_to_response('email_change_failed.html', {'err_msg': SYSTEM_MAINTENANCE_MSG})

    with transaction.atomic():
        try:
            pec = PendingEmailChange.objects.get(activation_key=key)
        except PendingEmailChange.DoesNotExist:
            response = render_to_response("invalid_email_key.html", {})
            transaction.set_rollback(True)
            return response

        user = pec.user
        address_context = {
            'old_email': user.email,
            'new_email': pec.new_email
        }

        if len(User.objects.filter(email=pec.new_email)) != 0:
            response = render_to_response("email_exists.html", {})
            transaction.set_rollback(True)
            return response

        subject = render_to_string('emails/email_change_subject.txt', address_context)
        subject = ''.join(subject.splitlines())
        message = render_to_string('emails/confirm_email_change.txt', address_context)
        u_prof = UserProfile.objects.get(user=user)
        meta = u_prof.get_meta()
        if 'old_emails' not in meta:
            meta['old_emails'] = []
        meta['old_emails'].append([user.email, datetime.datetime.now(UTC).isoformat()])
        u_prof.set_meta(meta)
        u_prof.save()
        # Send it to the old email...
        try:
            user.email_user(
                subject,
                message,
                configuration_helpers.get_value('email_from_address', settings.DEFAULT_FROM_EMAIL)
            )
        except Exception:    # pylint: disable=broad-except
            log.warning('Unable to send confirmation email to old address', exc_info=True)
            response = render_to_response("email_change_failed.html", {'email': user.email})
            transaction.set_rollback(True)
            return response

        user.email = pec.new_email
        user.save()
        pec.delete()
        # And send it to the new email...
        try:
            user.email_user(
                subject,
                message,
                configuration_helpers.get_value('email_from_address', settings.DEFAULT_FROM_EMAIL)
            )
        except Exception:  # pylint: disable=broad-except
            log.warning('Unable to send confirmation email to new address', exc_info=True)
            response = render_to_response("email_change_failed.html", {'email': pec.new_email})
            transaction.set_rollback(True)
            return response

        response = render_to_response("email_change_successful.html", address_context)
        return response


@require_POST
@login_required
@ensure_csrf_cookie
def change_email_settings(request):
    """
    Modify logged-in user's setting for receiving emails from a course.
    """
    user = request.user

    course_id = request.POST.get("course_id")
    course_key = CourseKey.from_string(course_id)
    receive_emails = request.POST.get("receive_emails")
    if receive_emails:
        optout_object = Optout.objects.filter(user=user, course_id=course_key)
        if optout_object:
            optout_object.delete()
        log.info(
            u"User %s (%s) opted in to receive emails from course %s",
            user.username,
            user.email,
            course_id,
        )
        track.views.server_track(
            request,
            "change-email-settings",
            {"receive_emails": "yes", "course": course_id},
            page='dashboard',
        )
    else:
        Optout.objects.get_or_create(user=user, course_id=course_key)
        log.info(
            u"User %s (%s) opted out of receiving emails from course %s",
            user.username,
            user.email,
            course_id,
        )
        track.views.server_track(
            request,
            "change-email-settings",
            {"receive_emails": "no", "course": course_id},
            page='dashboard',
        )

    return JsonResponse({"success": True})


@ensure_csrf_cookie
def text_me_the_app(request):
    """
    Text me the app view.
    """
    text_me_fragment = TextMeTheAppFragmentView().render_to_fragment(request)
    context = {
        'nav_hidden': True,
        'show_dashboard_tabs': True,
        'show_program_listing': ProgramsApiConfig.is_student_dashboard_enabled(),
        'fragment': text_me_fragment
    }

    return render_to_response('text-me-the-app.html', context)


@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_global_staff
def batch_register_students_precheck(request):
    return _register_and_enroll_students_precheck(request)


@require_POST
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_global_staff
def batch_register_students(request):  # pylint: disable=too-many-statements
    """
    Create new accounts for students.
    Passing a csv file that contains a list of students.
    Requires staff access.

    -If the email address and username don't exist, create the new account

    -If the email address and username already exists, do nothing

    -If the email address already exists, but the username is different, assume there is an error and fail.
    The failure will be messaged in a response in the browser.

    -If the username already exists but the email is different, assume it is a different user and fail.
    The failure will be messaged in a response in the browser.

    The errors and the number of users created is logged in the browser response.
    """

    if not configuration_helpers.get_value(
            'ALLOW_AUTOMATED_SIGNUPS',
            settings.FEATURES.get('ALLOW_AUTOMATED_SIGNUPS', False),
    ):
        return HttpResponseForbidden()

    general_errors = []
    row_errors = []
    created_and_enrolled = []
    untouched = []

    if 'students_list' in request.FILES:
        students = []

        try:
            upload_file = request.FILES.get('students_list')
            if upload_file.name.endswith('.csv'):
                students = [row for row in csv.reader(upload_file.read().splitlines())]
            else:
                general_errors.append({'response': _(
                    'Make sure that the file you upload is in CSV format with no extraneous characters or rows.')})

        except Exception:  # pylint: disable=broad-except
            general_errors.append({'response': _('Could not read uploaded file.')})
        finally:
            upload_file.close()

        row_num = 0
        for student in students:
            row_num = row_num + 1

            # verify that we have the right number of columns in every row but allow for blank lines
            expected_length = len(LT_CSV) - 2
            if len(student) != expected_length:
                if len(student) > 0:
                    row_errors.append({
                        'response': _('Row #{row_num}: Data must have exactly {expected_length} columns ('
                                      'first name, last name, username, email, password, gender, year of birth, '
                                      'language, country, city, location, company, employee id, hire date, job code, '
                                      'department, supervisor, learning group, comments).')
                            .format(row_num=row_num, expected_length=expected_length)
                    })
                continue
            try:
                student = [col.decode('utf-8-sig') for col in student]
            except UnicodeDecodeError:
                row_errors.append({
                    'response': _('Row #{row_num}: Invalid utf-8 characters').format(row_num=row_num)
                })
                continue
            first_name = student[LT_CSV['first_name']].strip()
            last_name = student[LT_CSV['last_name']].strip()
            username = student[LT_CSV['username']].strip()
            email = student[LT_CSV['email']].strip()
            password = student[LT_CSV['password']].strip()
            gender = student[LT_CSV['gender']].strip()
            year_of_birth = student[LT_CSV['year_of_birth']].strip()
            language = student[LT_CSV['language']].strip().lower()
            country = student[LT_CSV['country']].strip().upper()
            company = student[LT_CSV['company']].strip()
            hire_date = student[LT_CSV['hire_date']].strip()

            try:
                validation_errors, valid_username, valid_email = csv_student_field_validation(
                    first_name, last_name, username, email, password,
                    gender, year_of_birth, language, country, company, hire_date, row_num)

                row_errors += validation_errors

                if len(validation_errors) == 0:
                    try:
                        if User.objects.filter(email=email).exists():
                            # Email address already exists.
                            # see if it is an exact match with email and username
                            # if it's not an exact match then just display an error message
                            if not User.objects.filter(email=email, username=username).exists():
                                row_errors.append({
                                    'response': _(
                                        'Row #{row_num}: An account with email {email} exists but the provided username {username} '
                                        'is different.').format(row_num=row_num, email=email, username=username)
                                })
                            else:
                                # user (username, email) already exists
                                log.info(u'user %s already registered', username)
                                untouched.append({
                                    'response': _(
                                        'Row #{row_num}: User with username {username} was already registered ' \
                                        'so nothing has changed.').format(row_num=row_num, username=username)
                                })

                        elif is_email_retired(email):
                            # We are either attempting to enroll a retired user or create a new user with
                            # an email or a username which is already associated with a retired account.
                            # Simply block these attempts.
                            row_errors.append({
                                'username': username,
                                'email': email,
                                'response': _('Row #{row_num}: Invalid email address.').format(row_num=row_num),
                            })
                            log.warning(u'Email address %s or username %s is associated with a retired user, ' +
                                        u'so course enrollment was blocked.', email, username)
                        else:
                            # This email does not yet exist, so we need to create a new account
                            # If username already exists in the database, then it will raise an IntegrityError exception.
                            hire_date = hire_date if len(hire_date) > 0 else None
                            if User.objects.filter(username=username).exists():
                                row_errors.append({
                                    'response': _(
                                        'Row #{row_num}: An account with username {username} exists but the provided email {email} '
                                        'is different.').format(row_num=row_num, username=username, email=email)
                                })
                            elif is_username_retired(username):
                                row_errors.append({
                                    'username': username,
                                    'email': email,
                                    'response': _('Row #{row_num}: Invalid username.').format(row_num=row_num),
                                })
                                log.warning(u'Email address %s or username %s is associated with a retired user, ' +
                                            u'so course enrollment was blocked.', email, username)
                            else:
                                year_of_birth = int(year_of_birth) if len(year_of_birth) > 0 else None
                                # get use profile org
                                orgs = configuration_helpers.get_current_site_orgs()
                                if not orgs:
                                    org = None
                                else:
                                    org = "+".join(orgs)
                                user = lt_create_user_and_user_profile(
                                    email, username, first_name, last_name, password,
                                    gender, year_of_birth, language, country,
                                    student[LT_CSV['city']].strip(),
                                    student[LT_CSV['location']].strip(),
                                    student[LT_CSV['company']].strip(),
                                    student[LT_CSV['employee_id']].strip(),
                                    hire_date,
                                    student[LT_CSV['job_code']].strip(),
                                    student[LT_CSV['department']].strip(),
                                    student[LT_CSV['supervisor']].strip(),
                                    student[LT_CSV['learning_group']].strip(),
                                    student[LT_CSV['comments']].strip(),
                                    org
                                )

                                log.info(u'user %s created', username)
                                created_and_enrolled.append({
                                    'response': _('Row #{row_num}: {username} / {email}')
                                        .format(row_num=row_num, username=username, email=email)
                                })
                    except Exception as ex:
                        log.exception(type(ex).__name__)
                        row_errors.append(
                            {'response': _('Row #{row_num}: {ex}').format(row_num=row_num, ex=type(ex).__name__)})
            except DjangoUnicodeDecodeError:
                row_errors.append({
                    'response': _('Row #{row_num}: Invalid utf-8 characters').format(row_num=row_num)
                })

    else:
        general_errors.append({'response': _('File is not attached.')})

    results = {
        'general_errors': general_errors,
        'row_errors': row_errors,
        'created': created_and_enrolled,
        'untouched': untouched
    }
    return JsonResponse(results)


@require_POST
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_global_staff
def batch_update_students(request):
    return _batch_update_student(request)


@require_POST
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_global_staff
def batch_send_welcoming_email(request):
    return _send_welcoming_email(request)


@require_POST
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_global_staff
@require_post_params(action="enroll or unenroll", identifiers="stringified list of emails and/or usernames",
                     course_id="course ID to enroll/unenroll")
def batch_enroll_in_course(request):
    """
    Enroll or unenroll students by email.
    Requires staff access.

    Query Parameters:
    - action in ['enroll', 'unenroll']
    - identifiers is string containing a list of emails and/or usernames separated by anything split_input_list can handle.
    - auto_enroll is a boolean (defaults to false)
        If auto_enroll is false, students will be allowed to enroll.
        If auto_enroll is true, students will be enrolled as soon as they register.
    - email_students is a boolean (defaults to false)
        If email_students is true, students will be sent email notification
        If email_students is false, students will not be sent email notification

    Returns an analog to this JSON structure: {
        "action": "enroll",
        "auto_enroll": false,
        "results": [
            {
                "email": "testemail@test.org",
                "before": {
                    "enrollment": false,
                    "auto_enroll": false,
                    "user": true,
                    "allowed": false
                },
                "after": {
                    "enrollment": true,
                    "auto_enroll": false,
                    "user": true,
                    "allowed": false
                }
            }
        ]
    }
    """
    course_id = request.POST.get('course_id')
    course_id = CourseKey.from_string(course_id)
    action = request.POST.get('action')
    identifiers_raw = request.POST.get('identifiers')
    identifiers = _split_input_list(identifiers_raw)
    auto_enroll = _get_boolean_param(request, 'auto_enroll')
    email_students = _get_boolean_param(request, 'email_students')
    reason = "Admin Panel Batch Enrollment"
    role = "Learner"

    allowed_role_choices = configuration_helpers.get_value(
        'MANUAL_ENROLLMENT_ROLE_CHOICES',
        settings.MANUAL_ENROLLMENT_ROLE_CHOICES)
    if role and role not in allowed_role_choices:
        return JsonResponse(
            {
                'action': action,
                'results': [{'error': True, 'message': 'Not a valid role choice'}],
                'auto_enroll': auto_enroll,
            }, status=400)

    enrollment_obj = None
    state_transition = DEFAULT_TRANSITION_STATE

    email_params = {}
    if email_students:
        course = get_course_by_id(course_id)
        email_params = get_email_params(course, auto_enroll, secure=request.is_secure())

    results = []
    for identifier in identifiers:
        # First try to get a user object from the identifer
        user = None
        email = None
        language = None
        try:
            user = get_student_from_identifier(identifier)
        except User.DoesNotExist:
            email = identifier
        else:
            email = user.email
            language = get_user_email_language(user)

        try:
            # Use django.core.validators.validate_email to check email address
            # validity (obviously, cannot check if email actually /exists/,
            # simply that it is plausibly valid)
            validate_email(email)  # Raises ValidationError if invalid
            no_email_address = getattr(settings, 'LEARNER_NO_EMAIL')
            if action == 'enroll':
                if (no_email_address and email.endswith(no_email_address)
                        and auto_enroll and not email_students):
                    before, after, enrollment_obj = enroll_user(course_id, user)
                    results.append({
                        'identifier': identifier,
                        'before': {
                            'user': True,
                            'enrollment': before,
                            'allowed': False,
                            'auto_enroll': False,
                        },
                        'after': {
                            'user': True,
                            'enrollment': after,
                            'allowed': False,
                            'auto_enroll': False,
                        }
                    })
                else:
                    before, after, enrollment_obj = enroll_email(
                        course_id, email, auto_enroll, email_students, email_params, language=language
                    )
                    before_enrollment = before.to_dict()['enrollment']
                    before_user_registered = before.to_dict()['user']
                    before_allowed = before.to_dict()['allowed']
                    after_enrollment = after.to_dict()['enrollment']
                    after_allowed = after.to_dict()['allowed']

                    if before_user_registered:
                        if after_enrollment:
                            if before_enrollment:
                                state_transition = ENROLLED_TO_ENROLLED
                            else:
                                if before_allowed:
                                    state_transition = ALLOWEDTOENROLL_TO_ENROLLED
                                else:
                                    state_transition = UNENROLLED_TO_ENROLLED
                    else:
                        if after_allowed:
                            state_transition = UNENROLLED_TO_ALLOWEDTOENROLL

            elif action == 'unenroll':
                if user and ProgramsApiConfig.is_student_dashboard_enabled():
                    # Activate checking while program is enabled
                    _filter = {
                        'courses.course_runs.key': str(course_id)
                    }
                    _programs_uuids = [
                        program.to_dict()['uuid']
                        for program in PartialProgram.query(
                            _filter,
                            loading_policy=PartialProgram.POLICY_LOAD_LP_ONLY
                        )
                    ]
                    user_enrolled_programs_count = ProgramEnrollment.objects.filter(
                        program_uuid__in=_programs_uuids,
                        user_id=user.id,
                        status=ProgramEnrollmentStatuses.ENROLLED
                    ).count()
                    if user_enrolled_programs_count > 0:
                        raise _PartialUnenrollException(
                            'The user({}) has existed in other {} programs'.format(
                                user.email, user_enrolled_programs_count
                            )
                        )

                if (no_email_address and email.endswith(no_email_address)
                        and not email_students):
                    before, after = unenroll_user(course_id, user)
                    results.append({
                        'identifier': identifier,
                        'before': {
                            'user': True,
                            'enrollment': before,
                            'allowed': False,
                            'auto_enroll': False,
                        },
                        'after': {
                            'user': True,
                            'enrollment': after,
                            'allowed': False,
                            'auto_enroll': False,
                        }
                    })
                else:
                    before, after = unenroll_email(
                        course_id, email, email_students, email_params, language=language
                    )
                    before_enrollment = before.to_dict()['enrollment']
                    before_allowed = before.to_dict()['allowed']
                    enrollment_obj = CourseEnrollment.get_enrollment(user, course_id) if user else None

                    if before_enrollment:
                        state_transition = ENROLLED_TO_UNENROLLED
                    else:
                        if before_allowed:
                            state_transition = ALLOWEDTOENROLL_TO_UNENROLLED
                        else:
                            state_transition = UNENROLLED_TO_UNENROLLED

            else:
                return HttpResponseBadRequest(strip_tags(
                    "Unrecognized action '{}'".format(action)
                ))

        except _PartialUnenrollException:
            # Flag this email/username as an error if we only unenroll this from Course before Program,
            # But continue checking the remaining in the list
            results.append(
                {
                    'identifier': identifier,
                    'partialUnenrollIdentifier': True
                }
            )
        except ValidationError:
            # Flag this email as an error if invalid, but continue checking
            # the remaining in the list
            results.append({
                'identifier': identifier,
                'invalidIdentifier': True,
            })

        except Exception as exc:  # pylint: disable=broad-except
            # catch and log any exceptions
            # so that one error doesn't cause a 500.
            log.exception(u"Error while #{}ing student")
            log.exception(exc)
            results.append({
                'identifier': identifier,
                'error': True,
            })

        else:
            if (no_email_address and not email.endswith(no_email_address)) or \
                    (no_email_address is None and email is not None):
                ManualEnrollmentAudit.create_manual_enrollment_audit(
                    request.user, email, state_transition, reason, enrollment_obj, role
                )
                results.append({
                    'identifier': identifier,
                    'before': before.to_dict(),
                    'after': after.to_dict(),
                })

    response_payload = {
        'action': action,
        'results': results,
        'auto_enroll': auto_enroll,
    }
    return JsonResponse(response_payload)


@require_POST
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_global_staff
@require_post_params(action="enroll or unenroll", identifiers="stringified list of emails and/or usernames",
                     program_id="program ID to enroll/unenroll")
def batch_enroll_in_program(request):
    """
    Enroll or unenroll students into a program by email.
    Requires staff access.

    Query Parameters:
    - action in ['enroll', 'unenroll']
    - identifiers is string containing a list of emails and/or usernames separated by anything split_input_list can handle.
    - program_id is a string containing the program ID to enroll/unenroll the users to.
    - auto_enroll is a boolean (defaults to false)
        If auto_enroll is false, students will be allowed to enroll.
        If auto_enroll is true, students will be enrolled as soon as they register.
    - email_students is a boolean (defaults to false)
        If email_students is true, students will be sent email notification
        If email_students is false, students will not be sent email notification

    Returns an analog to this JSON structure: {
        "action": "enroll",
        "auto_enroll": false,
        "results": [
            {
                "email": "testemail@test.org",
                "before": {
                    "enrollment": false,
                    "auto_enroll": false,
                    "user": true,
                    "allowed": false
                },
                "after": {
                    "enrollment": true,
                    "auto_enroll": false,
                    "user": true,
                    "allowed": false
                }
            }
        ]
    }
    """
    program_id = request.POST.get('program_id')
    action = request.POST.get('action')
    identifiers_raw = request.POST.get('identifiers')
    identifiers = _split_input_list(identifiers_raw)
    auto_enroll = _get_boolean_param(request, 'auto_enroll')
    email_students = _get_boolean_param(request, 'email_students')

    email_params = {}
    if email_students:
        email_params = get_email_params_for_program(program_id, auto_enroll, secure=request.is_secure())

    results = []
    for identifier in identifiers:
        # First try to get a user object from the identifier
        user = None
        email = None
        language = None
        try:
            user = get_student_from_identifier(identifier)
        except User.DoesNotExist:
            email = identifier
        else:
            email = user.email
            language = get_user_email_language(user)

        try:
            # Use django.core.validators.validate_email to check email address
            # validity (obviously, cannot check if email actually /exists/,
            # simply that it is plausibly valid)
            validate_email(email)  # Raises ValidationError if invalid
            no_email_address = getattr(settings, 'LEARNER_NO_EMAIL')
            if action == 'enroll':
                if (user and no_email_address and email.endswith(no_email_address)
                        and auto_enroll and not email_students):
                    existing_enrollment = fetch_program_enrollments(
                        program_uuid=program_id,
                        users=[user.id]
                    )
                    # Consider the situation when enrollment already exist.
                    before, create, update = (True, False, True) if existing_enrollment else (False, True, False)
                    # Enroll a program
                    write_program_enrollment(
                        program_id,
                        {
                            'username': user.username,
                            'status': ProgramEnrollmentStatuses.ENROLLED
                        },
                        create, update
                    )

                    # Enroll all courses of this program for user.
                    program = PartialProgram.query_one(
                        {'_id': program_id}
                    )
                    program_course_keys = [
                        CourseKey.from_string(course_run['key'])
                        for course in program['courses'] for course_run in course['course_runs']
                    ] if program else []

                    if program_course_keys:
                        write_program_courses_enrollments(
                            program_id,
                            program_course_keys,
                            {
                                'username': user.username,
                                'status': ProgramCourseEnrollmentStatuses.ACTIVE
                            },
                            create,
                            update,
                        )
                    results.append({
                        'identifier': identifier,
                        'before': {
                            'user': True,
                            'enrollment': before,
                            'allowed': False,
                            'auto_enroll': False,
                        },
                        'after': {
                            'user': True,
                            'enrollment': True,
                            'allowed': False,
                            'auto_enroll': False,
                        }
                    })
                else:
                    before, after, enrollment_obj = program_enroll_email(
                        program_id, email, auto_enroll, email_students, email_params, language=language
                    )
                    results.append({
                        'identifier': identifier,
                        'before': {
                            'user': before.to_dict()['user'],
                            'enrollment': before.to_dict()['enrollment'],
                            'allowed': before.to_dict()['allowed'],
                            'auto_enroll': False,
                        },
                        'after': {
                            'user': after.to_dict()['user'],
                            'enrollment': after.to_dict()['enrollment'],
                            'allowed': after.to_dict()['allowed'],
                            'auto_enroll': auto_enroll,
                        }
                    })

            elif action == 'unenroll':
                existing_enrollment = None
                if user:
                    existing_enrollment = fetch_program_enrollments(
                        program_uuid=program_id,
                        users=[user.id],
                        program_enrollment_statuses=ProgramEnrollmentStatuses.__ACTIVE__
                    )
                # Consider the situation when enrollment already exist.
                if existing_enrollment and (no_email_address and email.endswith(no_email_address)
                                            and not email_students):
                    create, update = (False, True)

                    write_program_enrollment(
                        program_id,
                        {
                            'username': user.username,
                            'status': ProgramEnrollmentStatuses.CANCELED
                        },
                        create, update
                    )

                    # Enroll all courses of this program for user.
                    program = PartialProgram.query_one(
                        {'_id': program_id}
                    )
                    program_course_keys = [
                        CourseKey.from_string(course_run['key'])
                        for course in program['courses'] for course_run in course['course_runs']
                    ] if program else []

                    if program_course_keys:
                        write_program_courses_enrollments(
                            program_id,
                            program_course_keys,
                            {
                                'username': user.username,
                                'status': ProgramCourseEnrollmentStatuses.INACTIVE
                            },
                            create,
                            update,
                        )
                    results.append({
                        'identifier': identifier,
                        'before': {
                            'user': True,
                            'enrollment': True,
                            'allowed': False,
                            'auto_enroll': False,
                        },
                        'after': {
                            'user': True,
                            'enrollment': False,
                            'allowed': False,
                            'auto_enroll': False,
                        }
                    })
                else:
                    before, after = program_unenroll_email(
                        program_id, email, email_students, email_params, language=language
                    )
                    results.append({
                        'identifier': identifier,
                        'before': {
                            'user': before.to_dict()['user'],
                            'enrollment': before.to_dict()['enrollment'],
                            'allowed': before.to_dict()['allowed'],
                            'auto_enroll': False,
                        },
                        'after': {
                            'user': after.to_dict()['user'],
                            'enrollment': after.to_dict()['enrollment'],
                            'allowed': after.to_dict()['allowed'],
                            'auto_enroll': False,
                        }
                    })

            else:
                return HttpResponseBadRequest(strip_tags(
                    "Unrecognized action '{}'".format(action)
                ))

        except _PartialUnenrollException:
            # Flag this email/username as an error if we only unenroll this from Course before Program,
            # But continue checking the remaining in the list
            results.append(
                {
                    'identifier': identifier,
                    'partialUnenrollIdentifier': True
                }
            )
        except ValidationError:
            # Flag this email as an error if invalid, but continue checking
            # the remaining in the list
            results.append({
                'identifier': identifier,
                'invalidIdentifier': True,
            })

        except Exception as exc:  # pylint: disable=broad-except
            # catch and log any exceptions
            # so that one error doesn't cause a 500.
            log.exception(u"Error while #{}ing student")
            log.exception(exc)
            results.append({
                'identifier': identifier,
                'error': True,
            })

    response_payload = {
        'action': action,
        'results': results,
        'auto_enroll': auto_enroll,
    }
    return JsonResponse(response_payload)
