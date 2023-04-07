from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.csrf import ensure_csrf_cookie
from util.cache import cache_if_anonymous
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from student.triboo_groups import UDEMY_DENIED_GROUP
from django.http import Http404

@ensure_csrf_cookie
@login_required
@cache_if_anonymous()
def udemy_catalog(request):
    udemy_url = configuration_helpers.get_value('UDEMY_URL', None)
    if configuration_helpers.get_value('ENABLE_UDEMY_CATALOG', settings.FEATURES.get('ENABLE_UDEMY_CATALOG', False)) \
        and udemy_url \
        and UDEMY_DENIED_GROUP not in [group.name for group in request.user.groups.all()]:
        return redirect(udemy_url)
    else:
        raise Http404