"""
Python API functions related to reading program enrollments.

Outside of this subpackage, import these functions
from `lms.djangoapps.program_enrollments.api`.
"""


from organizations.models import Organization

from third_party_auth.models import SAMLProviderConfig
from openedx.core.djangoapps.catalog.utils import get_programs

from ..exceptions import (
    BadOrganizationShortNameException,
    ProgramDoesNotExistException,
    ProgramHasNoAuthoringOrganizationException,
    ProviderConfigurationException,
    ProviderDoesNotExistException
)
from ..models import ProgramCourseEnrollment, ProgramEnrollment

_STUDENT_ARG_ERROR_MESSAGE = (
    "user is not provided."
)
_REALIZED_FILTER_ERROR_TEMPLATE = (
    "{} and {} are mutually exclusive; at most one of them may be passed in as True."
)
_STUDENT_LIST_ARG_ERROR_MESSAGE = (
    'user list is empty or None.'
)


def get_program_enrollment(
        program_uuid,
        user=None,
):
    """
    Get a single program enrollment.

    Required arguments:
        * program_uuid (UUID|str)
        * At least one of:
            * user (User)

    Returns: ProgramEnrollment

    Raises: ProgramEnrollment.DoesNotExist, ProgramEnrollment.MultipleObjectsReturned
    """
    if not user:
        raise ValueError(_STUDENT_ARG_ERROR_MESSAGE)
    filters = {
        "user": user,
    }
    return ProgramEnrollment.objects.get(
        program_uuid=program_uuid, **_remove_none_values(filters)
    )


def get_program_course_enrollment(
        program_uuid,
        course_key,
        user=None,
):
    """
    Get a single program-course enrollment.

    Required arguments:
        * program_uuid (UUID|str)
        * course_key (CourseKey|str)
        * At least one of:
            * user (User)

    Returns: ProgramCourseEnrollment

    Raises:
        * ProgramCourseEnrollment.DoesNotExist
        * ProgramCourseEnrollment.MultipleObjectsReturned
    """
    if not user:
        raise ValueError(_STUDENT_ARG_ERROR_MESSAGE)
    filters = {
        "program_enrollment__user": user,
    }
    return ProgramCourseEnrollment.objects.get(
        program_enrollment__program_uuid=program_uuid,
        course_key=course_key,
        **_remove_none_values(filters)
    )


def fetch_program_enrollments(
        program_uuid,
        users=None,
        program_enrollment_statuses=None,
        realized_only=False,
        waiting_only=False,
):
    """
    Fetch program enrollments for a specific program.

    Required argument:
        * program_uuid (UUID|str)

    Optional arguments:
        * users (iterable[User])
        * program_enrollment_statuses (iterable[str])
        * realized_only (bool)
        * waiting_only (bool)

    Optional arguments are used as filtersets if they are not None.
    At most one of (realized_only, waiting_only) may be provided.

    Returns: queryset[ProgramEnrollment]
    """
    if realized_only and waiting_only:
        raise ValueError(
            _REALIZED_FILTER_ERROR_TEMPLATE.format("realized_only", "waiting_only")
        )
    filters = {
        "user__in": users,
        "status__in": program_enrollment_statuses,
    }
    if realized_only:
        filters["user__isnull"] = False
    if waiting_only:
        filters["user__isnull"] = True
    return ProgramEnrollment.objects.filter(
        program_uuid=program_uuid, **_remove_none_values(filters)
    )


