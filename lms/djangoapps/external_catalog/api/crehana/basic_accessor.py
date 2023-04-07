

class CrehanaRequestException(Exception):
    pass


class BasicResourcesAccessor(object):
    def __init__(self, slug, api_key, api_secret, api_url_prefix):
        self._api_url_prefix = api_url_prefix
        self._slug = slug
        self._headers = {
            'api-key': api_key,
            'secret-access': api_secret
        }

    @classmethod
    def _validate_and_return(cls, http_resp):
        """Return data if http status is equal to 200, otherwise raise exception"""
        if http_resp.status_code not in (200, 201):
            raise CrehanaRequestException(
                'Crehana API exception: {}'.format(http_resp.content)
            )
        return http_resp.json()
