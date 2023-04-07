class AndersPinkRequestException(Exception):
    pass


class BasicBriefingAccessor(object):
    def __init__(self, api_key, base_api_url, api_time, is_board_enabled):
        self._base_api_url = base_api_url
        self._api_time = api_time
        self._is_board_enabled = is_board_enabled
        self._headers = {
            'X-Api-Key': api_key,
        }

    @classmethod
    def _validate_and_return(cls, http_resp):
        """Return data if http status is equal to 200, otherwise raise exception"""
        if http_resp.status_code not in (200, 201):
            raise AndersPinkRequestException(
                'anderspink api exception: {}'.format(http_resp.content)
            )
        return http_resp.json()