"""
This file contains implementation override of SearchFilterGenerator which will allow
    * Filter by all courses in which the user is enrolled in
"""

from search.filter_generator import SearchFilterGenerator

from openedx.core.djangoapps.course_groups.partition_scheme import CohortPartitionScheme
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.core.djangoapps.user_api.partition_schemes import RandomUserPartitionScheme
from student.models import CourseEnrollment

INCLUDE_SCHEMES = [CohortPartitionScheme, RandomUserPartitionScheme, ]
SCHEME_SUPPORTS_ASSIGNMENT = [RandomUserPartitionScheme, ]


class LmsSearchFilterGenerator(SearchFilterGenerator):
    """ SearchFilterGenerator for LMS Search """

    def _enrollments_for_user(self, user):
        """Return the specified user's course enrollments.

            ***
                Note: if u wanna add a course enrollment data cache.
                So, please support data expiration mechanism
            ***

        """
        return CourseEnrollment.enrollments_for_user(user)

    def field_dictionary(self, **kwargs):
        """ add course if provided otherwise add courses in which the user is enrolled in """
        field_dictionary = super(LmsSearchFilterGenerator, self).field_dictionary(**kwargs)
        if not kwargs.get('user'):
            field_dictionary['course'] = []
        elif not kwargs.get('course_id'):
            user_enrollments = self._enrollments_for_user(kwargs['user'])
            field_dictionary['course'] = [unicode(enrollment.course_id) for enrollment in user_enrollments]

        # if we have an org filter, only include results for these orgs
        course_org_filter = configuration_helpers.get_current_site_orgs()
        if course_org_filter:
            field_dictionary['org'] = course_org_filter

        return field_dictionary

    def exclude_dictionary(self, **kwargs):
        """
            Exclude any courses defined outside the current org.
        """
        exclude_dictionary = super(LmsSearchFilterGenerator, self).exclude_dictionary(**kwargs)
        course_org_filter = configuration_helpers.get_current_site_orgs()
        # If we have a course filter we are ensuring that we only get those courses above
        if not course_org_filter:
            org_filter_out_set = configuration_helpers.get_all_orgs()
            if org_filter_out_set:
                exclude_dictionary['org'] = list(org_filter_out_set)

        return exclude_dictionary


class LmsProgramSearchFilterGenerator(SearchFilterGenerator):
    """ SearchFilterGenerator for LMS Search """

    def field_dictionary(self, **kwargs):
        """Filter programs by field `status` in status `active`
        """
        field_dictionary = super(LmsProgramSearchFilterGenerator, self).field_dictionary(**kwargs)

        # Only fetch published programs
        field_dictionary['status'] = ['active']
        # Only fetch programs which related with specified partners
        partners = configuration_helpers.get_value('course_org_filter', [])
        if not isinstance(partners, list) and partners:
            partners = [partners]
        field_dictionary['partner'] = partners

        return field_dictionary

    def exclude_dictionary(self, **kwargs):
        """
            Exclude any programs defined outside the current org.

            - Exclude : programs with "Private Visibility"

        """
        return {'visibility': [1, 2]}
