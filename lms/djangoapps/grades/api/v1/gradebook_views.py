"""
Defines an endpoint for gradebook data related to a course.
"""
import copy
import logging
import json
from collections import namedtuple
from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import ugettext as _
from django.utils import timezone
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.response import Response
from six import text_type
from util.date_utils import to_timestamp

from courseware.courses import get_course_by_id
from lms.djangoapps.grades.api.v1.utils import (
    USER_MODEL,
    GradeViewMixin,
    PaginatedAPIView,
    verify_course_exists
)
from lms.djangoapps.grades.constants import ScoreDatabaseTableEnum
from lms.djangoapps.grades.course_data import CourseData
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from lms.djangoapps.grades.events import SUBSECTION_GRADE_CALCULATED, subsection_grade_calculated
from lms.djangoapps.grades.models import (
    PersistentCourseGrade,
    PersistentSubsectionGrade,
    PersistentSubsectionGradeOverride,
    PersistentSubsectionGradeOverrideHistory,
)
from lms.djangoapps.grades.services import GradesService
from lms.djangoapps.grades.signals.signals import GRADE_EDITED
from lms.djangoapps.grades.subsection_grade import CreateSubsectionGrade
from lms.djangoapps.grades.tasks import (
    recalculate_subsection_grade_v3,
    send_grade_override_email,
    update_course_progress
)
from lms.djangoapps.instructor.enrollment import get_user_email_language
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey
from openedx.core.djangoapps.course_groups import cohorts
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.core.djangoapps.util.forms import to_bool
from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, view_auth_classes
from student.auth import has_course_author_access
from student.models import CourseEnrollment
from student.roles import BulkRoleCache
from track.event_transaction_utils import (
    create_new_event_transaction_id,
    get_event_transaction_id,
    get_event_transaction_type,
    set_event_transaction_type
)

log = logging.getLogger(__name__)


@contextmanager
def bulk_gradebook_view_context(course_key, users):
    """
    Prefetches all course and subsection grades in the given course for the given
    list of users, also, fetch all the score relavant data,
    storing the result in a RequestCache and deleting grades on context exit.
    """
    PersistentSubsectionGrade.prefetch(course_key, users)
    PersistentCourseGrade.prefetch(course_key, users)
    CourseEnrollment.bulk_fetch_enrollment_states(users, course_key)
    cohorts.bulk_cache_cohorts(course_key, users)
    BulkRoleCache.prefetch(users)
    yield
    PersistentSubsectionGrade.clear_prefetched_data(course_key)
    PersistentCourseGrade.clear_prefetched_data(course_key)


def get_bool_param(request, param_name, default):
    """
    Given a request, parameter name, and default value, returns
    either a boolean value or the default.
    """
    param_value = request.query_params.get(param_name, None)
    bool_value = to_bool(param_value)
    if bool_value is None:
        return default
    else:
        return bool_value


def course_author_access_required(view):
    """
    Ensure the user making the API request has course author access to the given course.

    This decorator parses the course_id parameter, checks course access, and passes
    the parsed course_key to the view as a parameter. It will raise a
    403 error if the user does not have author access.

    Usage::
        @course_author_access_required
        def my_view(request, course_key):
            # Some functionality ...
    """
    def _wrapper_view(self, request, course_id, *args, **kwargs):
        """
        Checks for course author access for the given course by the requesting user.
        Calls the view function if has access, otherwise raises a 403.
        """
        course_key = CourseKey.from_string(course_id)
        if not has_course_author_access(request.user, course_key):
            raise DeveloperErrorViewMixin.api_error(
                status_code=status.HTTP_403_FORBIDDEN,
                developer_message='The requesting user does not have course author permissions.',
                error_code='user_permissions',
            )
        return view(self, request, course_key, *args, **kwargs)
    return _wrapper_view


def graded_subsections_for_course(course_structure):
    """
    Given a course block structure, yields the subsections of the course that are graded.
    Args:
        course_structure: A course structure object.  Not user-specific.
    """
    for chapter_key in course_structure.get_children(course_structure.root_block_usage_key):
        for subsection_key in course_structure.get_children(chapter_key):
            subsection = course_structure[subsection_key]
            if subsection.graded:
                yield subsection


