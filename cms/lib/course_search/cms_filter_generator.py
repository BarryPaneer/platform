"""
This file contains implementation override of SearchFilterGenerator which will allow
    * Filter by all courses in which the user is enrolled in
"""

from search.filter_generator import SearchFilterGenerator

from openedx.core.djangoapps.course_groups.partition_scheme import CohortPartitionScheme
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.core.djangoapps.user_api.partition_schemes import RandomUserPartitionScheme
from student.roles import (
    CourseInstructorRole,
    CourseStaffRole,
    GlobalStaff,
    UserBasedRole,
)
from lms.djangoapps.teams.program_team_roles import ProgramInstructorRole
from lms.djangoapps.teams.program_team_roles import ProgramStaffRoles
from lms.djangoapps.teams.models import ProgramAccessRole
from student.roles import STUDIO_ADMIN_ACCESS_GROUP


INCLUDE_SCHEMES = [CohortPartitionScheme, RandomUserPartitionScheme, ]
SCHEME_SUPPORTS_ASSIGNMENT = [RandomUserPartitionScheme, ]


def _courses_with_user(user):
    """Get all courses that user can access.
    """
    instructor_courses = UserBasedRole(user, CourseInstructorRole.ROLE).courses_with_role()
    staff_courses = UserBasedRole(user, CourseStaffRole.ROLE).courses_with_role()
    all_courses = instructor_courses | staff_courses
    return [course.course_id for course in all_courses if course.course_id]


class CmsSearchFilterGenerator(SearchFilterGenerator):
    """ SearchFilterGenerator for CMS Search """

    _user_access_courses = {}

    def field_dictionary(self, **kwargs):
        """ add course if provided otherwise add courses in which the user is enrolled in """
        field_dictionary = super(CmsSearchFilterGenerator, self).field_dictionary(**kwargs)
        if not kwargs.get('user'):
            field_dictionary['course'] = []
        elif not kwargs.get('course_id'):
            user_access_courses = _courses_with_user(kwargs['user'])
            field_dictionary['course'] = [unicode(course) for course in user_access_courses]

        # if we have an org filter, only include results for these orgs
        course_org_filter = configuration_helpers.get_current_site_orgs()
        if course_org_filter:
            field_dictionary['org'] = course_org_filter

        return field_dictionary

    def exclude_dictionary(self, **kwargs):
        """
            Exclude any courses defined outside the current org.
        """
        exclude_dictionary = super(CmsSearchFilterGenerator, self).exclude_dictionary(**kwargs)
        course_org_filter = configuration_helpers.get_current_site_orgs()
        # If we have a course filter we are ensuring that we only get those courses above
        if not course_org_filter:
            org_filter_out_set = configuration_helpers.get_all_orgs()
            if org_filter_out_set:
                exclude_dictionary['org'] = list(org_filter_out_set)

        return exclude_dictionary


class CmsProgramSearchFilterGenerator(SearchFilterGenerator):
    """ SearchFilterGenerator for CMS Programs Search """
    _user_access_courses = {}

    def _programs_with_user(self, user):
        """Get all program ids that user can access.

            First:
                Only `Studio Super Admin` / `Platform Admin` / `Platform Super Admin` can access programs.

            Note:
                `Studio Super Admin` = `Studio Admin` + `Learning Path Admin` Group

            Access rules as follow:
                1. Platform Admin / Super Admin: could access all programs.
                2. Studio Super Admin: only access his programs.

        """
        if user.is_superuser or user.is_staff:
            return ProgramAccessRole.objects.filter(
                role__in=(
                    ProgramInstructorRole.ROLE,
                    ProgramStaffRoles.ROLE
                )
            ).values_list(
                'program_id', flat=True
            )
        else:
            return ProgramAccessRole.objects.filter(
                role__in=(
                    ProgramInstructorRole.ROLE,
                    ProgramStaffRoles.ROLE
                ),
                user=user
            ).values_list(
                'program_id', flat=True
            )

    def field_dictionary(self, **kwargs):
        """Return programs' UUIDs if the current request user own permission for accessing them"""
        field_dictionary = super(CmsProgramSearchFilterGenerator, self).field_dictionary(**kwargs)

        user_access_programs = self._programs_with_user(
            kwargs['user']
        )
        programs_uuids = {
            str(program_id)
            for program_id in user_access_programs
        }

        field_dictionary['uuid'] = list(programs_uuids)

        # Only fetch programs which related with specified partners
        partners = configuration_helpers.get_value('course_org_filter', [])
        if not isinstance(partners, list) and partners:
            partners = [partners]
        field_dictionary['partner'] = partners

        return field_dictionary

    def exclude_dictionary(self, **kwargs):
        """
            Exclude any programs defined outside the current org.
        """
        return {}
