"""
Enrollment operations for use by instructor APIs.

Does not include any access control, be sure to check access before calling.
"""

import json
import logging
from datetime import datetime
from email.mime.image import MIMEImage

import pytz
from course_modes.models import CourseMode
from courseware.models import StudentModule
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives
from django.urls import reverse
from django.utils.translation import override as override_language
from edxmako.shortcuts import render_to_string
from eventtracking import tracker
from opaque_keys.edx.keys import CourseKey
from path import Path
from six import text_type
from student.models import (
    CourseEnrollment,
    CourseEnrollmentAllowed,
    anonymous_id_for_user,
    is_email_retired,
    ProgramEnrollmentAllowed,
)
from submissions import api as sub_api  # installed from the edx-submissions repository
from submissions.models import score_set
from track.event_transaction_utils import (
    create_new_event_transaction_id,
    get_event_transaction_id,
    set_event_transaction_type
)
from util.email_utils import send_mail_with_alias as send_mail
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError

from lms.djangoapps.grades.constants import ScoreDatabaseTableEnum
from lms.djangoapps.grades.events import STATE_DELETED_EVENT_TYPE
from lms.djangoapps.grades.signals.handlers import disconnect_submissions_signal_receiver
from lms.djangoapps.grades.signals.signals import PROBLEM_RAW_SCORE_CHANGED
from lms.djangoapps.program_enrollments.api import write_program_enrollment, write_program_courses_enrollments, \
    fetch_program_enrollments
from lms.djangoapps.program_enrollments.constants import ProgramEnrollmentStatuses, ProgramCourseEnrollmentStatuses
from lms.djangoapps.program_enrollments.persistance.programs import PartialProgram
from openedx.core.djangoapps.lang_pref import LANGUAGE_KEY
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.core.djangoapps.theming.helpers import get_theme_base_dir
from openedx.core.djangoapps.theming.models import SiteTheme
from openedx.core.djangoapps.user_api.models import UserPreference

log = logging.getLogger(__name__)


class EmailEnrollmentState(object):
    """ Store the complete enrollment state of an email in a class """

    def __init__(self, course_id, email):
        # N.B. retired users are not a concern here because they should be
        # handled at a higher level (i.e. in enroll_email).  Besides, this
        # class creates readonly objects.
        exists_user = User.objects.filter(email=email).exists()
        if exists_user:
            user = User.objects.get(email=email)
            mode, is_active = CourseEnrollment.enrollment_mode_for_user(user, course_id)
            # is_active is `None` if the user is not enrolled in the course
            exists_ce = is_active is not None and is_active
            full_name = user.profile.name
            ceas = CourseEnrollmentAllowed.for_user(user).filter(course_id=course_id).all()
        else:
            mode = None
            exists_ce = False
            full_name = None
            ceas = CourseEnrollmentAllowed.objects.filter(email=email, course_id=course_id).all()
        exists_allowed = ceas.exists()
        state_auto_enroll = exists_allowed and ceas[0].auto_enroll

        self.user = exists_user
        self.enrollment = exists_ce
        self.allowed = exists_allowed
        self.auto_enroll = bool(state_auto_enroll)
        self.full_name = full_name
        self.mode = mode

    def __repr__(self):
        return "{}(user={}, enrollment={}, allowed={}, auto_enroll={})".format(
            self.__class__.__name__,
            self.user,
            self.enrollment,
            self.allowed,
            self.auto_enroll,
        )

    def to_dict(self):
        """
        example: {
            'user': False,
            'enrollment': False,
            'allowed': True,
            'auto_enroll': True,
        }
        """
        return {
            'user': self.user,
            'enrollment': self.enrollment,
            'allowed': self.allowed,
            'auto_enroll': self.auto_enroll,
        }


