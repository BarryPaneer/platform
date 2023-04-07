import logging
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from xmodule.modulestore.course_checklist import Checkpoints, StudioCoursesChecklists
from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, view_auth_classes

from .utils import course_author_access_required


log = logging.getLogger(__name__)


@view_auth_classes()
class CourseStepsValidationView(DeveloperErrorViewMixin, GenericAPIView):
    """Manage (read/update) `checklists` for courses
    """
    @course_author_access_required
    def get(self, request, course_key):
        """Returns checklists validation information for the given course key

            **Example Requests**

                GET /api/courses/v1/steps_validation/{course_id}/

            **GET Response Sample**

                [
                    {'name': 'Step 1', 'key': 'step 1', 'status': 1, 'step_desc': 'Start creating your course content'},
                    {'name': 'Step 2', 'key': 'step 2', 'status': 1, 'step_desc': 'Set your grading policy'},
                    {'name': 'Step 3', 'key': 'step 3", 'status': 0, 'step_desc': 'Add accurate members to your course team'},
                    ...
                    ...
                    {'name': 'Step 3', 'key': 'step_9', 'status': 0, 'step_desc': 'Enable your certificate'}
                ]

                *** Note: keys defined in Checkpoints.ALL_CHECKPOINT_STATUS.
        """
        _checklists = StudioCoursesChecklists()

        return Response(
            _checklists.get_checklists_by_key(str(course_key))
        )

    @course_author_access_required
    def post(self, request, course_key):
        """Update parts of checklists for the given course key

            **Example Requests**

                POST /api/courses/v1/steps_validation/{course_id}/

            **Payload Sample**
                {
                    "step_1": 1,
                    "step_6": 0
                }

                *** Note: keys defined in Checkpoints.ALL_CHECKPOINT_STATUS.

            **POST Response Sample**

                [
                    {'name': 'Step 1', 'key': 'step 1', 'status': 1, 'step_desc': 'Start creating your course content'},
                    {'name': 'Step 2', 'key': 'step 2', 'status': 1, 'step_desc': 'Set your grading policy'},
                    {'name': 'Step 3', 'key': 'step 3", 'status': 0, 'step_desc': 'Add accurate members to your course team'},
                    ...
                    ...
                    {'name': 'Step 3', 'key': 'step_9', 'status': 0, 'step_desc': 'Enable your certificate'}
                ]

        """
        _steps_logs = None

        if request.data.get('steps_logs'):
            _steps_logs = {
                step_key: step_status for step_key, step_status in request.data.get('steps_logs').items()
                if Checkpoints.is_valid_step_keys(step_key) and Checkpoints.is_valid_checkpoint_status(step_status)
            }

        if not course_key or not _steps_logs:
            return Response(
                data={
                    'error': 'Invalid course key ( {} ) or arguments ( {} )'.format(
                        str(course_key), request.POST.get('steps_logs')
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        _checklists = StudioCoursesChecklists()
        _checklists.upsert_checklists_by_key(str(course_key), _steps_logs)

        return Response(
            _checklists.get_checklists_by_key(str(course_key))
        )
