from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.views.decorators.csrf import ensure_csrf_cookie
from edxmako.shortcuts import render_to_response
from util.cache import cache_if_anonymous

from openedx.features.centrical_support.utils import (
    get_triboo_centrical_index_url,
    is_triboo_centrical_enabled
)


@ensure_csrf_cookie
@login_required
@cache_if_anonymous()
def triboo_centrical_catalog(request):
    if is_triboo_centrical_enabled([group.name for group in request.user.groups.all()]):
        return render_to_response(
            'centrical/centrical_platform.html',
            {
                'disable_footer': True,
                'is_centrical_platform': True,
                'centrical_platform_url': get_triboo_centrical_index_url()
            }
        )
    else:
        raise Http404
