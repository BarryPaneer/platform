# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
from django.core.exceptions import EmptyResultSet
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError

from .role_users import ProgramInstructorRole
from .role_users import ProgramStaffRoles
from common.djangoapps.student.roles import GlobalStaff
from common.djangoapps.student.auth import (
    STUDIO_EDIT_ROLES,
    STUDIO_VIEW_USERS,
    STUDIO_EDIT_CONTENT,
    STUDIO_VIEW_CONTENT,
    STUDIO_NO_PERMISSIONS
)


log = logging.getLogger(__name__)


class ProgramRolesManager(object):
    """Program Teams manager"""
    # Keep the definition be same with the function `get_user_permissions` which
    #   in file: /Users/barrypaneer/workspace/hawthorn/platform/common/djangoapps/student/auth.py
    PERMISSION_ALL = STUDIO_EDIT_ROLES | STUDIO_VIEW_USERS | STUDIO_EDIT_CONTENT | STUDIO_VIEW_CONTENT

    ROLES_HIERARCHY_VECTOR = (
        ProgramInstructorRole, ProgramStaffRoles
    )

    @classmethod
    def get_permissions(cls, user, program_id):
        """Get program access permissions by `user` & `program uuid`

            Grants permissions for users as follow:
             - "Platform Admin"
             - "Platform Super Admin"
             - "User in LP. Teams"

            @param user:        user obj.
            @type user:         record
            @param program_id:  program uuid
            @type program_id:   string
            @return:            permissions integer (Mask value)
            @rtype:             integer
        """
        if not program_id:
            return STUDIO_NO_PERMISSIONS

        # Platform Admin / Super Admin have Super permission
        if GlobalStaff().has_user(user) or \
                user.is_superuser:
            return cls.PERMISSION_ALL

        if ProgramInstructorRole(program_id).has_user(user):
            return cls.PERMISSION_ALL

        if ProgramStaffRoles(program_id).has_user(user):
            # Staff only view or edit content
            return STUDIO_EDIT_CONTENT | STUDIO_VIEW_CONTENT

        return STUDIO_NO_PERMISSIONS

    @classmethod
    def get_role_of_user(cls, request_user, user, program_uuid):
        if not (request_user.is_authenticated and request_user.is_active):
            raise PermissionDenied('Unlogin user Or user is not activated.')

        for role in cls.ROLES_HIERARCHY_VECTOR:
            if role(program_uuid).has_user(user):
                return role.ROLE

        raise EmptyResultSet('[WARN] The user does not have any role.')

    @classmethod
    def add_role_to_user(cls, request_user, new_user, program_uuid, new_role):
        """Add new role to a user for Cases:
             - [Upgrade User Role] Add new role to a user if the caller has edit permission.
             - [Demote User Role] Self-demote a old higher role by adding a new low level role.

            @param request_user:        caller
            @type request_user:         user obj.
            @param new_user:            target user.
            @type new_user:             user obj.
            @param program_uuid:        program uuid string
            @type program_uuid:         string (uuid)
            @param new_role:            new role name for target user(new user)
            @type new_role:             string
            @return:                    matched role type
            @rtype:                     string

        """
        # Checking for new role name (should be valid role name)
        higher_roles_types = []
        matched_role_type = None
        for role_type in cls.ROLES_HIERARCHY_VECTOR:
            role = role_type(program_uuid)
            if role_type.ROLE == new_role and not role.has_user(new_user):
                matched_role_type = role_type
                break
            elif role.has_user(new_user):
                higher_roles_types.append(role_type)
                break

        if not matched_role_type and not higher_roles_types:
            raise ValidationError('Invalid role name.')

        # Checking creating permission
        requester_permissions = cls.get_permissions(
            request_user, program_uuid
        )
        if not (requester_permissions & STUDIO_EDIT_ROLES) \
                and \
                not (new_user.id == request_user.user.id and higher_roles_types):
            # Raise Exception if `No permission` or `Not self-Demotion`
            raise PermissionDenied('No permission Or Self-Demotion.')

        # Remove higher roles if the user has more than 1 roles.
        for old_role_type in higher_roles_types:
            if isinstance(old_role_type, ProgramInstructorRole) and role.users_with_role().count() == 1:
                raise ValidationError(
                    'You may not remove the last Admin. Add another Admin first.'
                )
            old_role_type(
                program_uuid
            ).remove_user(new_user)
            role_name = 'Staff' if old_role_type.ROLE == 'staff' else 'Admin'
            log.info('User {user_id} removed {email} from Learning Path Team as {role_name}, path_id: {path_id}'.format(
                user_id=request_user.id, email=new_user.email, path_id=program_uuid, role_name=role_name
            ))

        # Add new role for user
        if matched_role_type:
            matched_role_type(
                program_uuid
            ).add_user(new_user)
            role_name = 'Staff' if new_role == 'staff' else 'Admin'
            log.info('User {user_id} added {email} to Learning Path Team as {role_name}, path_id: {path_id}'.format(
                user_id=request_user.id, email=new_user.email, path_id=program_uuid, role_name=role_name
            ))

            return matched_role_type

    @classmethod
    def remove_roles_from_user(cls, request_user, user, program_uuid):
        """Delete all roles of this user except the last `ProgramInstructorRole`

            @param request_user:        caller
            @type request_user:         user obj.
            @param user:                target user.
            @type user:                 user obj.
            @param program_uuid:        program uuid
            @type program_uuid:         string(uuid)
            @return:                    None
        """
        # Checking creating permission
        requester_permissions = cls.get_permissions(
            request_user, program_uuid
        )
        if not (requester_permissions & STUDIO_EDIT_ROLES):
            raise PermissionDenied('No permission for deleting.')

        # Delete roles of user
        user_existing_roles = [
            role_type
            for role_type in cls.ROLES_HIERARCHY_VECTOR
            if role_type(program_uuid).has_user(user)
        ]
        if not user_existing_roles:
            raise ValidationError(
                'User({}) do not has any roles for this program.'.format(user)
            )

        for old_role in user_existing_roles:
            if isinstance(old_role, ProgramInstructorRole) and old_role.users_with_role().count() == 1:
                raise ValidationError(
                    'You may not remove the last Admin. Add another Admin first.'
                )
            old_role(program_uuid).remove_user(user)
