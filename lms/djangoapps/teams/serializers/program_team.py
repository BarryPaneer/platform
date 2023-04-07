from rest_framework.serializers import ModelSerializer as _ModelSerializer

from lms.djangoapps.teams.models import ProgramAccessRole
from openedx.core.djangoapps.user_api.serializers import UserSerializer


class ProgramTeamMembershipReadSerializer(_ModelSerializer):
    """Serializes program team members for reading only
    """
    user = UserSerializer(read_only=True)

    @classmethod
    def prefetch_queryset(cls, program_uuid):
        """Return program team members by querying `ProgramAcessRole` table.

            Because program team is a `Virtual Concept`.
        """
        added_users_set = set()
        program_users_roles = []

        for record in ProgramAccessRole.objects.filter(
            program_id=program_uuid
        ).order_by('role').all():
            if record.user_id in added_users_set:
                continue

            added_users_set.add(record.user_id)

            user_role = {
                'user_id': record.user_id,
                'program_id': record.program_id,
                'role': record.role
            }
            program_users_roles.append(
                ProgramAccessRole(**user_role)
            )

        return program_users_roles

    class Meta(object):
        model = ProgramAccessRole
        fields = ('user', 'role')


class ProgramTeamMemberRolesWriteSerializer(_ModelSerializer):
    """Serialize team member roles for writing"""
    class Meta(object):
        model = ProgramAccessRole
        fields = ('role', 'user', 'program_id')


class ProgramTeamMemberRolesReadSerializer(_ModelSerializer):
    """Serialize team member roles for reading"""
    @classmethod
    def fetch_user_roles(cls, team_id, user_id):
        return ProgramAccessRole.objects.filter(
            program_id=team_id, user_id=user_id
        ).all()

    class Meta(object):
        model = ProgramAccessRole
        fields = ('id', 'role')
