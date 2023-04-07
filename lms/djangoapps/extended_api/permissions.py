from rest_framework.permissions import IsAuthenticated


class IsStaffAndOrgMember(IsAuthenticated):
    """
    Permission to check that user is staff and member of site organization.
    """

    def has_permission(self, request, view):
        is_authenticated = super(IsStaffAndOrgMember, self).has_permission(request, view)
        if is_authenticated:
            is_admin = (request.user.is_staff and request.user.is_superuser)
            return (is_admin and request.user.profile.org and request.user.is_active)
        return False
