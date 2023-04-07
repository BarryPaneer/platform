"""
    statistics of prod. programs For LMS pages.

"""

from datetime import datetime
from pytz import UTC

from django.utils.functional import cached_property
from opaque_keys.edx.keys import CourseKey

from course_modes.models import CourseMode
from courseware.models import StudentModule
from entitlements.models import CourseEntitlement
from lms.djangoapps.certificates import api as certificate_api
from lms.djangoapps.program_enrollments.constants import ProgramEnrollmentStatuses
from lms.djangoapps.program_enrollments.models import ProgramEnrollment
from lms.djangoapps.program_enrollments.persistance.programs import PartialProgram
from student.models import CourseEnrollment
from xmodule import course_metadata_utils


class ProgramsCompletionStatistics(object):
    """Utility for gauging a user's progress towards program completion.

        Ref code: openedx/core/djangoapps/programs/utils.py : class ProgramProgressMeter

    """
    def __init__(self, user, count_only=True, programs_limit=None, program_uuid=None, sorted_by_enrollment_date=False, allowed_visibilities=None):
        """Constructor

            @param user:                        The user for which to find programs.
            @type user:                         django.contrib.auth.models.User
            @param count_only:                  count the number only.
            @type count_only:                   boolean
            @param programs_limit:              limit number of queryset
            @type programs_limit:               integer
            @param program_uuid:                program uuid
            @type program_uuid:                 string
            @param sorted_by_enrollment_date:   sort programs list by program enrollment date
            @type sorted_by_enrollment_date:    boolean
            @param allowed_visibilities:        allowed `visibilities` of LPs for querying
            @type allowed_visibilities:         boolean

        """
        self._allowed_visibilities = allowed_visibilities
        self._sorted_by_enrollment_date = sorted_by_enrollment_date
        self._program_uuid = program_uuid \
            if program_uuid else None       # [Filter] query by program uuid only.
        self._programs_limit = programs_limit \
            if programs_limit else 0        # [Filter] Zero. means query all records in collection.

        self._count_only = count_only       # [Format]
        self._user = user                   # [Filter]

        self._programs = None               # [Cache] Programs Records Cache
        self._course_run_ids = set()        # courses uuids of enrollment table
        self._course_uuids = {              # courses uuids of entitlement table
            entitlement.course_uuid
            for entitlement in CourseEntitlement.unexpired_entitlements_for_user(self._user)
        }

        enrollments = list(
            CourseEnrollment.enrollments_for_user(self._user)
        )
        enrollments.sort(
            key=lambda e: e.created, reverse=True
        )

        for enrollment in enrollments:
            # enrollment.course_id is really a CourseKey
            enrollment_course_id = unicode(enrollment.course_id)

            # We can't use dict.keys() for this because the course run ids need to be ordered
            self._course_run_ids.add(enrollment_course_id)

    @property
    def engaged_programs(self):
        """Query programs from MongoDB with filter arguments of courses UUIDs

            Filter Arguments Sample as follow:
                {
                    'courses.course_runs.key':{
                        '$in':[
                            'course-v1:edX+bcs_101+bcs_2021',
                            'course-v1:BarryOrg+bcs_101+bcs_2021',
                            'course-v1:edX+barry_test_course_abc_0+barry_test_course_abc_0',
                            ...
                        ]
                    }
                }

            @return:              generator of class `PartialProgram` instance List.
            @rtype:               generator

        """
        if self._programs:
            return self._programs

        # Setup courses uuids' filter
        courses_ids = self._course_run_ids.union(self._course_uuids)
        _filter = {
            'courses.course_runs.key': {
                '$in': list(courses_ids)
            }
        }
        if self._allowed_visibilities:
            _filter['visibility'] = {'$in': self._allowed_visibilities}
        # Query programs' info of current user by status (`enrolled` & `pending`)
        program_uuid_2_enrollment_date = {
            str(enrollment['program_uuid']): enrollment['modified']
            for enrollment in ProgramEnrollment.objects.values(
                'program_uuid',
                'modified'
            ).filter(
                user=self._user,
                status__in=[
                    ProgramEnrollmentStatuses.ENROLLED,
                    ProgramEnrollmentStatuses.PENDING
                ],
            ).all()
        }
        # Setup programs uuids' filter
        if self._program_uuid:
            _filter['_id'] = self._program_uuid
        else:
            _filter = {
                '_id': {
                    '$in': list(program_uuid_2_enrollment_date.keys())
                }
            }

        def _gen_program_raw_dict(p):
            program_raw_dict = p.to_dict()

            if self._sorted_by_enrollment_date:
                # Adding enrollment date into Program Record
                program_uuid = program_raw_dict['uuid']

                modified_date = program_uuid_2_enrollment_date.get(program_uuid)
                if modified_date:
                    program_raw_dict['modified'] = str(modified_date)
                if program_raw_dict['start'] == 'is_null':
                    program_raw_dict['non_started'] = False
                elif type(program_raw_dict['start']) in (unicode, str):
                    try:
                        program_start = datetime.strptime(program_raw_dict['non_started'], '%Y-%m-%dT%H:%M:%SZ'
                                                          ).replace(tzinfo=UTC)
                        program_raw_dict['non_started'] = not course_metadata_utils.has_course_started(program_start)
                    except Exception as e:
                        program_raw_dict['non_started'] = False
                else:
                    program_raw_dict['non_started'] = not course_metadata_utils.has_course_started(
                        program_raw_dict['start'])

            return program_raw_dict

        # Query programs by filters
        self._programs = [
            _gen_program_raw_dict(program)
            for program in PartialProgram.query(
                _filter,
                limit=self._programs_limit
            )
        ]

        if self._sorted_by_enrollment_date:
            def get_enrollment_date(program):
                return program.get('modified', '1970-01-01')
            # Sort programs list by field `modified` DESC
            self._programs.sort(key=get_enrollment_date, reverse=True)

        return self._programs

    @property
    def progress(self):
        """Get programs' statistics data
        """
        progress = []

        for program in self.engaged_programs:
            completed, in_progress, not_started = [], [], []

            for course in program['courses']:
                active_entitlement = CourseEntitlement.get_entitlement_if_active(
                    user=self._user,
                    course_uuid=course['uuid']
                )

                if self._is_course_complete(course):
                    completed.append(course)
                elif self._is_course_enrolled(course) or active_entitlement:
                    # Show all currently enrolled courses and active entitlements as in progress
                    if active_entitlement:
                        # course['course_runs'] = get_fulfillable_course_runs_for_entitlement(
                        #     active_entitlement,
                        #     course['course_runs']
                        # )
                        # course['user_entitlement'] = active_entitlement.to_dict()
                        # course['enroll_url'] = reverse(
                        #     'entitlements_api:v1:enrollments',
                        #     args=[str(active_entitlement.uuid)]
                        # )
                        in_progress.append(course)
                    else:
                        course_in_progress = self._is_course_in_progress(course)

                        if course_in_progress:
                            in_progress.append(course)
                        else:
                            course['expired'] = not course_in_progress
                            not_started.append(course)
                else:
                    not_started.append(course)

            progress.append(
                {
                    'uuid': program['uuid'],
                    'completed': len(completed) if self._count_only else completed,
                    'in_progress': len(in_progress) if self._count_only else in_progress,
                    'not_started': len(not_started) if self._count_only else not_started
                }
            )

        return progress

    def _is_course_complete(self, course):
        """Check if a user has completed a course.
            A course is completed if the user has earned a certificate for any of
            the nested course runs.

            Ref method: openedx/core/djangoapps/programs/utils.py:  def _is_course_complete(self, course):

            @param course:          dict course data which contained by Program in MongoDB.
            @type course:           dict
            @return:                indicating whether the course is complete.
            @rtype:                 boolean
        """
        for course_run in course['course_runs']:
            course_key = CourseKey.from_string(course_run['key'])

            try:
                completed_status = CourseEnrollment.objects.values_list(
                    'completed',
                    flat=True
                ).get(
                    user=self._user,
                    course_id=course_key
                )

                return True \
                    if completed_status else False

            except CourseEnrollment.DoesNotExist:
                continue

        return False

    @cached_property
    def completed_course_runs(self):
        """Determine which course runs have been completed by the user.

            @return:        list of completed courses: data format: [data format: `course_key`: `certificate type`]
            @rtype:         list
        """
        return self.course_runs_with_state['completed']

    @cached_property
    def failed_course_runs(self):
        """Determine which course runs have been failed by the user.

            @return:        list of course run IDs
            @rtype:         list
        """
        return [
            run['course_run_id']
            for run in self.course_runs_with_state['failed']
        ]

    @cached_property
    def course_runs_with_state(self):
        """Determine which course runs have been completed and failed by the user.

            @return:        dict of `completed & failed` courses [data format: `course_key`: `certificate type`]
            @rtype:         dict
        """
        course_run_certificates = certificate_api.get_certificates_for_user(
            self._user.username
        )
        completed_runs, failed_runs = [], []
        for certificate in course_run_certificates:
            certificate_type = certificate['type']

            # Treat "no-id-professional" certificates as "professional" certificates
            if certificate_type == CourseMode.NO_ID_PROFESSIONAL_MODE:
                certificate_type = CourseMode.PROFESSIONAL

            course_data = {
                'course_run_id': unicode(certificate['course_key']),
                'type': certificate_type,
            }

            if certificate_api.is_passing_status(certificate['status']):
                completed_runs.append(course_data)
            else:
                failed_runs.append(course_data)

        return {
            'completed': completed_runs, 'failed': failed_runs
        }

    def _is_course_enrolled(self, course):
        """Check if a user is enrolled in a course.

        A user is considered to be enrolled in a course if
        they're enrolled in any of the nested course runs.

            @param course:          dict course data which contained by Program in MongoDB.
            @type course:           dict
            @return:                indicating whether the course is in progress.
            @rtype:                 boolean
        """
        return any(
            course_run['key'] in self._course_run_ids
            for course_run in course['course_runs']
        )

    def _is_course_in_progress(self, course):
        """Check if course qualifies as in progress as part of the program.
            A course is considered to be in progress if a user is enrolled in a run
            of the correct mode or a run of the correct mode is still available for enrollment.

            @param course:          dict course data which contained by Program in MongoDB.
            @type course:           dict
            @return:                indicating whether the course is in progress.
            @rtype:                 boolean
        """
        enrolled_runs = [
            CourseKey.from_string(
                run['key']
            )
            for run in course['course_runs']
            if run['key'] in self._course_run_ids
        ]

        if StudentModule.objects.filter(
            student=self._user,
            course_id__in=enrolled_runs
        ).exists():
            return True

        return False