def fetch_program_course_enrollments(
        program_uuid,
        course_key,
        users=None,
        program_enrollment_statuses=None,
        program_enrollments=None,
        active_only=False,
        inactive_only=False,
        realized_only=False,
        waiting_only=False,
):
    """
    Fetch program-course enrollments for a specific program and course run.

    Required argument:
        * program_uuid (UUID|str)
        * course_key (CourseKey|str)

    Optional arguments:
        * users (iterable[User])
        * program_enrollment_statuses (iterable[str])
        * program_enrollments (iterable[ProgramEnrollment])
        * active_only (bool)
        * inactive_only (bool)
        * realized_only (bool)
        * waiting_only (bool)

    Optional arguments are used as filtersets if they are not None.
    At most one of (realized_only, waiting_only) may be provided.
    At most one of (active_only, inactive_only) may be provided.

    Returns: queryset[ProgramCourseEnrollment]
    """
    if active_only and inactive_only:
        raise ValueError(
            _REALIZED_FILTER_ERROR_TEMPLATE.format("active_only", "inactive_only")
        )
    if realized_only and waiting_only:
        raise ValueError(
            _REALIZED_FILTER_ERROR_TEMPLATE.format("realized_only", "waiting_only")
        )
    filters = {
        "program_enrollment__user__in": users,
        "program_enrollment__status__in": program_enrollment_statuses,
        "program_enrollment__in": program_enrollments,
    }
    if active_only:
        filters["status"] = "active"
    if inactive_only:
        filters["status"] = "inactive"
    if realized_only:
        filters["program_enrollment__user__isnull"] = False
    if waiting_only:
        filters["program_enrollment__user__isnull"] = True
    return ProgramCourseEnrollment.objects.filter(
        program_enrollment__program_uuid=program_uuid,
        course_key=course_key,
        **_remove_none_values(filters)
    )


def fetch_program_enrollments_by_student(
        user=None,
        program_uuids=None,
        program_enrollment_statuses=None,
        realized_only=False,
        waiting_only=False,
):
    """
    Fetch program enrollments for a specific student.

    Required arguments (at least one must be provided):
        * user (User)

    Optional arguments:
        * provided_uuids (iterable[UUID|str])
        * program_enrollment_statuses (iterable[str])
        * realized_only (bool)
        * waiting_only (bool)

    Optional arguments are used as filtersets if they are not None.
    At most one of (realized_only, waiting_only) may be provided.

    Returns: queryset[ProgramEnrollment]
    """
    if not user:
        raise ValueError(_STUDENT_ARG_ERROR_MESSAGE)
    if realized_only and waiting_only:
        raise ValueError(
            _REALIZED_FILTER_ERROR_TEMPLATE.format("realized_only", "waiting_only")
        )
    filters = {
        "user": user,
        "program_uuid__in": program_uuids,
        "status__in": program_enrollment_statuses,
    }
    if realized_only:
        filters["user__isnull"] = False
    if waiting_only:
        filters["user__isnull"] = True
    return ProgramEnrollment.objects.filter(**_remove_none_values(filters))


def fetch_program_enrollments_by_students(
    users=None,
    program_enrollment_statuses=None,
    realized_only=False,
    waiting_only=False,
):
    """
    Fetch program enrollments for a specific list of students.

    Required arguments (at least one must be provided):
        * users (iterable[User])

    Optional arguments:
        * program_enrollment_statuses (iterable[str])
        * realized_only (bool)
        * waiting_only (bool)

    Optional arguments are used as filtersets if they are not None.

    Returns: queryset[ProgramEnrollment]
    """
    if not users:
        raise ValueError(_STUDENT_LIST_ARG_ERROR_MESSAGE)
    if realized_only and waiting_only:
        raise ValueError(
            _REALIZED_FILTER_ERROR_TEMPLATE.format("realized_only", "waiting_only")
        )
    filters = {
        "user__in": users,
        "status__in": program_enrollment_statuses,
    }
    if realized_only:
        filters["user__isnull"] = False
    if waiting_only:
        filters["user__isnull"] = True
    return ProgramEnrollment.objects.filter(**_remove_none_values(filters))


