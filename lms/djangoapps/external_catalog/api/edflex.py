import logging
from urlparse import urljoin

from oauthlib.oauth2 import BackendApplicationClient
from requests import HTTPError
from requests_oauthlib import OAuth2Session


log = logging.getLogger(__name__)


class EdflexOauthClient(object):
    """
    Client to consume Edflex service API.
    """
    TOKEN_URL = '/api/oauth/v2/token'
    CATALOGS_URL = '/api/selection/catalogs'
    CATALOG_URL = '/api/selection/catalogs/{id}'
    RESOURCE_URL = '/api/resource/resources/{id}'
    SELECTIONS_URL = '/api/selection/selections'
    SELECTION_URL = '/api/selection/selections/{id}'

    def __init__(self, client_id, client_secret, locale, base_api_url):
        self.client_id = client_id
        self.client_secret = client_secret
        self.locale = locale
        self.base_api_url = base_api_url
        client = BackendApplicationClient(client_id=self.client_id)
        self.oauth_client = OAuth2Session(client=client)
        self.fetch_token()

    def fetch_token(self):
        token_url = urljoin(self.base_api_url, self.TOKEN_URL)
        self.oauth_client.fetch_token(
            token_url=token_url,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )

    def get_resource(self, url):
        resource_url = urljoin(self.base_api_url, url)
        resp = self.oauth_client.get(
            url=resource_url,
            headers={'content-type': 'application/json'},
            params={'locale': self.locale}
        )
        try:
            resp.raise_for_status()
        except HTTPError as er:
            log.error(er)
            content = None
        else:
            content = resp.json()
        return content
