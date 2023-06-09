"""
This module contains tasks for asynchronous execution of grade updates.
"""

from logging import getLogger

import six
from celery import task
from celery_utils.persist_on_failure import LoggedPersistOnFailureTask
from courseware.model_data import get_score
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.utils import DatabaseError

from lms.djangoapps.course_blocks.api import get_course_blocks
from lms.djangoapps.grades.config.models import ComputeGradesSetting
from opaque_keys.edx.keys import CourseKey, UsageKey
from opaque_keys.edx.locator import CourseLocator
from openedx.core.djangoapps.monitoring_utils import set_custom_metric, set_custom_metrics_for_course_key
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from student.models import CourseEnrollment
from submissions import api as sub_api
from track.event_transaction_utils import set_event_transaction_id, set_event_transaction_type
from django.core.mail import send_mail
from util.date_utils import from_timestamp
from xmodule.modulestore.django import modulestore

from .config.waffle import DISABLE_REGRADE_ON_POLICY_CHANGE, waffle
from .constants import ScoreDatabaseTableEnum
from .course_grade_factory import CourseGradeFactory
from .exceptions import DatabaseNotReadyError
from .services import GradesService
from .signals.signals import SUBSECTION_SCORE_CHANGED
from .subsection_grade_factory import SubsectionGradeFactory
from .transformer import GradesTransformer

log = getLogger(__name__)

COURSE_GRADE_TIMEOUT_SECONDS = 1200
KNOWN_RETRY_ERRORS = (  # Errors we expect occasionally, should be resolved on retry
    DatabaseError,
    ValidationError,
    DatabaseNotReadyError,
)
RECALCULATE_GRADE_DELAY_SECONDS = 2  # to prevent excessive _has_db_updated failures. See TNL-6424.
RETRY_DELAY_SECONDS = 40
SUBSECTION_GRADE_TIMEOUT_SECONDS = 300


@task(base=LoggedPersistOnFailureTask, routing_key=settings.POLICY_CHANGE_GRADES_ROUTING_KEY)
def compute_all_grades_for_course(**kwargs):
    """
    Compute grades for all students in the specified course.
    Kicks off a series of compute_grades_for_course_v2 tasks
    to cover all of the students in the course.
    """
    if waffle().is_enabled(DISABLE_REGRADE_ON_POLICY_CHANGE):
        log.debug('Grades: ignoring policy change regrade due to waffle switch')
    else:
        course_key = CourseKey.from_string(kwargs.pop('course_key'))
        for course_key_string, offset, batch_size in _course_task_args(course_key=course_key, **kwargs):
            kwargs.update({
                'course_key': course_key_string,
                'offset': offset,
                'batch_size': batch_size,
            })
            compute_grades_for_course_v2.apply_async(
                kwargs=kwargs, routing_key=settings.POLICY_CHANGE_GRADES_ROUTING_KEY
            )


@task(
    bind=True,
    base=LoggedPersistOnFailureTask,
    default_retry_delay=RETRY_DELAY_SECONDS,
    max_retries=1,
    time_limit=COURSE_GRADE_TIMEOUT_SECONDS,
    rate_limit=settings.POLICY_CHANGE_TASK_RATE_LIMIT,
)
def compute_grades_for_course_v2(self, **kwargs):
    """
    Compute grades for a set of students in the specified course.

    The set of students will be determined by the order of enrollment date, and
    limited to at most <batch_size> students, starting from the specified
    offset.

    TODO: Roll this back into compute_grades_for_course once all workers have
    the version with **kwargs.
    """
    if 'event_transaction_id' in kwargs:
        set_event_transaction_id(kwargs['event_transaction_id'])

    if 'event_transaction_type' in kwargs:
        set_event_transaction_type(kwargs['event_transaction_type'])

    try:
        return compute_grades_for_course(kwargs['course_key'], kwargs['offset'], kwargs['batch_size'])
    except Exception as exc:
        raise self.retry(kwargs=kwargs, exc=exc)