GradebookUpdateResponseItem = namedtuple('GradebookUpdateResponseItem',
                                         ['user_id', 'usage_id', 'success', 'reason', 'grade_data'])


@view_auth_classes()
class GradebookBulkUpdateView(GradeViewMixin, PaginatedAPIView):
    """
    **Use Case**
        Creates `PersistentSubsectionGradeOverride` objects for multiple (user_id, usage_id)
        pairs in a given course, and invokes a Django signal to update subsection grades in
        an asynchronous celery task.

    **Example Request**
        POST /api/grades/v1/gradebook/{course_id}/bulk-update

    **POST Parameters**
        This endpoint does not accept any URL parameters.

    **Example POST Data**
          {
            9: {"block-v1:edX+DemoX+Demo_Course+type@sequential+block@basic_questions": 50,
                "block-v1:edX+DemoX+Demo_Course+type@sequential+block@advanced_questions": 100},

            11: {"block-v1:edX+DemoX+Demo_Course+type@sequential+block@basic_questions": 90}
          }

    **POST Response Values**
        An HTTP 202 may be returned if a grade override was created for each of the requested (user_id, usage_id)
        pairs in the request data.
        An HTTP 403 may be returned if the `writable_gradebook` feature is not
        enabled for this course.
        An HTTP 404 may be returned for the following reasons:
            * The requested course_key is invalid.
            * No course corresponding to the requested key exists.
            * The requesting user is not enrolled in the requested course.
        An HTTP 422 may be returned if any of the requested (user_id, usage_id) pairs
        did not have a grade override created due to some exception.  A `reason` detailing the exception
        is provided with each response item.

    **Example successful POST Response**
        [
          {
            "user_id": 9,
            "usage_id": ["some-requested-usage-id", "some-requested-usage-id"]
            "success": true,
            "reason": null,
            "grade_data": [
                {'category': 'Total', 'override': True, 'usage_key': '', 'grade': 75, 'class': 'high-column',
                    'percent': 0.75, 'detail': u'Total', 'label': 'Total'},
                {'category': u'Homework', 'override': True, 'usage_key': u'block-v1:edX+DemoX+Demo_Course+type@se..},
                {'category': u'Homework', 'override': True, 'usage_key': u'block-v1:edX+DemoX+Demo_Course+type@se..},
                {'category': u'Homework', 'override': False, 'usage_key': '', 'grade': 0, 'class': '', 'percent':..},
                {'category': u'Exam', 'override': False, 'usage_key': u'block-v1:edX+DemoX+Demo_Course+type@seq..}
            ]
          }
        ]
    """

    @verify_course_exists
    @course_author_access_required
    def post(self, request, course_key):
        """
        Creates or updates `PersistentSubsectionGradeOverrides` for the (user_id, usage_key)
        specified in the request data.  The `GRADE_EDITED` signal is invoked
        after the grade override is created, which triggers a celery task to update the
        course and subsection grades for the specified user.
        """

        course = get_course_by_id(course_key, depth=None)

        result = []
        email_list = []
        course_progress_users = []
        whole = False
        data = request.data['log']
        number_of_sections = int(request.data['number_of_sections'])
        import json
        data = json.loads(data)
        for user_id, keys in data.items():
            requested_user_id = int(user_id)
            usage_ids = list(set(keys))
            override_sections = {}
            if number_of_sections == len(usage_ids):
                whole = True
            try:
                user = self._get_single_user(request, course_key, requested_user_id)
            except USER_MODEL.DoesNotExist:
                continue

            for requested_usage_id in copy.copy(usage_ids):
                try:
                    usage_key = UsageKey.from_string(requested_usage_id)

                except InvalidKeyError as exc:
                    self._log_update_result(
                        request.user, requested_user_id, requested_usage_id, success=False, reason=text_type(exc)
                    )
                    usage_ids.remove(requested_usage_id)
                    continue

                try:
                    subsection_grade_model = PersistentSubsectionGrade.objects.get(
                        user_id=requested_user_id,
                        course_id=course_key,
                        usage_key=usage_key
                    )

                except PersistentSubsectionGrade.DoesNotExist:
                    subsection = course.get_child(usage_key)
                    if subsection:
                        subsection_grade_model = self._create_subsection_grade(user, course, subsection)
                    else:
                        self._log_update_result(
                            request.user, requested_user_id, requested_usage_id, success=False,
                            reason=u'usage_key does not exist in this course.'
                        )
                        usage_ids.remove(requested_usage_id)
                        continue

                if subsection_grade_model:
                    # if the current score equals to the override score, skip and remove the usage_id from the list
                    # This won't happen if we edit the score of subsections one by one, but it could happen when we
                    # edit the total score or the average score, because we have to change all the score of the included
                    # subsection to the same
                    override_score = keys[requested_usage_id] * subsection_grade_model.possible_all / 100
                    if override_score == subsection_grade_model.earned_all:
                        usage_ids.remove(requested_usage_id)
                        continue
                    else:
                        override_data = {
                            "earned_all_override": override_score,
                            "possible_all_override": subsection_grade_model.possible_all,
                            "earned_graded_override": override_score,
                            "possible_graded_override": subsection_grade_model.possible_all
                        }
                        override = self._create_override(request.user, subsection_grade_model, **override_data)
                        self._log_update_result(
                            request.user, requested_user_id, requested_usage_id, subsection_grade_model, override, True
                        )

            if usage_ids:
                course_grade = CourseGradeFactory().read(user, course)
                grade_summary = course_grade.summary
                graded_subsections = course_grade.graded_subsections_by_format
                section_breakdown = grade_summary['section_breakdown']
                for section in section_breakdown:
                    sections_by_format = graded_subsections.get(section.get('category'))
                    if sections_by_format:
                        pair = sections_by_format.popitem(last=False)
                        section['usage_key'] = unicode(pair[0])
                        if unicode(pair[0]) in usage_ids:
                            override_sections[pair[1].display_name] = int(section['percent'] * 100)
                        if pair[1].override is not None:
                            section['override'] = True
                            grade_summary['override'] = True
                    else:
                        continue
                grade_data = self._grade_data(grade_summary)
                result.append(GradebookUpdateResponseItem(
                    user_id=user.id,
                    usage_id=usage_ids,
                    success=True,
                    reason=None,
                    grade_data=grade_data
                ))
                email_list.append({
                    'total': int(grade_summary['percent'] * 100),
                    'name': user.profile.name or user.username,
                    'email': user.email,
                    'whole': whole,
                    'sections': override_sections,
                    'language': get_user_email_language(user)
                })
                course_progress_users.append(user.id)

        if email_list:
            # we don't finish the anaytics transcript feature yet, so use this fake link
            transcript_link = request.build_absolute_uri(reverse('analytics_my_transcript'))
            course_name = course.display_name_with_default_escaped
            platform_name = configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME)
            email_service_enabled = configuration_helpers.get_value('ENABLE_EMAIL_SERVICE', True)
            from_alias = configuration_helpers.get_value('email_from_alias', settings.DEFAULT_FROM_EMAIL_ALIAS)
            from_address = configuration_helpers.get_value('email_from_address', settings.DEFAULT_FROM_EMAIL)
            from_address = "{0} <{1}>".format(from_alias, from_address)
            send_grade_override_email.apply_async(
                kwargs={
                    'student_info': email_list,
                    'transcript_link': transcript_link,
                    'course_name': course_name,
                    'platform_name': platform_name,
                    'email_service_enabled': email_service_enabled,
                    'from_address': from_address
                }
            )
            if course_progress_users:
                update_course_progress.apply_async(
                    kwargs={
                        'users': course_progress_users,
                        'course_id': unicode(course_key)
                    }
                )

        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        if len(result) > 0:
            status_code = status.HTTP_202_ACCEPTED

        return Response(
            {item.user_id: item._asdict() for item in result},
            status=status_code,
            content_type='application/json'
        )

    def _create_subsection_grade(self, user, course, subsection):
        course_data = CourseData(user, course=course)
        subsection_grade = CreateSubsectionGrade(subsection, course_data.structure, {}, {})
        return subsection_grade.update_or_create_model(user, force_update_subsections=True)

    def _create_override(self, request_user, subsection_grade_model, **override_data):
        """
        Helper method to create a `PersistentSubsectionGradeOverride` object
        and send a `GRADE_EDITED` signal.
        """
        override = PersistentSubsectionGradeOverride.update_or_create_override(
            requesting_user=request_user,
            subsection_grade_model=subsection_grade_model,
            feature=PersistentSubsectionGradeOverrideHistory.GRADEBOOK,
            **override_data
        )

        GRADE_EDITED.send(
            sender=None,
            user_id=subsection_grade_model.user_id,
            course_id=subsection_grade_model.course_id,
            modified=override.modified,
        )

        set_event_transaction_type(SUBSECTION_GRADE_CALCULATED)
        create_new_event_transaction_id()

        recalculate_subsection_grade_v3.apply(
            kwargs=dict(
                user_id=subsection_grade_model.user_id,
                anonymous_user_id=None,
                course_id=text_type(subsection_grade_model.course_id),
                usage_id=text_type(subsection_grade_model.usage_key),
                only_if_higher=False,
                expected_modified_time=to_timestamp(override.modified),
                score_deleted=False,
                event_transaction_id=unicode(get_event_transaction_id()),
                event_transaction_type=unicode(get_event_transaction_type()),
                score_db_table=ScoreDatabaseTableEnum.overrides,
                force_update_subsections=True,
            )
        )
        # Emit events to let our tracking system to know we updated subsection grade
        subsection_grade_calculated(subsection_grade_model)
        return override

    def _grade_data(self, grade_summary):
        data = []
        for section in grade_summary['section_breakdown']:
            attrs = {'percent': section['percent'], 'category': section['category'],
                     'label': section['label'], 'detail': section['detail'],
                     'class': '', 'grade': int(round(section['percent'] * 100)),
                     'usage_key': section.get('usage_key', ''),
                     'override': section.get('override', False)}
            if 'Avg' in section['label']:
                attrs['class'] = 'high-column'
            if section.get('override', False):
                attrs['override'] = True
            data.append(attrs)
        total = {'percent': grade_summary['percent'], 'category': 'Total', 'label': 'Total',
                 'detail': _('Total'),'class': 'high-column', 'grade': int(round(grade_summary['percent'] * 100)),
                 'override': grade_summary.get('override', False), 'usage_key': ''}
        if grade_summary.get('manually_changed'):
            total['manually_changed'] = True
        data = [total] + data
        return data

    @staticmethod
    def _log_update_result(
        request_user,
        user_id, usage_id,
        subsection_grade_model=None,
        subsection_grade_override=None,
        success=False,
        reason=None,
    ):

        log.info(
            u'Grades: Bulk_Update, UpdatedByUser: %s, User: %s, Usage: %s, Grade: %s, GradeOverride: %s, Success: %s, '
            u'Reason: %s',
            request_user.id,
            user_id,
            usage_id,
            subsection_grade_model,
            subsection_grade_override,
            success,
            reason
        )


