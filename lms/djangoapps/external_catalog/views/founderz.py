import logging
import certifi
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest
from http.client import HTTPConnection
from django.shortcuts import redirect
from django.views.decorators.csrf import ensure_csrf_cookie
from requests import post as _http_post

from lms.djangoapps.external_catalog.utils import (
    get_founderz_configuration,
    is_founderz_enabled
)
from util.cache import cache_if_anonymous


logger = logging.getLogger(__name__)

__FOUNDERZ_TOKEN_URL = r'https://founderz.com/api/founderz/gettoken/{partner_id}/{slug}/{user_id}/{user_email}/get'
__FOUNDERZ_ACCESS_URL = r'https://founderz.com/api/founderz/sso-login/getaccess/{partner_id}/{slug}/{api_key}/{token}'


@ensure_csrf_cookie
@login_required
@cache_if_anonymous()
def founderz_catalog(request):
    if not is_founderz_enabled(request.user.groups.all()):
        raise Http404

    _client_key = get_founderz_configuration().get('client_key')
    _client_secret = get_founderz_configuration().get('client_secret')
    _slug = get_founderz_configuration().get('slug')
    _partner_id = get_founderz_configuration().get('partner_id')

    HTTPConnection._http_vsn_str = 'HTTP/1.0'
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}
    response = _http_post(
        __FOUNDERZ_TOKEN_URL.format(
            partner_id=_partner_id, slug=_slug,
            user_id=request.user.id, user_email=request.user.email
        ),
        data={'api_key': _client_key, 'secret_access': _client_secret},
        verify=certifi.where(),
        headers=headers
    )

    logger.info("FOUNDERZ_TOKEN_URL = %s => %s" % (__FOUNDERZ_TOKEN_URL.format(
            partner_id=_partner_id, slug=_slug,
            user_id=request.user.id, user_email=request.user.email
        ), response.status_code))
    if response.status_code not in (200, 201):
        return HttpResponseBadRequest('Failed to fetch token from founderz server.')

    logger.info("FOUNDERZ_ACCESS_URL = %s" % __FOUNDERZ_ACCESS_URL.format(
            partner_id=_partner_id, slug=_slug,
            api_key=_client_key, token=response.json()['token']
        ))
    return redirect(
        __FOUNDERZ_ACCESS_URL.format(
            partner_id=_partner_id, slug=_slug,
            api_key=_client_key, token=response.json()['token']
        )
    )
