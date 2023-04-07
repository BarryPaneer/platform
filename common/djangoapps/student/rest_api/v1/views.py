"""
    student views
"""
from django.contrib.auth.models import User
from django.db.models import Q

from edx_rest_framework_extensions import permissions
from rest_framework.authentication import BasicAuthentication
from rest_framework.authentication import SessionAuthentication
from rest_framework.viewsets import ReadOnlyModelViewSet

from student.roles import LT_DEVELOPER, LT_TESTER
from openedx.core.djangoapps.user_api.serializers import UserSerializer
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers


class StudentsView(ReadOnlyModelViewSet):
    """Students list"""
    authentication_classes = (SessionAuthentication, BasicAuthentication)
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserSerializer
    paginate_by_param = "page_size"

    def get_queryset(self):
        orgs = '+'.join(
            configuration_helpers.get_current_site_orgs()
        )
        user_filter = Q(profile__org=orgs) | Q(profile__org=None) & Q(is_active=True)

        if self.request.user.profile.org in [LT_DEVELOPER, LT_TESTER]:
            user_filter = user_filter | Q(profile__org=LT_TESTER)

        object_list = User.objects.filter(
            user_filter
        ).prefetch_related('preferences')

        name = self.request.GET.get('name', None)
        if name:
            object_list = object_list.filter(
                Q(username__icontains=name) |
                Q(email__icontains=name)
            )

        return object_list
