from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.csrf import ensure_csrf_cookie
from util.cache import cache_if_anonymous
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from student.triboo_groups import LINKEDIN_DENIED_GROUP

@ensure_csrf_cookie
@login_required
@cache_if_anonymous()
def linkedin_catalog(request):
    linkedin_url = configuration_helpers.get_value('LINKEDIN_URL', None)
    if configuration_helpers.get_value('ENABLE_LINKEDIN_CATALOG', settings.FEATURES.get('ENABLE_LINKEDIN_CATALOG', False)) \
        and linkedin_url \
        and LINKEDIN_DENIED_GROUP not in [group.name for group in request.user.groups.all()]:
        return redirect(linkedin_url)
    else:
        raise Http404