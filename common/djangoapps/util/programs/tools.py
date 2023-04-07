from django.contrib.auth import get_user_model

from lms.djangoapps.program_enrollments.constants import ProgramEnrollmentStatuses
from lms.djangoapps.program_enrollments.models import ProgramEnrollment
from openedx.core.djangoapps.catalog.models import CatalogIntegration
from util.programs import SiteProgramsLoader


class ProgramCoursesKeysStatistics(object):
    """Statistics for published programs

        *** Download all program from Service discovery ***

    """
    def __init__(self, published_only=True):
        """Constructor

            @param published_only:        load `active/retired` programs Only.
            @type published_only:         boolean
        """
        service_user = get_user_model().objects.get(
            username=CatalogIntegration.current().service_username
        )

        valid_status_list = ('active', 'retired') \
            if published_only \
            else \
            ('active', 'retired', 'unpublished')

        # Generating dict<program_uuid: course_keys_set>
        self._program_uuids_2_course_keys = {
            program['uuid']: {
                course_run['key']
                for course in program.get('courses', []) for course_run in course['course_runs']
            }
            for program in SiteProgramsLoader(
                service_user
            ).get_programs().values()
            if program.get('status') in valid_status_list
        }

    def get_programs_courses_keys_by_user_id(self, user):
        """Return program uuid : courses keys mapping

            @param program_uuid:        user
            @type program_uuid:         object
            @return:                    dict<program_uuid: courses keys>
            @rtype:                     dict

        """
        # Get all programs uuids (enrolled)
        program_uuids = [
            str(enrollment['program_uuid'])
            for enrollment in ProgramEnrollment.objects.values(
                'program_uuid'
            ).filter(
                user=user,
                status__in=[
                    ProgramEnrollmentStatuses.ENROLLED,
                    ProgramEnrollmentStatuses.PENDING
                ],
            ).all()
        ]
        # Return dict<program_uuid: course_keys_set>
        return {
            program_uuid: self._program_uuids_2_course_keys[program_uuid]
            for program_uuid in program_uuids
            if program_uuid in self._program_uuids_2_course_keys
        }

    def count_completed_programs_by_user(self, user, completed_courses_keys):
        """Return completed programs number for user

            @param program_uuid:            user
            @type program_uuid:             object
            @param completed_courses_keys:  courses keys
            @type completed_courses_keys:   tuple/set/list
            @return:                        completed program number of user
            @rtype:                         integer
        """
        completed_programs_number = 0
        completed_courses_keys = completed_courses_keys \
            if isinstance(object, set) \
            else set(completed_courses_keys)
        user_programs_courses_keys = self.get_programs_courses_keys_by_user_id(user)

        for _, program_courses_keys_set in user_programs_courses_keys.items():
            program_courses_number = len(program_courses_keys_set)
            courses_intersection = program_courses_keys_set & completed_courses_keys

            if program_courses_number == len(courses_intersection):
                completed_programs_number += 1

        return completed_programs_number
