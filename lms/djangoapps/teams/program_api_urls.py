"""
Defines the URL routes for the Programs Team API.

    urls of Courses Teams which used by CMS `urls_pattern` only.

"""

from django.conf.urls import include
from django.conf.urls import url
from rest_framework_nested import routers

from .views import (
    ProgramTeamMembersView,
    ProgramTeamMemberRolesView
)

# program admins
team_members_router = routers.SimpleRouter()
team_members_router.register(
    r'v0/programadmins',
    ProgramTeamMembersView,
    base_name=r'programadmins'
)
# program admins roles
team_members_roles_router = routers.NestedSimpleRouter(
    team_members_router,
    r'v0/programadmins',
    lookup=r'program'
)
team_members_roles_router.register(
    r'roles',
    ProgramTeamMemberRolesView,
    base_name=r'roles'
)


urlpatterns = (
    url(r'^', include(team_members_router.urls)),
    url(r'^', include(team_members_roles_router.urls))
)
