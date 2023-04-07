"""
Python API functions related to writing program enrollments.

Outside of this subpackage, import these functions
from `lms.djangoapps.program_enrollments.api`.
"""


import logging

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from course_modes.models import CourseMode
from student.models import CourseEnrollment, NonExistentCourseError

from ..constants import ProgramCourseEnrollmentStatuses
from ..constants import ProgramCourseOperationStatuses as ProgramCourseOpStatuses
from ..constants import ProgramEnrollmentStatuses
from ..constants import ProgramOperationStatuses as ProgramOpStatuses
from ..models import ProgramCourseEnrollment, ProgramEnrollment
from .reading import fetch_program_course_enrollments_by_students, fetch_program_enrollments

logger = logging.getLogger(__name__)


def write_program_enrollment(program_uuid, enrollment_requests, create, update):
    """
    Create/update a program enrollment for a student.

    Arguments:
        program_uuid (UUID|str)
        enrollment_requests (dict): dict in the form:
            * 'username': str
            * 'status': str from ProgramEnrollmentStatuses
        create (bool): non-existent enrollments will be created iff `create`,
            otherwise they will be skipped as 'duplicate'.
        update (bool): existing enrollments will be updated iff `update`,
            otherwise they will be skipped as 'not-in-program'

    At least one of `create` or `update` must be True.

    Returns: dict[str: str]
        Mapping of user name to strings from ProgramOperationStatuses.
    """
    if not (create or update):
        raise ValueError("At least one of (create, update) must be True")

    username = enrollment_requests.get('username')
    status = enrollment_requests.get('status')
    if not username or not status:
        raise ValueError('please provide arguments: `email` and `status`')

    # Fetch existing program enrollments.
    user = User.objects.get(username=username)
    existing_enrollment = fetch_program_enrollments(
        program_uuid=program_uuid, users=[user.id]
    )

    # For each enrollment request, try to create/update:
    # * For creates, build up list `to_save`, which we will bulk-create afterwards.
    # * For updates, do them in place.
    # Update `results` with the new status or an error status for each operation.
    result = {}
    to_save = []

    if status not in ProgramEnrollmentStatuses.__ALL__:
        raise ValidationError('Invalid enrollment status')
    else:
        if existing_enrollment:
            if not update:
                raise ValidationError('Conflict: user already has been enrolled.')
            else:
                result[username] = change_program_enrollment_status(
                    existing_enrollment.first(), status
                )
        else:
            if not create:
                raise ValidationError('Unenrolled: User need to been enrolled first.')
            else:
                new_enrollment = create_program_enrollment(
                    program_uuid=program_uuid,
                    user=user,
                    status=status
                )
                to_save.append(new_enrollment)
                result[username] = new_enrollment.status

    return result


def create_program_enrollment(
        program_uuid,
        user,
        status,
        save=True,
):
    """
    Create a program enrollment.

    Arguments:
        program_uuid (UUID|str)
        user (User)
        status (str): from ProgramEnrollmentStatuses
        save (bool): Whether to save the created ProgamEnrollment.
            Defaults to True. One may set this to False in order to
            bulk-create the enrollments.

    Returns: ProgramEnrollment
    """
    if not user:
        raise ValueError("user should be empty")
    program_enrollment = ProgramEnrollment(
        program_uuid=program_uuid,
        user=user,
        status=status,
    )
    if save:
        program_enrollment.save()
    return program_enrollment


def change_program_enrollment_status(program_enrollment, new_status):
    """
    Update a program enrollment with a new status.

    Arguments:
        program_enrollment (ProgramEnrollment)
        status (str): from ProgramCourseEnrollmentStatuses

    Returns: str
        String from ProgramOperationStatuses.
    """
    if new_status not in ProgramEnrollmentStatuses.__ALL__:
        return ProgramOpStatuses.INVALID_STATUS
    program_enrollment.status = new_status
    program_enrollment.save()
    return program_enrollment.status


def write_program_courses_enrollments(
        program_uuid,
        course_keys,
        enrollment_requests,
        create,
        update,
):
    """
    Bulk create/update a set of program-courses enrollments.

    Arguments:
        program_uuid (UUID|str)
        enrollment_requests (dict): dict in the form:
            * 'username': str
            * 'status': str from ProgramCourseEnrollmentStatuses
        create (bool): non-existent enrollments will be created iff `create`,
            otherwise they will be skipped as 'duplicate'.
        update (bool): existing enrollments will be updated iff `update`,
            otherwise they will be skipped as 'not-in-program'

    At least one of `create` or `update` must be True.

    Returns: dict[str: str]
        Mapping of user keys to strings from ProgramCourseOperationStatuses.
    """
    if not (create or update):
        raise ValueError("At least one of (create, update) must be True")

    username = enrollment_requests.get('username')
    status = enrollment_requests.get('status')
    if not username or status not in ProgramCourseEnrollmentStatuses.__ALL__:
        raise ValueError('please provide valid arguments: `username` and `status` : {}'.format(enrollment_requests))

    # Fetch enrollments regardless of anchored Program Enrollments
    user = User.objects.filter(username=username).first()
    existing_course_enrollments = fetch_program_course_enrollments_by_students(
        users=[user.id],
        course_keys=course_keys,
        program_uuids=[program_uuid]
    ).select_related('program_enrollment')

    program_enrollment = fetch_program_enrollments(
        program_uuid=program_uuid,
        users=[user.id],
    ).first()

    existing_course_enrollment_keys = {
        course_enrollment.course_key: course_enrollment
        for course_enrollment in existing_course_enrollments
    }

    # For each enrollment request, try to create/update. ProgramCourseEnrollment
    # For creates, build up list `to_save`, which we will bulk-create afterwards.
    # For updates, do them in place in order to preserve history records.
    # For each operation, update `results` with the new status or an error status.
    results = {}
    created_enrollments = []
    updated_enrollments = []
    for course_key in course_keys:
        course_key_str = str(course_key)
        if course_key in existing_course_enrollment_keys:
            course_enrollment = existing_course_enrollment_keys[course_key]
            if not update:
                raise ValidationError('Conflict: courses already has been enrolled.')
            results[course_key_str] = change_program_course_enrollment_status(
                course_enrollment, status
            )
            updated_enrollments.append(course_enrollment)
        else:
            if not create:
                results[course_key_str] = ProgramCourseOpStatuses.NOT_FOUND
                continue
            new_course_enrollment = create_program_course_enrollment(
                program_enrollment,
                course_key,
                status,
                save=True
            )
            results[course_key_str] = new_course_enrollment.status

    # For every created/updated enrollment, check if the user should be course staff.
    # If that enrollment has a linked user, assign the user the course staff role
    # If that enrollment does not have a linked user, create a CourseAccessRoleAssignment
    # for that enrollment.
    written_enrollments = ProgramCourseEnrollment.objects.filter(
        id__in=[enrollment.id for enrollment in created_enrollments + updated_enrollments]
    ).select_related('program_enrollment')

    return results


