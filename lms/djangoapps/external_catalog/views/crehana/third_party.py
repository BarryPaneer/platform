from logging import getLogger
from urllib import quote
from urllib import unquote

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from util.cache import cache_if_anonymous

from lms.djangoapps.external_catalog.api import CrehanaAccessor
from ...utils import get_crehana_configuration


log = getLogger(__name__)


class ThirdPartyRedirectionPage(View):
    @method_decorator(login_required)
    @method_decorator(ensure_csrf_cookie)
    @method_decorator(cache_if_anonymous())
    def get(self, request):
        crehana_cfg = get_crehana_configuration()
        crehana_accessor = CrehanaAccessor(
            slug=crehana_cfg['client_slug'],
            api_key=crehana_cfg['client_key'],
            api_secret=crehana_cfg['client_secret'],
            api_url_prefix=crehana_cfg['base_api_url']
        )

        user_info = crehana_accessor.create_user(
            email=unquote(quote(request.user.email)),
            first_name=unquote(quote(request.user.first_name.encode('utf-8'))),
            last_name=unquote(quote(request.user.last_name.encode('utf-8')))
        )

        user_id = user_info['id']
        sso_token = crehana_accessor.generate_sso_token_by_uid(user_id)
        sso_login_url = crehana_accessor.generate_url_by_sso_token(sso_token, request.GET.get('next_url'))

        return redirect(sso_login_url)