@task(base=LoggedPersistOnFailureTask)
def compute_grades_for_course(course_key, offset, batch_size, **kwargs):  # pylint: disable=unused-argument
    """
    Compute and save grades for a set of students in the specified course.

    The set of students will be determined by the order of enrollment date, and
    limited to at most <batch_size> students, starting from the specified
    offset.
    """
    course_key = CourseKey.from_string(course_key)
    enrollments = CourseEnrollment.objects.filter(course_id=course_key).order_by('created')
    student_iter = (enrollment.user for enrollment in enrollments[offset:offset + batch_size])
    for result in CourseGradeFactory().iter(
            users=student_iter, course_key=course_key, force_update=True, clear_request_cache=True):
        if result.error is not None:
            raise result.error


@task(
    bind=True,
    base=LoggedPersistOnFailureTask,
    time_limit=SUBSECTION_GRADE_TIMEOUT_SECONDS,
    max_retries=2,
    default_retry_delay=RETRY_DELAY_SECONDS,
    routing_key=settings.POLICY_CHANGE_GRADES_ROUTING_KEY
)
def recalculate_course_and_subsection_grades_for_user(self, **kwargs):  # pylint: disable=unused-argument
    """
    Recalculates the course grade and all subsection grades
    for the given ``user`` and ``course_key`` keyword arguments.
    """
    user_id = kwargs.get('user_id')
    course_key_str = kwargs.get('course_key')

    if not (user_id or course_key_str):
        message = 'recalculate_course_and_subsection_grades_for_user missing "user" or "course_key" kwargs from {}'
        raise Exception(message.format(kwargs))

    user = User.objects.get(id=user_id)
    course_key = CourseKey.from_string(course_key_str)

    previous_course_grade = CourseGradeFactory().read(user, course_key=course_key)
    if previous_course_grade and previous_course_grade.attempted:
        CourseGradeFactory().update(
            user=user,
            course_key=course_key,
            force_update_subsections=True
        )


@task(
    bind=True,
    base=LoggedPersistOnFailureTask,
    time_limit=SUBSECTION_GRADE_TIMEOUT_SECONDS,
    max_retries=3,
    default_retry_delay=RETRY_DELAY_SECONDS,
    routing_key=settings.RECALCULATE_GRADES_ROUTING_KEY
)
def recalculate_subsection_grade_v3(self, **kwargs):
    """
    Latest version of the recalculate_subsection_grade task.  See docstring
    for _recalculate_subsection_grade for further description.
    """
    _recalculate_subsection_grade(self, **kwargs)


@task(
    bind=True,
    base=LoggedPersistOnFailureTask,
    time_limit=SUBSECTION_GRADE_TIMEOUT_SECONDS,
    max_retries=2,
    default_retry_delay=RETRY_DELAY_SECONDS,
    routing_key=settings.RECALCULATE_PROGRESS_ROUTING_KEY
)
def update_course_progress(self, **kwargs):
    """
    a celery task to batch update learners' course progress,
    this task is called after gradebook edit
    """
    users = kwargs.get('users')
    course_id = kwargs.get('course_id')
    course_key = CourseKey.from_string(course_id)
    for u in users:
        user = User.objects.get(id=u)
        CourseGradeFactory().update_course_completion_percentage(course_key, user)


