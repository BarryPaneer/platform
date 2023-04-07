"""A wrapper of Anderspink B2B Api : `AnderspinkClient`
"""
from requests import get as _http_get
from urlparse import urljoin

from lms.djangoapps.external_catalog.utils import ExternalCatalogLogger
from .basic_accessor import BasicBriefingAccessor as _BasicBriefingAccessor
from ..utils import exception_retry

log = ExternalCatalogLogger.getLoggerByName()


class AndersPinkDownloader(_BasicBriefingAccessor):
    """
    Client to consume Anderspink service API.
    """

    def __init__(self, api_key, base_api_url, api_time, is_board_enabled):
        super(AndersPinkDownloader, self).__init__(api_key, base_api_url, api_time, is_board_enabled)
        self.base_api_url = base_api_url
        self.is_board_enabled = is_board_enabled
        self.api_time = api_time



    @exception_retry(retry_times=3)
    def get_briefings(self):
        response = _http_get(
            url=urljoin(
                self.base_api_url,
                'briefings'
            ), headers=self._headers
        )
        return self._validate_and_return(response)


    @exception_retry(retry_times=3)
    def get_boards(self):
        response = _http_get(
            url=urljoin(
                self.base_api_url,
                'boards'
            ), headers=self._headers
        )
        return self._validate_and_return(response)


    @exception_retry(retry_times=3)
    def get_articles(self, limit, offset, time, briefing, api_name):
        """Create a anders pink user with parameters & Return User Info."""

        url = urljoin(
            self.base_api_url,
            '{api_name}/{id}?limit={limit}&offset={offset}&time={time}'.format(api_name=api_name,id=briefing["id"], limit=limit,offset=offset, time=time),
        )
        response = _http_get(url, headers=self._headers)

        return self._validate_and_return(response)


class AndersPinkDataCache(AndersPinkDownloader):
    """A cache of AndersPink `briefings/articles`"""
    FETCH_BATCH_SIZE = 50

    def __init__(self, api_key, base_api_url, api_time, is_board_enabled):
        super(AndersPinkDataCache, self).__init__(
            api_key, base_api_url, api_time, is_board_enabled
        )
        self._briefing_cache = []
        self._article_cache = []
        self._board_cache = []
        self._board_article_cache = []
        self.TIME = api_time
        self.is_board_enabled = is_board_enabled


    def download(self):
        """
            Downloading resources from anderspink server
            *** Throw exception if still get error while downloading after retry ***
        """
        log.info('Anderspink briefing is downloading...')

        briefings = self.get_briefings()
        self._briefing_cache = briefings.get('data', {}).get('owned_briefings', [])
        log.info('Downloaded, briefing count = {}'.format(len(self._briefing_cache)))

        for briefing in self._briefing_cache:
            for i in range(0, 0xffff, self.FETCH_BATCH_SIZE):
                try:
                    api_name = "briefings"
                    articles = self.get_articles(self.FETCH_BATCH_SIZE, i, self.TIME, briefing, api_name)
                    if not articles['data'].get('articles', ()):
                        break

                    self._article_cache.append(articles)
                except Exception as e:
                    log.info(str(e))

        log.info('Anderspink board is downloading...')

        boards = self.get_boards()
        log.info(
            'Downloaded, board count = {}'.format(
                len(boards)
            )
        )
        self._board_cache.append(boards)

        if self.is_board_enabled:
            for board in self._board_cache[0]['data'].get("owned_boards", ()):
                for i in range(0, 0xffff, self.FETCH_BATCH_SIZE):
                    try:
                        api_name = "boards"
                        articles = self.get_articles(
                            self.FETCH_BATCH_SIZE, i, self.TIME, board, api_name)
                        if not articles['data'].get('articles', ()):
                            break

                        self._board_article_cache.append(articles)
                    except Exception as e:
                        log.info(str(e))


    @property
    def briefings(self):
        """briefings cache"""
        return self._briefing_cache

    @property
    def articles(self):
        """articles cache"""
        return self._article_cache

    @property
    def boards(self):
        """boards cache"""
        return self._board_cache

    @property
    def board_articles(self):
        """articles cache"""
        return self._board_article_cache