def create_program_course_enrollment(program_enrollment, course_key, status, save=True):
    """
    Create a program course enrollment.

    If `program_enrollment` is realized (i.e., has a non-null User),
    then also create a course enrollment.

    Arguments:
        program_enrollment (ProgramEnrollment)
        course_key (CourseKey|str)
        status (str): from ProgramCourseEnrollmentStatuses
        save (bool): Whether to save the created ProgamCourseEnrollment.
            Defaults to True. One may set this to False in order to
            bulk-create the enrollments.
            Note that if a CourseEnrollment is created, it will be saved
            regardless of this value.

    Returns: ProgramCourseEnrollment

    Raises: NonExistentCourseError
    """
    course_enrollment = (
        enroll_in_masters_track(program_enrollment.user, course_key, status)
        if program_enrollment.user
        else None
    )
    program_course_enrollment = ProgramCourseEnrollment(
        program_enrollment=program_enrollment,
        course_key=course_key,
        course_enrollment=course_enrollment,
        status=status,
    )
    if save:
        program_course_enrollment.save()
    return program_course_enrollment


def change_program_course_enrollment_status(program_course_enrollment, new_status):
    """
    Update a program course enrollment with a new status.

    If `program_course_enrollment` is realized with a CourseEnrollment,
    then also update that.

    Arguments:
        program_course_enrollment (ProgramCourseEnrollment)
        status (str): from ProgramCourseEnrollmentStatuses

    Returns: str
        String from ProgramOperationCourseStatuses.
    """
    if new_status == program_course_enrollment.status:
        return new_status
    if new_status == ProgramCourseEnrollmentStatuses.ACTIVE:
        active = True
    elif new_status == ProgramCourseEnrollmentStatuses.INACTIVE:
        active = False
    else:
        return ProgramCourseOpStatuses.INVALID_STATUS
    if program_course_enrollment.course_enrollment:
        # The courses are not unenrolled by program unenrollment actions.
        if not program_course_enrollment.course_enrollment.is_active:
            program_course_enrollment.course_enrollment.activate()
        # else:
        #     program_course_enrollment.course_enrollment.deactivate()
    program_course_enrollment.status = new_status
    program_course_enrollment.save()
    return program_course_enrollment.status


def enroll_in_masters_track(user, course_key, status):
    """
    Ensure that the user is enrolled in the Master's track of course.
    Either creates or updates a course enrollment.

    Arguments:
        user (User)
        course_key (CourseKey|str)
        status (str): from ProgramCourseEnrollmentStatuses

    Returns: CourseEnrollment

    Raises: NonExistentCourseError
    """
    if status not in ProgramCourseEnrollmentStatuses.__ALL__:
        raise ValueError("invalid ProgramCourseEnrollmentStatus: {}".format(status))
    if CourseEnrollment.is_enrolled(user, course_key):
        course_enrollment = CourseEnrollment.objects.get(
            user=user,
            course_id=course_key,
        )
        if course_enrollment.mode in {CourseMode.AUDIT, CourseMode.HONOR}:
            course_enrollment.mode = CourseMode.PROFESSIONAL#MASTERS
            course_enrollment.save()
            message_template = (
                "Converted course enrollment for user id={} "
                "and course key={} from mode {} to Master's."
            )
            logger.info(
                message_template.format(user.id, course_key, course_enrollment.mode)
            )
        elif course_enrollment.mode != CourseMode.PROFESSIONAL:#MASTERS:
            error_message = (
                "Cannot convert CourseEnrollment to Master's from mode {}. "
                "user id={}, course_key={}."
            ).format(
                course_enrollment.mode, user.id, course_key
            )
            logger.error(error_message)
    else:
        course_enrollment = CourseEnrollment.enroll(
            user,
            course_key,
            mode=CourseMode.PROFESSIONAL,#MASTERS,
            check_access=False,
        )
    if course_enrollment.mode == CourseMode.PROFESSIONAL:#MASTERS:
        if status == ProgramCourseEnrollmentStatuses.INACTIVE:
            course_enrollment.deactivate()
    return course_enrollment