@task(
    bind=True,
    base=LoggedPersistOnFailureTask,
    time_limit=SUBSECTION_GRADE_TIMEOUT_SECONDS,
    max_retries=2,
    default_retry_delay=RETRY_DELAY_SECONDS,
    routing_key=settings.RECALCULATE_GRADES_ROUTING_KEY
)
def send_grade_override_email(self, **kwargs):
    email_service_enabled = kwargs['email_service_enabled']
    from_address = kwargs['from_address']
    student_info = kwargs['student_info']
    transcript = kwargs['transcript_link']
    course_name = kwargs['course_name']
    platform_name = kwargs['platform_name']

    if not email_service_enabled:
        return

    from lms.djangoapps.instructor.enrollment import render_message_to_string
    for student in student_info:
        sections = [] if student['whole'] else student['sections']
        params = {'name': student['name'],
                  'transcript': transcript,
                  'sections': sections,
                  'platform_name': platform_name,
                  'course_name': course_name,
                  'score': student['total']}

        subject, message = render_message_to_string(
            'emails/manually_change_grade_email_subject.txt',
            'emails/manually_change_grade_email_message.txt',
            params
        )

        subject = subject.strip('\n')
        try:
            log.info(
                u'Sending course/section - complete email to {email}'.format(email=student['email'])
            )
            send_mail(
                subject, message, from_address, [student['email']], fail_silently=False)
        except Exception as e:
            log.error(
                u'Failed to send email to {email}, Reason: {reason}'.format(
                    email=student['email'],
                    reason=e
                )
            )


@task(
    bind=True,
    base=LoggedPersistOnFailureTask,
    time_limit=SUBSECTION_GRADE_TIMEOUT_SECONDS,
    max_retries=2,
    default_retry_delay=RETRY_DELAY_SECONDS,
    routing_key=settings.RECALCULATE_PROGRESS_ROUTING_KEY
)
def calculate_course_progress(self, **kwargs):
    """
    celery task to update course progress for a single learner
    this task will be called after a BlockCompletion.post_save
    """
    course_id = kwargs.get('course_id')
    user_id = kwargs.get('user_id')
    course_key = CourseKey.from_string(course_id)
    user = User.objects.get(id=user_id)
    CourseGradeFactory().update_course_completion_percentage(course_key, user)


def _recalculate_subsection_grade(self, **kwargs):
    """
    Updates a saved subsection grade.

    Keyword Arguments:
        user_id (int): id of applicable User object
        anonymous_user_id (int, OPTIONAL): Anonymous ID of the User
        course_id (string): identifying the course
        usage_id (string): identifying the course block
        only_if_higher (boolean): indicating whether grades should
            be updated only if the new raw_earned is higher than the
            previous value.
        expected_modified_time (serialized timestamp): indicates when the task
            was queued so that we can verify the underlying data update.
        score_deleted (boolean): indicating whether the grade change is
            a result of the problem's score being deleted.
        event_transaction_id (string): uuid identifying the current
            event transaction.
        event_transaction_type (string): human-readable type of the
            event at the root of the current event transaction.
        score_db_table (ScoreDatabaseTableEnum): database table that houses
            the changed score. Used in conjunction with expected_modified_time.
    """
    try:
        course_key = CourseLocator.from_string(kwargs['course_id'])
        scored_block_usage_key = UsageKey.from_string(kwargs['usage_id']).replace(course_key=course_key)

        set_custom_metrics_for_course_key(course_key)
        set_custom_metric('usage_id', unicode(scored_block_usage_key))

        # The request cache is not maintained on celery workers,
        # where this code runs. So we take the values from the
        # main request cache and store them in the local request
        # cache. This correlates model-level grading events with
        # higher-level ones.
        set_event_transaction_id(kwargs.get('event_transaction_id'))
        set_event_transaction_type(kwargs.get('event_transaction_type'))

        # Verify the database has been updated with the scores when the task was
        # created. This race condition occurs if the transaction in the task
        # creator's process hasn't committed before the task initiates in the worker
        # process.
        has_database_updated = _has_db_updated_with_new_score(self, scored_block_usage_key, **kwargs)

        if not has_database_updated:
            raise DatabaseNotReadyError

        _update_subsection_grades(
            course_key,
            scored_block_usage_key,
            kwargs['only_if_higher'],
            kwargs['user_id'],
            kwargs['score_deleted'],
            kwargs.get('force_update_subsections', False),
        )
    except Exception as exc:
        if not isinstance(exc, KNOWN_RETRY_ERRORS):
            log.info("tnl-6244 grades unexpected failure: {}. task id: {}. kwargs={}".format(
                repr(exc),
                self.request.id,
                kwargs,
            ))
        raise self.retry(kwargs=kwargs, exc=exc)