class EmailProgramEnrollmentState(object):
    """ Store the complete enrollment state of an email in a class """

    def __init__(self, program_id, email):
        # N.B. retired users are not a concern here because they should be
        # handled at a higher level (i.e. in enroll_email).  Besides, this
        # class creates readonly objects.
        exists_user = User.objects.filter(email=email).exists()
        if exists_user:
            user = User.objects.get(email=email)
            existing_enrollment = fetch_program_enrollments(
                program_uuid=program_id,
                users=[user.id],
                program_enrollment_statuses=ProgramEnrollmentStatuses.__ACTIVE__
            )
            is_active = True if existing_enrollment else False
            exists_pe = is_active is not None and is_active
            full_name = user.profile.name
            peas = ProgramEnrollmentAllowed.for_user(user).filter(program_id=program_id).all()
        else:
            exists_pe = False
            full_name = None
            peas = ProgramEnrollmentAllowed.objects.filter(email=email, program_id=program_id).all()
        exists_allowed = peas.exists()
        state_auto_enroll = exists_allowed and peas[0].auto_enroll

        self.user = exists_user
        self.enrollment = exists_pe
        self.allowed = exists_allowed
        self.auto_enroll = bool(state_auto_enroll)
        self.full_name = full_name

    def __repr__(self):
        return "{}(user={}, enrollment={}, allowed={}, auto_enroll={})".format(
            self.__class__.__name__,
            self.user,
            self.enrollment,
            self.allowed,
            self.auto_enroll,
        )

    def to_dict(self):
        """
        example: {
            'user': False,
            'enrollment': False,
            'allowed': True,
            'auto_enroll': True,
        }
        """
        return {
            'user': self.user,
            'enrollment': self.enrollment,
            'allowed': self.allowed,
            'auto_enroll': self.auto_enroll,
        }


def get_user_email_language(user):
    """
    Return the language most appropriate for writing emails to user. Returns
    None if the preference has not been set, or if the user does not exist.
    """
    # Calling UserPreference directly instead of get_user_preference because the user requesting the
    # information is not "user" and also may not have is_staff access.
    return UserPreference.get_value(user, LANGUAGE_KEY)


def enroll_email(course_id, student_email, auto_enroll=False, email_students=False, email_params=None, language=None):
    """
    Enroll a student by email.

    `student_email` is student's emails e.g. "foo@bar.com"
    `auto_enroll` determines what is put in CourseEnrollmentAllowed.auto_enroll
        if auto_enroll is set, then when the email registers, they will be
        enrolled in the course automatically.
    `email_students` determines if student should be notified of action by email.
    `email_params` parameters used while parsing email templates (a `dict`).
    `language` is the language used to render the email.

    returns two EmailEnrollmentState's
        representing state before and after the action.
    """
    previous_state = EmailEnrollmentState(course_id, student_email)
    enrollment_obj = None
    if previous_state.user:
        # if the student is currently unenrolled, don't enroll them in their
        # previous mode

        # for now, White Labels use 'shoppingcart' which is based on the
        # "honor" course_mode. Given the change to use "audit" as the default
        # course_mode in Open edX, we need to be backwards compatible with
        # how White Labels approach enrollment modes.
        if CourseMode.is_white_label(course_id):
            course_mode = CourseMode.DEFAULT_SHOPPINGCART_MODE_SLUG
        else:
            course_mode = None

        if previous_state.enrollment:
            course_mode = previous_state.mode

        enrollment_obj = CourseEnrollment.enroll_by_email(student_email, course_id, course_mode)
        if email_students:
            email_params['message'] = 'enrolled_enroll'
            email_params['email_address'] = student_email
            email_params['full_name'] = previous_state.full_name
            send_mail_to_student(student_email, email_params, language=language)
    elif not is_email_retired(student_email):
        cea, _ = CourseEnrollmentAllowed.objects.get_or_create(course_id=course_id, email=student_email)
        cea.auto_enroll = auto_enroll
        cea.save()
        if email_students:
            email_params['message'] = 'allowed_enroll'
            email_params['email_address'] = student_email
            send_mail_to_student(student_email, email_params, language=language)

    after_state = EmailEnrollmentState(course_id, student_email)

    return previous_state, after_state, enrollment_obj


