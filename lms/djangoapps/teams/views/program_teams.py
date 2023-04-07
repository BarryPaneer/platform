# -*- coding: utf-8 -*-
from __future__ import unicode_literals

"""HTTP endpoints for the Program Teams Members Management API.

    Program Team is used for management of team memeber roles accessing.
    &
    We just access member data in table `program_access_roles` in Mysql.

    *** We don't create table like `program_team` for this. ***

"""

import logging

from django.db import transaction
from django.db.models import Q
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from rest_framework import permissions
from rest_framework import status, viewsets
from rest_framework.authentication import BasicAuthentication
from rest_framework.response import Response

from student.roles import STUDIO_ADMIN_ACCESS_GROUP
from student.roles import LEARNING_PATH_ADMIN_ACCESS_GROUP
from student.models import CourseAccessRole
from common.djangoapps.student.auth import (
    STUDIO_EDIT_CONTENT,
    STUDIO_VIEW_CONTENT
)
from common.djangoapps.util.rest_csrfexempt_session_auth import CsrfExemptSessionAuthentication
from cms.djangoapps.api.proxy.views import DiscoveryRequestProxy
from lms.djangoapps.teams.program_team_roles import ProgramInstructorRole
from lms.djangoapps.teams.program_team_roles import ProgramStaffRoles
from lms.djangoapps.program_enrollments.programs import ProgramCoursesLoader
from opaque_keys.edx.keys import CourseKey
from openedx.core.lib.api.view_utils import ExpandableFieldViewMixin

from ..program_team_roles import ProgramRolesManager
from ..serializers import (
    ProgramTeamMembershipReadSerializer,
    ProgramTeamMemberRolesWriteSerializer,
    ProgramTeamMemberRolesReadSerializer,
)
from student.roles import studio_access_role


TEAM_MEMBERSHIPS_PER_PAGE = 2
TOPICS_PER_PAGE = 12
MAXIMUM_SEARCH_SIZE = 100000

log = logging.getLogger(__name__)


