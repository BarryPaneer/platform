"""An accessor of Crehana user info. / sso login /...
"""
from requests import post as _http_post
from urlparse import urljoin

from .basic_accessor import BasicResourcesAccessor as _BasicResourcesAccessor


class CrehanaAccessor(_BasicResourcesAccessor):
    """class for user info. / sso login /..."""
    def __init__(self, slug, api_key, api_secret, api_url_prefix):
        super(CrehanaAccessor, self).__init__(
            slug, api_key, api_secret, api_url_prefix
        )

    def create_user(self, email, first_name, last_name):
        """Create a crehana user with parameters & Return User Info."""
        payload = {
            'email': email, 'first_name': first_name, 'last_name': last_name
        }
        response = _http_post(
            url=urljoin(
                self._api_url_prefix,
                '{}/users/'.format(self._slug)
            ),
            headers=self._headers,
            data=payload
        )
        return self._validate_and_return(response)

    def generate_sso_token_by_uid(self, user_id):
        """Generate & return a crehana sso token string by `user_id`
        """
        response = _http_post(
            url=urljoin(self._api_url_prefix, '{slug}/users/{user_id}/sso-auth/'.format(slug=self._slug, user_id=user_id)),
            json={"api_key": self._headers['api-key'], "secret_access": self._headers['secret-access']}
        )
        return self._validate_and_return(response)['token']

    def generate_url_by_sso_token(self, sso_token, next_url=None):
        """Generate login url string with SSO token & return

            if `next_url` is not None, then the url format maybe:
                https:/www.abc.com/griky/sso-auth/?api_key=key_abc&token=test_token&next_url=https://www.crehana.com/clases/v2/9185/detalle/

        """
        url = urljoin(
            self._api_url_prefix,
            '{slug}/sso-auth/?api_key={api_key}&token={auth_token}'.format(
                slug=self._slug,
                api_key=self._headers['api-key'],
                auth_token=sso_token
            )
        )

        if not next_url:
            return url

        return url + '&next_url={}'.format(next_url)