@require_POST
def undo_override_for_student(request, course_id):
    user_id = int(request.POST.get('user_id'))
    user = User.objects.get(id=user_id)
    course_key = CourseKey.from_string(course_id)
    usage_ids = json.loads(request.POST.get('usage_ids'))
    for key in usage_ids:
        GradesService().undo_override_subsection_grade(user_id, course_id, key)
    GRADE_EDITED.send(
        sender=None,
        user_id=user_id,
        course_id=course_key,
        modified=timezone.now(),
    )
    grade_summary = CourseGradeFactory().read(user, course_key=course_key).summary
    update_course_progress.apply_async(
        kwargs={
            'users': [user_id],
            'course_id': course_id
        }
    )
    data = []
    for section in grade_summary['section_breakdown']:
        attrs = {'percent': section['percent'], 'category': section['category'],
                 'label': section['label'], 'detail': section['detail'],
                 'class': '', 'grade': int(round(section['percent'] * 100)),
                 'usage_key': section.get('usage_key', ''),
                 'override': section.get('override', False)}
        if 'Avg' in section['label']:
            attrs['class'] = 'high-column'
        if section.get('override', False):
            attrs['override'] = True
        data.append(attrs)
    total = {'percent': grade_summary['percent'], 'category': 'Total', 'label': 'Total',
             'detail': _('Total'), 'class': 'high-column', 'grade': int(round(grade_summary['percent'] * 100)),
             'override': grade_summary.get('override', False), 'usage_key': ''}
    data = [total] + data
    return JsonResponse({user_id: data})