def program_enroll_email(program_id, student_email, auto_enroll=False, email_students=False, email_params=None,
                         language=None):
    """
    Enroll a student into a program by email.

    `student_email` is student's emails e.g. "foo@bar.com"
    `auto_enroll` determines what is put in CourseEnrollmentAllowed.auto_enroll
        if auto_enroll is set, then when the email registers, they will be
        enrolled in the course automatically.
    `email_students` determines if student should be notified of action by email.
    `email_params` parameters used while parsing email templates (a `dict`).
    `language` is the language used to render the email.

    returns two EmailProgramEnrollmentState's
        representing state before and after the action.
    """
    previous_state = EmailProgramEnrollmentState(program_id, student_email)
    enrollment_obj = None
    if previous_state.user:
        user = User.objects.get(email=student_email)
        existing_enrollment = fetch_program_enrollments(
            program_uuid=program_id,
            users=[user.id]
        )
        create, update = (False, True) if existing_enrollment else (True, False)
        # Enroll a program
        enrollment_obj = write_program_enrollment(
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
        if email_students:
            email_params['message'] = 'program_enrolled'
            email_params['email_address'] = student_email
            email_params['full_name'] = previous_state.full_name
            send_mail_to_student(student_email, email_params, language=language)
    elif not is_email_retired(student_email):
        pea, _ = ProgramEnrollmentAllowed.objects.get_or_create(program_id=program_id, email=student_email)
        pea.auto_enroll = auto_enroll
        pea.save()
        if email_students:
            email_params['message'] = 'program_allowed_enroll'
            email_params['email_address'] = student_email
            send_mail_to_student(student_email, email_params, language=language)

    after_state = EmailProgramEnrollmentState(program_id, student_email)

    return previous_state, after_state, enrollment_obj


def enroll_user(course_id, student):
    """
    Enroll a student by user.

    `student` is student's user

    returns the enrollment state before and after enrollment and the enrollment object.
    """
    # if the student is currently unenrolled, don't enroll them in their
    # previous mode

    # for now, White Labels use 'shoppingcart' which is based on the
    # "honor" course_mode. Given the change to use "audit" as the default
    # course_mode in Open edX, we need to be backwards compatible with
    # how White Labels approach enrollment modes.
    if CourseMode.is_white_label(course_id):
        course_mode = CourseMode.DEFAULT_SHOPPINGCART_MODE_SLUG
    else:
        course_mode = None

    mode, is_active = CourseEnrollment.enrollment_mode_for_user(student, course_id)
    # is_active is `None` if the user is not enrolled in the course
    before_enrollment = is_active is not None and is_active
    if before_enrollment:
        course_mode = mode

    enrollment_obj = CourseEnrollment.enroll(student, course_id, course_mode)
    after_enrollment = enrollment_obj.is_active
    return before_enrollment, after_enrollment, enrollment_obj


def unenroll_email(course_id, student_email, email_students=False, email_params=None, language=None):
    """
    Unenroll a student by user.

    `student` is student's user
    `email_students` determines if student should be notified of action by email.
    `email_params` parameters used while parsing email templates (a `dict`).
    `language` is the language used to render the email.

    returns two EmailEnrollmentState's
        representing state before and after the action.
    """
    previous_state = EmailEnrollmentState(course_id, student_email)
    if previous_state.enrollment:
        CourseEnrollment.unenroll_by_email(student_email, course_id)
        if email_students:
            email_params['message'] = 'enrolled_unenroll'
            email_params['email_address'] = student_email
            email_params['full_name'] = previous_state.full_name
            send_mail_to_student(student_email, email_params, language=language)

    if previous_state.allowed:
        CourseEnrollmentAllowed.objects.get(course_id=course_id, email=student_email).delete()
        if email_students:
            email_params['message'] = 'allowed_unenroll'
            email_params['email_address'] = student_email
            # Since no User object exists for this student there is no "full_name" available.
            send_mail_to_student(student_email, email_params, language=language)

    after_state = EmailEnrollmentState(course_id, student_email)

    return previous_state, after_state


def program_unenroll_email(program_id, student_email, email_students=False, email_params=None, language=None):
    """
    Unenroll a student from a progeam by email.

    `student_email` is student's email
    `email_students` determines if student should be notified of action by email.
    `email_params` parameters used while parsing email templates (a `dict`).
    `language` is the language used to render the email.

    returns two EmailProgramEnrollmentState's
        representing state before and after the action.
    """
    previous_state = EmailProgramEnrollmentState(program_id, student_email)
    if previous_state.enrollment:
        user = User.objects.get(email=student_email)

        create, update = (False, True)

        write_program_enrollment(
            program_id,
            {
                'username': user.username,
                'status': ProgramEnrollmentStatuses.CANCELED
            },
            create, update
        )

        # Unenroll all courses of this program for user.
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
        if email_students:
            email_params['message'] = 'program_enrolled_unenroll'
            email_params['email_address'] = student_email
            email_params['full_name'] = previous_state.full_name
            send_mail_to_student(student_email, email_params, language=language)

    if previous_state.allowed:
        ProgramEnrollmentAllowed.objects.get(program_id=program_id, email=student_email).delete()
        if email_students:
            email_params['message'] = 'program_allowed_unenroll'
            email_params['email_address'] = student_email
            # Since no User object exists for this student there is no "full_name" available.
            send_mail_to_student(student_email, email_params, language=language)

    after_state = EmailProgramEnrollmentState(program_id, student_email)

    return previous_state, after_state


def unenroll_user(course_id, student):
    """
    Unenroll a student by user.

    `student` is student's user

    returns the enrollment state before and after unenrollment.
    """
    _, before_is_active = CourseEnrollment.enrollment_mode_for_user(student, course_id)
    # is_active is `None` if the user is not enrolled in the course
    if before_is_active is not None and before_is_active:
        CourseEnrollment.unenroll(student, course_id)

    _, after_is_active = CourseEnrollment.enrollment_mode_for_user(student, course_id)

    return before_is_active, after_is_active


def send_beta_role_email(action, user, email_params):
    """
    Send an email to a user added or removed as a beta tester.

    `action` is one of 'add' or 'remove'
    `user` is the User affected
    `email_params` parameters used while parsing email templates (a `dict`).
    """
    if action in ('add', 'remove'):
        email_params['message'] = '%s_beta_tester' % action
        email_params['email_address'] = user.email
        email_params['full_name'] = user.profile.name
    else:
        raise ValueError("Unexpected action received '{}' - expected 'add' or 'remove'".format(action))
    trying_to_add_inactive_user = not user.is_active and action == 'add'
    if not trying_to_add_inactive_user:
        send_mail_to_student(user.email, email_params, language=get_user_email_language(user))


def reset_student_attempts(course_id, student, module_state_key, requesting_user, delete_module=False):
    """
    Reset student attempts for a problem. Optionally deletes all student state for the specified problem.

    In the previous instructor dashboard it was possible to modify/delete
    modules that were not problems. That has been disabled for safety.

    `student` is a User
    `problem_to_reset` is the name of a problem e.g. 'L2Node1'.
    To build the module_state_key 'problem/' and course information will be appended to `problem_to_reset`.

    Raises:
        ValueError: `problem_state` is invalid JSON.
        StudentModule.DoesNotExist: could not load the student module.
        submissions.SubmissionError: unexpected error occurred while resetting the score in the submissions API.

    """
    user_id = anonymous_id_for_user(student, course_id)
    requesting_user_id = anonymous_id_for_user(requesting_user, course_id)
    submission_cleared = False
    try:
        # A block may have children. Clear state on children first.
        block = modulestore().get_item(module_state_key)
        if block.has_children:
            for child in block.children:
                try:
                    reset_student_attempts(course_id, student, child, requesting_user, delete_module=delete_module)
                except StudentModule.DoesNotExist:
                    # If a particular child doesn't have any state, no big deal, as long as the parent does.
                    pass
        if delete_module:
            # Some blocks (openassessment) use StudentModule data as a key for internal submission data.
            # Inform these blocks of the reset and allow them to handle their data.
            clear_student_state = getattr(block, "clear_student_state", None)
            if callable(clear_student_state):
                with disconnect_submissions_signal_receiver(score_set):
                    clear_student_state(
                        user_id=user_id,
                        course_id=unicode(course_id),
                        item_id=unicode(module_state_key),
                        requesting_user_id=requesting_user_id
                    )
                submission_cleared = True
    except ItemNotFoundError:
        block = None
        log.warning("Could not find %s in modulestore when attempting to reset attempts.", module_state_key)

    # Reset the student's score in the submissions API, if xblock.clear_student_state has not done so already.
    # We need to do this before retrieving the `StudentModule` model, because a score may exist with no student module.

    # TODO: Should the LMS know about sub_api and call this reset, or should it generically call it on all of its
    # xblock services as well?  See JIRA ARCH-26.
    if delete_module and not submission_cleared:
        sub_api.reset_score(
            user_id,
            text_type(course_id),
            text_type(module_state_key),
        )

    module_to_reset = StudentModule.objects.get(
        student_id=student.id,
        course_id=course_id,
        module_state_key=module_state_key
    )

    if delete_module:
        module_to_reset.delete()
        create_new_event_transaction_id()
        set_event_transaction_type(STATE_DELETED_EVENT_TYPE)
        tracker.emit(
            unicode(STATE_DELETED_EVENT_TYPE),
            {
                'user_id': unicode(student.id),
                'course_id': unicode(course_id),
                'problem_id': unicode(module_state_key),
                'instructor_id': unicode(requesting_user.id),
                'event_transaction_id': unicode(get_event_transaction_id()),
                'event_transaction_type': unicode(STATE_DELETED_EVENT_TYPE),
            }
        )
        if not submission_cleared:
            _fire_score_changed_for_block(
                course_id,
                student,
                block,
                module_state_key,
            )
    else:
        _reset_module_attempts(module_to_reset)


def _reset_module_attempts(studentmodule):
    """
    Reset the number of attempts on a studentmodule.

    Throws ValueError if `problem_state` is invalid JSON.
    """
    # load the state json
    problem_state = json.loads(studentmodule.state)
    # old_number_of_attempts = problem_state["attempts"]
    problem_state["attempts"] = 0

    # save
    studentmodule.state = json.dumps(problem_state)
    studentmodule.save()


def _fire_score_changed_for_block(
        course_id,
        student,
        block,
        module_state_key,
):
    """
    Fires a PROBLEM_RAW_SCORE_CHANGED event for the given module.
    The earned points are always zero. We must retrieve the possible points
    from the XModule, as noted below. The effective time is now().
    """
    if block and block.has_score:
        max_score = block.max_score()
        if max_score is not None:
            PROBLEM_RAW_SCORE_CHANGED.send(
                sender=None,
                raw_earned=0,
                raw_possible=max_score,
                weight=getattr(block, 'weight', None),
                user_id=student.id,
                course_id=unicode(course_id),
                usage_id=unicode(module_state_key),
                score_deleted=True,
                only_if_higher=False,
                modified=datetime.now().replace(tzinfo=pytz.UTC),
                score_db_table=ScoreDatabaseTableEnum.courseware_student_module,
            )


def get_email_params(course, auto_enroll, secure=True, course_key=None, display_name=None):
    """
    Generate parameters used when parsing email templates.

    `auto_enroll` is a flag for auto enrolling non-registered students: (a `boolean`)
    Returns a dict of parameters
    """

    protocol = 'https' if secure else 'http'
    course_key = course_key or text_type(course.id)
    display_name = display_name or course.display_name_with_default_escaped

    stripped_site_name = configuration_helpers.get_value(
        'SITE_NAME',
        settings.SITE_NAME
    )
    # TODO: Use request.build_absolute_uri rather than '{proto}://{site}{path}'.format
    # and check with the Services team that this works well with microsites
    registration_url = u'{proto}://{site}{path}'.format(
        proto=protocol,
        site=stripped_site_name,
        path=reverse('register_user')
    )
    course_url = u'{proto}://{site}{path}'.format(
        proto=protocol,
        site=stripped_site_name,
        path=reverse('course_root', kwargs={'course_id': course_key})
    )

    # We can't get the url to the course's About page if the marketing site is enabled.
    course_about_url = None
    if not settings.FEATURES.get('ENABLE_MKTG_SITE', False):
        course_about_url = u'{proto}://{site}{path}'.format(
            proto=protocol,
            site=stripped_site_name,
            path=reverse('about_course', kwargs={'course_id': course_key})
        )

    is_shib_course = uses_shib(course)

    # Composition of email
    email_params = {
        'site_name': stripped_site_name,
        'registration_url': registration_url,
        'course': course,
        'display_name': display_name,
        'auto_enroll': auto_enroll,
        'course_url': course_url,
        'course_about_url': course_about_url,
        'is_shib_course': is_shib_course,
    }
    return email_params


def get_email_params_for_program(program_id, auto_enroll, secure=True):
    """
    Generate parameters used when parsing email templates.

    `auto_enroll` is a flag for auto enrolling non-registered students: (a `boolean`)
    Returns a dict of parameters
    """

    protocol = 'https' if secure else 'http'

    stripped_site_name = configuration_helpers.get_value(
        'SITE_NAME',
        settings.SITE_NAME
    )
    # TODO: Use request.build_absolute_uri rather than '{proto}://{site}{path}'.format
    # and check with the Services team that this works well with microsites
    registration_url = u'{proto}://{site}{path}'.format(
        proto=protocol,
        site=stripped_site_name,
        path=reverse('register_user')
    )

    program_data = PartialProgram.query_one(
        {'_id': program_id}
    )
    program = program_data.to_dict()

    program_url = u'{proto}://{site}{path}'.format(
        proto=protocol,
        site=stripped_site_name,
        path=reverse('program_marketing_view', kwargs={'program_uuid': program_id})
    )

    # Composition of email
    email_params = {
        'site_name': stripped_site_name,
        'registration_url': registration_url,
        'program': program,
        'display_name': program['title'],
        'auto_enroll': auto_enroll,
        'program_url': program_url,
    }
    return email_params


def send_mail_to_student(student, param_dict, language=None):
    """
    Construct the email using templates and then send it.
    `student` is the student's email address (a `str`),

    `param_dict` is a `dict` with keys
    [
        `site_name`: name given to edX instance (a `str`)
        `registration_url`: url for registration (a `str`)
        `display_name` : display name of a course (a `str`)
        `course_id`: id of course (a `str`)
        `auto_enroll`: user input option (a `str`)
        `course_url`: url of course (a `str`)
        `email_address`: email of student (a `str`)
        `full_name`: student full name (a `str`)
        `message`: type of email to send and template to use (a `str`)
        `is_shib_course`: (a `boolean`)
    ]

    `language` is the language used to render the email. If None the language
    of the currently-logged in user (that is, the user sending the email) will
    be used.

    Returns a boolean indicating whether the email was sent successfully.
    """

    # add some helpers and microconfig subsitutions
    if 'display_name' in param_dict:
        param_dict['course_name'] = param_dict['display_name']

    param_dict['site_name'] = configuration_helpers.get_value(
        'SITE_NAME',
        param_dict['site_name']
    )

    subject = None
    message = None

    # see if there is an activation email template definition available as configuration,
    # if so, then render that
    message_type = param_dict['message']

    email_template_dict = {
        'ilt_request_updated': (
            'emails/ilt_request_update_email_subject.txt',
            'emails/ilt_request_update_email_message.txt',
            'emails/ilt_request_update_email_html_message.txt'
        ),
        'ilt_session_changed': (
            'emails/ilt_session_changed_email_subject.txt',
            'emails/ilt_session_changed_email_message.txt',
            'emails/ilt_session_changed_email_html_message.txt'
        ),
        'ilt_hotel_booking_check': (
            'emails/ilt_hotel_booking_check_subject.txt',
            'emails/ilt_hotel_booking_check_message.txt',
            'emails/ilt_hotel_booking_check_html_message.txt'
        ),
        'ilt_hotel_cancel': (
            'emails/ilt_hotel_cancel_email_subject.txt',
            'emails/ilt_hotel_cancel_email_message.txt',
            'emails/ilt_hotel_cancel_email_html_message.txt'
        ),
        'ilt_batch_unenroll': (
            'emails/ilt_batch_unenroll_email_subject.txt',
            'emails/ilt_batch_unenroll_email_message.txt',
            'emails/ilt_batch_unenroll_email_html_message.txt'
        ),
        'ilt_self_unenroll': (
            'emails/ilt_self_unenroll_email_subject.txt',
            'emails/ilt_self_unenroll_email_message.txt',
            'emails/ilt_self_unenroll_email_html_message.txt'
        ),
        'ilt_refused': (
            'emails/ilt_refused_email_subject.txt',
            'emails/ilt_refused_email_message.txt',
            'emails/ilt_refused_email_html_message.txt'
        ),
        'ilt_hotel_updated': (
            'emails/ilt_hotel_updated_email_subject.txt',
            'emails/ilt_hotel_updated_email_message.txt',
            'emails/ilt_hotel_updated_email_html_message.txt'
        ),
        'ilt_validate': (
            'emails/ilt_validate_email_subject.txt',
            'emails/ilt_validate_email_message.txt',
            'emails/ilt_validate_email_html_message.txt'
        ),
        'ilt_follow_up': (
            'emails/ilt_follow_up_email_subject.txt',
            'emails/ilt_follow_up_email_message.txt',
            'emails/ilt_follow_up_email_html_message.txt'
        ),
        'ilt_confirmed': (
            'emails/ilt_confirmed_email_subject.txt',
            'emails/ilt_confirmed_email_message.txt',
            'emails/ilt_confirmed_email_html_message.txt'
        ),
        'ilt_enrolled': (
            'emails/ilt_enrolled_email_subject.txt',
            'emails/ilt_enrolled_email_message.txt',
            'emails/ilt_enrolled_email_html_message.txt'
        ),
        'ilt_unenrolled': (
            'emails/ilt_unenrolled_email_subject.txt',
            'emails/ilt_unenrolled_email_message.txt',
            'emails/ilt_unenrolled_email_html_message.txt'
        ),
        'ilt_session_canceled': (
            'emails/ilt_session_canceled_email_subject.txt',
            'emails/ilt_session_canceled_email_message.txt',
            'emails/ilt_session_canceled_email_html_message.txt'
        ),
        'ilt_session_time_changed': (
            'emails/ilt_session_time_changed_email_subject.txt',
            'emails/ilt_session_time_changed_email_message.txt',
            'emails/ilt_session_time_changed_email_html_message.txt'
        ),
        'ilt_virtual_session_hourly_reminder': (
            'emails/ilt_virtual_session_hourly_reminder_email_subject.txt',
            'emails/ilt_virtual_session_hourly_reminder_email_message.txt',
            'emails/ilt_virtual_session_hourly_reminder_email_html_message.txt'
        ),
        'ilt_virtual_session_daily_reminder': (
            'emails/ilt_virtual_session_daily_reminder_email_subject.txt',
            'emails/ilt_virtual_session_daily_reminder_email_message.txt',
            'emails/ilt_virtual_session_daily_reminder_email_html_message.txt'
        ),
        'allowed_enroll': (
            'emails/enroll_email_allowedsubject.txt',
            'emails/enroll_email_allowedmessage.txt',
            'emails/enroll_email_allowed_html_message.txt'
        ),
        'enrolled_enroll': (
            'emails/enroll_email_enrolledsubject.txt',
            'emails/enroll_email_enrolledmessage.txt',
            'emails/enroll_email_enrolled_html_message.txt'
        ),
        'allowed_unenroll': (
            'emails/unenroll_email_subject.txt',
            'emails/unenroll_email_allowedmessage.txt',
            'emails/unenroll_email_allowed_html_message.txt',
        ),
        'enrolled_unenroll': (
            'emails/unenroll_email_subject.txt',
            'emails/unenroll_email_enrolledmessage.txt',
            'emails/unenroll_email_enrolled_html_message.txt',
        ),
        'add_beta_tester': (
            'emails/add_beta_tester_email_subject.txt',
            'emails/add_beta_tester_email_message.txt',
            'emails/add_beta_tester_email_html_message.txt'
        ),
        'remove_beta_tester': (
            'emails/remove_beta_tester_email_subject.txt',
            'emails/remove_beta_tester_email_message.txt',
            'emails/remove_beta_tester_email_html_message.txt'
        ),
        'account_creation_and_enrollment': (
            'emails/enroll_email_enrolledsubject.txt',
            'emails/account_creation_and_enroll_emailMessage.txt',
            'emails/account_creation_and_enroll_email_html_Message.txt'
        ),
        'waiver_request': (
            'emails/waiver_request_subject.txt',
            'emails/waiver_request_message.txt',
            'emails/waiver_request_html_message.txt'
        ),
        'waiver_request_approved': (
            'emails/waiver_request_accepted_subject.txt',
            'emails/waiver_request_accepted_message.txt',
            'emails/waiver_request_accepted_html_message.txt'
        ),
        'waiver_request_denied': (
            'emails/waiver_request_denied_subject.txt',
            'emails/waiver_request_denied_message.txt',
            'emails/waiver_request_denied_html_message.txt'
        ),
        'bulk_enroll': (
            'emails/bulk_enroll_subject.txt',
            'emails/bulk_enroll_message.txt',
            'emails/bulk_enroll_html_message.txt'
        ),
        'bulk_unenroll': (
            'emails/bulk_unenroll_subject.txt',
            'emails/bulk_unenroll_message.txt',
            'emails/bulk_unenroll_html_message.txt'
        ),
        'program_enrolled': (
            'emails/program_email_enrolledsubject.txt',
            'emails/program_email_enrolledmessage.txt',
            'emails/program_email_enrolled_html_message.txt'
        ),
        'program_allowed_enroll': (
            'emails/program_enroll_email_allowedsubject.txt',
            'emails/program_enroll_email_allowedmessage.txt',
            'emails/program_enroll_email_allowed_html_message.txt'
        ),
        'program_enrolled_unenroll': (
            'emails/program_unenroll_email_subject.txt',
            'emails/program_unenroll_email_enrolledmessage.txt',
            'emails/program_unenroll_email_enrolled_html_message.txt',
        ),
        'program_allowed_unenroll': (
            'emails/program_unenroll_email_subject.txt',
            'emails/program_unenroll_email_allowedmessage.txt',
            'emails/program_unenroll_email_allowed_html_message.txt',
        ),
    }

    subject_template, message_template, html_message_template = email_template_dict.get(
        message_type, (None, None, None))
    if subject_template is not None and message_template is not None:
        subject, message = render_message_to_string(
            subject_template, message_template, param_dict, language=language
        )

    if html_message_template:
        language = language or configuration_helpers.get_value('LANGUAGE_CODE', settings.LANGUAGE_CODE)
        with override_language(language):
            html_message = render_to_string(html_message_template, param_dict)
    else:
        html_message = None

    if subject and message:
        # Remove leading and trailing whitespace from body
        message = message.strip()

        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())
        from_address = configuration_helpers.get_value(
            'email_from_address',
            settings.DEFAULT_FROM_EMAIL
        )

        send_mail(subject, message, from_address, [student], fail_silently=False, html_message=html_message)


