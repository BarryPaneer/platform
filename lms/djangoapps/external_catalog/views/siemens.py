from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.csrf import ensure_csrf_cookie
from util.cache import cache_if_anonymous

from lms.djangoapps.external_catalog.utils import is_siemens_enabled
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers


@ensure_csrf_cookie
@login_required
@cache_if_anonymous()
def siemens_catalog(request):
    if is_siemens_enabled(request.user.groups.all()):
        siemens_url = configuration_helpers.get_value('SIEMENS_URL', None)
        return redirect(siemens_url)
    else:
        raise Http404