def fetch_program_course_enrollments_by_students(
        users=None,
        program_uuids=None,
        course_keys=None,
        program_enrollment_statuses=None,
        active_only=False,
        inactive_only=False,
        realized_only=False,
        waiting_only=False,
):
    """
    Fetch program-course enrollments for a specific list of students.

    Required arguments (at least one must be provided):
        * users (iterable[User])

    Optional arguments:
        * provided_uuids (iterable[UUID|str])
        * course_keys (iterable[CourseKey|str])
        * program_enrollment_statuses (iterable[str])
        * realized_only (bool)
        * waiting_only (bool)

    Optional arguments are used as filtersets if they are not None.
    At most one of (realized_only, waiting_only) may be provided.
    At most one of (active_only, inactive_only) may be provided.

    Returns: queryset[ProgramCourseEnrollment]
    """
    if not users:
        raise ValueError(_STUDENT_LIST_ARG_ERROR_MESSAGE)

    if active_only and inactive_only:
        raise ValueError(
            _REALIZED_FILTER_ERROR_TEMPLATE.format("active_only", "inactive_only")
        )
    if realized_only and waiting_only:
        raise ValueError(
            _REALIZED_FILTER_ERROR_TEMPLATE.format("realized_only", "waiting_only")
        )
    filters = {
        "program_enrollment__user__in": users,
        "program_enrollment__program_uuid__in": program_uuids,
        "course_key__in": course_keys,
        "program_enrollment__status__in": program_enrollment_statuses,
    }
    if active_only:
        filters["status"] = "active"
    if inactive_only:
        filters["status"] = "inactive"
    if realized_only:
        filters["program_enrollment__user__isnull"] = False
    if waiting_only:
        filters["program_enrollment__user__isnull"] = True
    return ProgramCourseEnrollment.objects.filter(**_remove_none_values(filters))


def _remove_none_values(dictionary):
    """
    Return a dictionary where key-value pairs with `None` as the value
    are removed.
    """
    return {
        key: value for key, value in dictionary.items() if value is not None
    }


def get_saml_provider_by_org_key(org_key):
    """
    Returns the SAML provider associated with the provided org_key

    Arguments:
        org_key (str)

    Returns: SAMLProvider

    Raises:
        BadOrganizationShortNameException
    """
    try:
        organization = Organization.objects.get(short_name=org_key)
    except Organization.DoesNotExist:
        raise BadOrganizationShortNameException(org_key)  # lint-amnesty, pylint: disable=raise-missing-from
    return get_saml_provider_for_organization(organization)


def get_org_key_for_program(program_uuid):
    """
    Return the key of the first Organization
    administering the given program.

    Arguments:
        program_uuid (UUID|str)

    Returns: org_key (str)

    Raises:
        ProgramDoesNotExistException
        ProgramHasNoAuthoringOrganizationException
    """
    program = get_programs(uuid=program_uuid)
    if program is None:
        raise ProgramDoesNotExistException(program_uuid)
    authoring_orgs = program.get('authoring_organizations')
    org_key = authoring_orgs[0].get('key') if authoring_orgs else None
    if not org_key:
        raise ProgramHasNoAuthoringOrganizationException(program_uuid)
    return org_key


def get_saml_provider_for_organization(organization):
    """
    Return currently configured SAML provider for the given Organization.

    Arguments:
        organization: Organization

    Returns: SAMLProvider

    Raises:
        ProviderDoesNotExistsException
        ProviderConfigurationException
    """
    try:
        provider_config = organization.samlproviderconfig_set.current_set().get(enabled=True)
    except SAMLProviderConfig.DoesNotExist:
        raise ProviderDoesNotExistException(organization)  # lint-amnesty, pylint: disable=raise-missing-from
    except SAMLProviderConfig.MultipleObjectsReturned:
        raise ProviderConfigurationException(organization)  # lint-amnesty, pylint: disable=raise-missing-from
    return provider_config


def get_provider_slug(provider_config):
    """
    Returns slug identifying a SAML provider.

    Arguments:
        provider_config: SAMLProvider

    Returns: str
    """
    return provider_config.provider_id.strip('saml-')