def send_custom_waiver_email(email, param_dict, language=None):
    """
    Construct the email using templates and then send it.
    `email` is the receiver's email address (a `str`),

    `param_dict` is a `dict` with keys
    [
        `site_name`: name given to edX instance (a `str`)
        `registration_url`: url for registration (a `str`)
        `display_name` : display name of a course (a `str`)
        `course_id`: id of course (a `str`)
        `auto_enroll`: user input option (a `str`)
        `course_url`: url of course (a `str`)
        `email_address`: email of student (a `str`)
        `full_name`: student full name (a `str`)
        `message`: type of email to send and template to use (a `str`)
        `is_shib_course`: (a `boolean`)
    ]

    `language` is the language used to render the email. If None the language
    of the currently-logged in user (that is, the user sending the email) will
    be used.

    Returns a boolean indicating whether the email was sent successfully.
    """

    # add some helpers and microconfig subsitutions
    if 'display_name' in param_dict:
        param_dict['course_name'] = param_dict['display_name']

    param_dict['site_name'] = configuration_helpers.get_value(
        'SITE_NAME',
        param_dict['site_name']
    )

    subject = None
    message = None
    html_message = None

    # see if there is an activation email template definition available as configuration,
    # if so, then render that
    message_type = param_dict['message']

    email_template_dict = {
        'forced_waiver_request': (
            'emails/waiver_request_subject.txt',
            'emails/forced_waiver_request_message.txt',
            'emails/forced_waiver_request_html.txt'
        ),
    }

    subject_template, message_template, html_template = email_template_dict.get(message_type, (None, None, None))
    if all([subject_template, message_template]):
        subject, message = render_message_to_string(
            subject_template, message_template, param_dict, language=language
        )
        html_message = render_to_string(html_template, param_dict)

    if subject and message:
        # Remove leading and trailing whitespace from body
        message = message.strip()

        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())
        from_address = configuration_helpers.get_value(
            'email_from_address',
            settings.DEFAULT_FROM_EMAIL
        )
        site_theme = SiteTheme.objects.get(id=param_dict['site_theme'])
        theme_dir = site_theme.theme_dir_name
        theme_dir_base = get_theme_base_dir(theme_dir)
        image_path = Path(theme_dir_base) / theme_dir / 'lms/static/images/logo.png'
        image_name = "logo.png"
        send_mail_with_image(subject, message, from_address, [email], fail_silently=False, html_message=html_message,
                             image_path=image_path, image_name=image_name)


