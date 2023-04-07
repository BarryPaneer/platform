"""
Middleware that checks user standing for the purpose of keeping users with
disabled accounts from accessing the site.
"""
from django.conf import settings
from django.http import HttpResponseForbidden
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _
from django.contrib.auth.models import User
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers

from student.models import UserStanding
from student.models import UserProfile



class UserStandingMiddleware(object):
    """
    Checks a user's standing on request. Returns a 403 if the user's
    status is 'disabled'.
    """
    def process_request(self, request):
        user = request.user
        try:
            user_account = UserStanding.objects.get(user=user.id)
            # because user is a unique field in UserStanding, there will either be
            # one or zero user_accounts associated with a UserStanding
        except UserStanding.DoesNotExist:
            pass
        else:
            if user_account.account_status == UserStanding.ACCOUNT_DISABLED:
                msg = _(
                    'Your account has been disabled. If you believe '
                    'this was done in error, please contact us at '
                    '{support_email}'
                ).format(
                    support_email=u'<a href="mailto:{address}?subject={subject_line}">{address}</a>'.format(
                        address=settings.DEFAULT_FEEDBACK_EMAIL,
                        subject_line=_('Disabled Account'),
                    ),
                )
                return HttpResponseForbidden(msg)


class TermsOfServiceMiddleware(object):
    """
    Check if a user's lt_is_tos_agreed is true.
    Returns to tos_page if it's not the case.
    """
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.user.is_authenticated() is False:
            return
        if request.user.is_superuser:
            return
        profile = UserProfile.objects.filter(user=request.user.id).first()
        if configuration_helpers.get_value('ENABLE_TERMS_OF_SERVICE_PAGE', settings.FEATURES.get('ENABLE_TERMS_OF_SERVICE_PAGE', False)):
            tos_agreed_flag = configuration_helpers.get_value('TERMS_OF_SERVICE_AGREED_ALL', settings.FEATURES.get('TERMS_OF_SERVICE_AGREED_ALL', False))
            users = User.objects.all()
            for user in users:
                user_profile = UserProfile.objects.filter(user=user.id).first()
                if user_profile.lt_is_tos_agreed != tos_agreed_flag:
                    user_profile.lt_is_tos_agreed = tos_agreed_flag
                    user_profile.save()
            if view_func.func_name in ['tos_page', 'confirm_tos', 'LogoutView']:
                return
            if profile.lt_is_tos_agreed:
                return
            return HttpResponseRedirect('/tos_page')
        return
