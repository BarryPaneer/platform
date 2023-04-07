from abc import ABCMeta
from abc import abstractmethod
from collections import defaultdict

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from ..models import ProgramAccessRole
from openedx.core.djangoapps.request_cache import get_cache


class _RoleUsersInterface(object):
    """A interface class of all Program Team Users of a role"""
    __metaclass__ = ABCMeta

    @abstractmethod
    def has_user(self, user):
        """Return whether the supplied django user has access to this role."""
        return False

    @abstractmethod
    def add_user(self, user):
        """Add the role to the supplied django users."""
        pass

    @abstractmethod
    def remove_user(self, user):
        """Remove the role from the supplied django users."""
        pass

    @abstractmethod
    def users_with_role(self):
        """Return a django QuerySet for all of the users with this role."""
        pass


class _UserRolesCache(object):
    """User's Programs Roles mapping object.

        Only do it while constuct instance:
            1. Make sure RequestCache of this user does exist.
            2. Fetch all programs roles of this user (programs uuids + roles)
            3. Cache roles for all programs.

    """
    CACHE_NAMESPACE = u"student.program_team_roles.BulkRoleCache"
    CACHE_KEY = u'program_team_roles_by_user'

    def __init__(self, user):
        self._roles = self.get_user_roles(user)

    @classmethod
    def get_user_roles(cls, user):
        """Return all program(s) Roles by user from `RequestCache`

            @param user:        user obj.
            @type user:         object
            @return:            {user_id: (program_uuid, program_role_name)}
            @rtype:             dict
        """
        if cls.CACHE_KEY not in get_cache(cls.CACHE_NAMESPACE):
            # Create `RequestCache` instance (`openedx/core/djangoapps/request_cache/middleware.py`)
            # By Cache: namespace & key
            get_cache(cls.CACHE_NAMESPACE)[cls.CACHE_KEY] = {}

        # Get cache data handler
        roles_by_user = defaultdict(set)
        if user.id not in get_cache(cls.CACHE_NAMESPACE)[cls.CACHE_KEY]:
            get_cache(cls.CACHE_NAMESPACE)[cls.CACHE_KEY] = roles_by_user

        # Fetch all program(s) Roles of this User.
        for role in ProgramAccessRole.objects.filter(user_id=user.id).all():
            roles_by_user[user.id].add(role)

        return get_cache(cls.CACHE_NAMESPACE)[cls.CACHE_KEY][user.id]

    def has_role(self, role_name, program_uuid):
        """Return True if `program role` & `program uuid` exist

            @param role_name:       user's program role name
            @type role_name:        string
            @param program_uuid:    program id
            @type program_uuid:     string
            @return:                True: role of program exist
            @rtype:                 boolean
        """
        return any(
            [
                access_role.role == role_name
                for access_role in self._roles
                if str(access_role.program_id) == program_uuid
            ]
        )


class RoleUsersImp(_RoleUsersInterface):
    """Implement the basic functionality of Role Users,
        and you should use the subclasses for all of these.
    """
    def __init__(self, role_name, program_uuid):
        super(_RoleUsersInterface, self).__init__()
        self._program_uuid = program_uuid
        self._role_name = role_name

    def has_user(self, user):
        """Check if the supplied django user has access to this role.

            @param user:        user obj.
            @type user:         request.User
            @return:            bool identifying if user has that particular role or not
            @rtype:             boolean
        """
        if not hasattr(user, '_program_roles'):
            # Create cache if it doesn't exist.
            user._program_roles = _UserRolesCache(user)

        return user._program_roles.has_role(
            self._role_name,
            self._program_uuid
        )

    def add_user(self, user):
        """Add the supplied django users to this role.
        """
        if self.has_user(user):
            raise ValidationError(r'User({}) already own this role({}).'.format(
                    user, self._role_name
                )
            )
        # Create new role of user into Mysql
        ProgramAccessRole(
            user=user,
            role=self._role_name,
            program_id=self._program_uuid
        ).save()
        # Delete user's cache and waiting for refresh.
        if hasattr(user, '_program_roles'):
            del user._program_roles

    def remove_user(self, user):
        """Remove the supplied django users from this role.
        """
        # Delete role of user from Mysql.
        ProgramAccessRole.objects.filter(
            user_id=user.id, role=self._role_name,
            program_id=self._program_uuid
        ).delete()
        # Delete user's cache and waiting for refresh.
        if hasattr(user, '_program_roles'):
            del user._program_roles

    def users_with_role(self):
        """Return a django QuerySet for all of the users with this role
        """
        return User.objects.get(
            programaccessrole__role=self._role_name,
            programaccessrole__program_id=self._program_uuid
        )