def send_mail_with_image(subject, message, from_email, recipient_list, fail_silently=False,
                         auth_user=None, auth_password=None, connection=None, html_message=None,
                         image_path=None, image_name=None):
    connection = connection or get_connection(username=auth_user,
                                              password=auth_password,
                                              fail_silently=fail_silently)
    email_showname = configuration_helpers.get_value('email_from_showname', settings.DEFAULT_FROM_EMAIL_ALIAS)
    from_email = "{0}<{1}>".format(email_showname, from_email)
    mail = EmailMultiAlternatives(subject, message, from_email, recipient_list,
                                  connection=connection)

    if all([html_message, image_path]):
        mail.attach_alternative(html_message, 'text/html')

        # it is important part that ensures embedding of image
        mail.mixed_subtype = 'related'

        with open(image_path, mode='rb') as f:
            image = MIMEImage(f.read())
            mail.attach(image)
            image.add_header('Content-ID', '<{}>'.format(image_name))

    return mail.send()


def render_message_to_string(subject_template, message_template, param_dict, language=None):
    """
    Render a mail subject and message templates using the parameters from
    param_dict and the given language. If language is None, the platform
    default language is used.

    Returns two strings that correspond to the rendered, translated email
    subject and message.
    """
    language = language or configuration_helpers.get_value('LANGUAGE_CODE', settings.LANGUAGE_CODE)
    with override_language(language):
        return get_subject_and_message(subject_template, message_template, param_dict)


def get_subject_and_message(subject_template, message_template, param_dict):
    """
    Return the rendered subject and message with the appropriate parameters.
    """
    subject = render_to_string(subject_template, param_dict)
    message = render_to_string(message_template, param_dict)
    return subject, message


def uses_shib(course):
    """
    Used to return whether course has Shibboleth as the enrollment domain

    Returns a boolean indicating if Shibboleth authentication is set for this course.
    """
    return course.enrollment_domain and course.enrollment_domain.startswith(settings.SHIBBOLETH_DOMAIN_PREFIX)