class ProgramTeamMembersView(ExpandableFieldViewMixin, viewsets.ModelViewSet):
    """List program admin list by querying table `program access role`
    """
    # OAuth2Authentication must come first to return a 401 for unauthenticated users
    lookup_field = r'id'
    authentication_classes = (CsrfExemptSessionAuthentication, BasicAuthentication)
    permission_classes = (permissions.IsAuthenticated,)

    def get_serializer_class(self):
        # For show listing only.
        return ProgramTeamMembershipReadSerializer

    def get_queryset(self):
        """Get queryset of program access roles by `program uuid`

            Using for reading only. (don't support delete/update...)
        """
        program_uuid = self.kwargs['id']

        return self.get_serializer_class().prefetch_queryset(
            program_uuid
        )

    def destroy(self, request, *args, **kwargs):
        program_uuid = self.kwargs['id']

        # 1. Checking for creating permission of program team.
        user_perms = ProgramRolesManager.get_permissions(
            request.user, program_uuid
        )
        if not (STUDIO_VIEW_CONTENT & user_perms):
            raise PermissionDenied(
                'current user has no permission for fetching program team members'
            )

        # 2. Remove all user's roles from table
        user = User.objects.get(
            email=request.data['email']
        )

        for role in ProgramRolesManager.ROLES_HIERARCHY_VECTOR:
            if role(program_uuid).has_user(user):
                role_name = 'Staff' if role.ROLE == 'staff' else 'Admin'
                log.info(
                    'User {user_id} removed {email} from Learning Path Team as {role_name}, path_id: {path_id}'.format(
                        user_id=request.user.id, email=request.data['email'], path_id=program_uuid, role_name=role_name
                    ))
                role(program_uuid).remove_user(user)

        return Response(
            {'program_uuid': program_uuid},
            status=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        """List team members & roles by checking request user permission.
        """
        program_uuid = self.kwargs['id']

        # 1. Checking for creating permission of program team.
        user_perms = ProgramRolesManager.get_permissions(
            request.user, program_uuid
        )
        if not (STUDIO_VIEW_CONTENT & user_perms):
            raise PermissionDenied(
                'current user has no permission for fetching program team members'
            )

        # 2. Fetch team members with pagination
        members = super(
            ProgramTeamMembersView, self
        ).list(
            request, *args, **kwargs
        )

        # 3. Extend additional info(Role Name) for each User in Row.
        if 'results' in members.data:
            # Get roles user_ids
            new_results = []
            staffs_ids = set()
            instructors_ids = set()

            for user_role_info in members.data['results']:
                if user_role_info['role'] == ProgramInstructorRole.ROLE:
                    instructors_ids.add(
                        user_role_info['user']['id']
                        )
                if user_role_info['role'] == ProgramStaffRoles.ROLE:
                    staffs_ids.add(
                        user_role_info['user']['id']
                        )

            staffs_ids = staffs_ids - instructors_ids

            # Extend additional data(Role Name for user)
            # Ref logic: def _manage_users(request, course_key):
            for user_role_info in members.data['results']:
                user = user_role_info['user']

                user_info = User.objects.get(id=user['id'])
                user_role_info['is_staff'] = True if user_info.is_staff else False
                user_role_info['is_studio_admin'] = STUDIO_ADMIN_ACCESS_GROUP in [group.name for group in user_info.groups.all()]

                if user['id'] in instructors_ids:
                    user_role_info['role'] = ProgramInstructorRole.ROLE

                elif user['id'] in staffs_ids \
                        and user['id'] not in instructors_ids:

                    if user_role_info['is_staff'] or user_role_info['is_studio_admin']:
                        user_role_info['role'] = ProgramStaffRoles.ROLE
                    else:
                        # user_role_info['role'] = 'triboo_instructor'
                        continue

                    new_results.append(user_role_info)

        return members


class ProgramTeamMemberRolesView(ExpandableFieldViewMixin, viewsets.ModelViewSet):
    """Add/Remove a role for a program team member"""
    # OAuth2Authentication must come first to return a 401 for unauthenticated users
    lookup_field = 'id'
    authentication_classes = (CsrfExemptSessionAuthentication, BasicAuthentication)
    permission_classes = (permissions.IsAuthenticated,)

    def get_serializer_class(self):
        if self.action in ('create',):
            return ProgramTeamMemberRolesWriteSerializer
        # self.action == 'list'
        return ProgramTeamMemberRolesReadSerializer

    def get_queryset(self):
        return self.get_serializer_class().fetch_user_roles(
            self.kwargs['program_uuid'],
            int(self.kwargs['users_id'])
        )

    @classmethod
    def is_legal_user(cls, user):
        """Only Platform Super Admin / Platform Admin / Studio Super Admin could access programs
        """
        user_groups = [group.name for group in user.groups.all()]

        return user.is_staff or user.is_superuser or (
            STUDIO_ADMIN_ACCESS_GROUP in user_groups and LEARNING_PATH_ADMIN_ACCESS_GROUP in user_groups
        )

    def _add_new_user_into_program_courses_teams(self, request_user, new_user, program_uuid, new_role):
        """Add new user of a Program Team into that Program's Courses teams.

            @param request_user:        request user.
            @type request_user:         user obj.
            @param new_user:            target user.
            @type new_user:             user obj.
            @param program_uuid:        program uuid string
            @type program_uuid:         string (uuid)
            @param new_role:            new role name for target user(new user)
            @type new_role:             string

        """
        # Get Program Courses list
        draft_program = ProgramCoursesLoader(
            request_user,
            program_uuid=program_uuid,
            current_site_domain=DiscoveryRequestProxy.get_site_domain(self.request)
        ).initialize_program_detail_to_draftdb()

        program_courses_runs = [
            course_run
            for course in draft_program['courses']
            for course_run in course['course_runs']
        ]

        # Get courses keys in programs
        program_courses_keys = [
            CourseKey.from_string(run['key'])
            for run in program_courses_runs
        ]
        # Get course_key:users mapping
        course_key_users_mapping = {}
        for role in CourseAccessRole.objects.filter(
            course_id__in=program_courses_keys
        ).all():
            if role.course_id not in course_key_users_mapping:
                course_key_users_mapping[role.course_id] = {role.user}
            else:
                course_key_users_mapping[role.course_id].add(role.user)
        # Get courses keys which the new user is not added.
        course_roles = {
            course_key
            for course_key in program_courses_keys
            if course_key not in course_key_users_mapping or new_user not in course_key_users_mapping[course_key]
        }
        # Add the user into Each Courses Teams by Course Keys
        with transaction.atomic():
            for course_id in course_roles:
                CourseAccessRole(
                    user=new_user,
                    org=course_id.org,
                    course_id=course_id,
                    role=new_role
                ).save()

    def create(self, request, program_id):
        """ `Create` / `Demote`  :  a program role for a user.

            Logic Ref: def _course_team_user(request, course_key, email)

            POST /api/team/v0/programadmins/{program_uuid}/roles/
        """
        user = User.objects.get(
            email=request.data['email']
        )

        if not self.is_legal_user(user):
            raise ValidationError(
                'It is an instructor user ({}). access denied.'.format(request.data['email'])
            )

        matched_role_type = ProgramRolesManager.add_role_to_user(
            request.user,
            user,
            program_id,
            request.data['role_name']
        )

        if matched_role_type:
            self._add_new_user_into_program_courses_teams(
                self.request.user, user,
                program_id, request.data['role_name']
            )

        return Response(
            {'program_uuid': program_id},
            status=status.HTTP_201_CREATED
        )

    def delete(self, request, program_id):
        """ Delete all roles for a user except the last `ProgramInstructorRole`

            DELETE /api/team/v0/programadmins/{program_uuid}/roles/
        """
        user = User.objects.get(
            email=request.data['email']
        )

        ProgramRolesManager.add_role_to_user(
            request.user,
            user,
            program_id,
            request.data['role_name']
        )

        return Response(
            {'removed_role': request.data['role_name']},
            status=status.HTTP_200_OK
        )