def _has_db_updated_with_new_score(self, scored_block_usage_key, **kwargs):
    """
    Returns whether the database has been updated with the
    expected new score values for the given problem and user.
    """
    if kwargs['score_db_table'] == ScoreDatabaseTableEnum.courseware_student_module:
        score = get_score(kwargs['user_id'], scored_block_usage_key)
        found_modified_time = score.modified if score is not None else None

    elif kwargs['score_db_table'] == ScoreDatabaseTableEnum.submissions:
        score = sub_api.get_score(
            {
                "student_id": kwargs['anonymous_user_id'],
                "course_id": unicode(scored_block_usage_key.course_key),
                "item_id": unicode(scored_block_usage_key),
                "item_type": scored_block_usage_key.block_type,
            }
        )
        found_modified_time = score['created_at'] if score is not None else None
    else:
        assert kwargs['score_db_table'] == ScoreDatabaseTableEnum.overrides
        score = GradesService().get_subsection_grade_override(
            user_id=kwargs['user_id'],
            course_key_or_id=kwargs['course_id'],
            usage_key_or_id=kwargs['usage_id']
        )
        found_modified_time = score.modified if score is not None else None

    if score is None:
        # score should be None only if it was deleted.
        # Otherwise, it hasn't yet been saved.
        db_is_updated = kwargs['score_deleted']
    else:
        db_is_updated = found_modified_time >= from_timestamp(kwargs['expected_modified_time'])

    if not db_is_updated:
        log.info(
            u"Grades: tasks._has_database_updated_with_new_score is False. Task ID: {}. Kwargs: {}. Found "
            u"modified time: {}".format(
                self.request.id,
                kwargs,
                found_modified_time,
            )
        )

    return db_is_updated


def _update_subsection_grades(
        course_key, scored_block_usage_key, only_if_higher, user_id, score_deleted, force_update_subsections=False):
    """
    A helper function to update subsection grades in the database
    for each subsection containing the given block, and to signal
    that those subsection grades were updated.
    """
    student = User.objects.get(id=user_id)
    store = modulestore()
    with store.bulk_operations(course_key):
        course_structure = get_course_blocks(student, store.make_course_usage_key(course_key))
        subsections_to_update = course_structure.get_transformer_block_field(
            scored_block_usage_key,
            GradesTransformer,
            'subsections',
            set(),
        )

        course = store.get_course(course_key, depth=0)
        subsection_grade_factory = SubsectionGradeFactory(student, course, course_structure)

        for subsection_usage_key in subsections_to_update:
            if subsection_usage_key in course_structure:
                subsection_grade = subsection_grade_factory.update(
                    course_structure[subsection_usage_key],
                    only_if_higher,
                    score_deleted,
                    force_update_subsections,
                )
                SUBSECTION_SCORE_CHANGED.send(
                    sender=None,
                    course=course,
                    course_structure=course_structure,
                    user=student,
                    subsection_grade=subsection_grade,
                )


def _course_task_args(course_key, **kwargs):
    """
    Helper function to generate course-grade task args.
    """
    from_settings = kwargs.pop('from_settings', True)
    enrollment_count = CourseEnrollment.objects.filter(course_id=course_key).count()
    if enrollment_count == 0:
        log.warning("No enrollments found for {}".format(course_key))

    if from_settings is False:
        batch_size = kwargs.pop('batch_size', 100)
    else:
        batch_size = ComputeGradesSetting.current().batch_size

    for offset in six.moves.range(0, enrollment_count, batch_size):
        yield (six.text_type(course_key), offset, batch_size)
