"""A wrapper of Crehana B2B Api : `CrehanaClient`
"""
from requests import get as _http_get
from urlparse import urljoin

from lms.djangoapps.external_catalog.utils import ExternalCatalogLogger
from .basic_accessor import BasicResourcesAccessor as _BasicResourcesAccessor
from ..utils import exception_retry


log = ExternalCatalogLogger.getLoggerByName()


class CrehanaDownloader(_BasicResourcesAccessor):
    """Crehana api wrapper class  for downloading data from crehana server"""
    def __init__(self, slug, api_key, api_secret, api_url_prefix):
        super(CrehanaDownloader, self).__init__(
            slug, api_key, api_secret, api_url_prefix
        )

    @exception_retry(retry_times=3)
    def fetch_all_catalogs(self):
        """Get all catalogs info."""
        response = _http_get(
            urljoin(
                self._api_url_prefix,
                '{}/categories/'.format(self._slug)
            ),
            headers=self._headers
        )
        return self._validate_and_return(response)

    @exception_retry(retry_times=3)
    def fetch_courses(self, category_name=None, offset=0, size=10):
        """Get courses info. batch by batch by category name"""
        url = urljoin(
            self._api_url_prefix,
            '{}/available-courses/?size={}&offset={}'.format(self._slug, size, offset)
        )
        if category_name:
            url = urljoin(url, '&category={}'.format(category_name))

        response = _http_get(url, headers=self._headers)

        return self._validate_and_return(response)


class CrehanaDataCache(CrehanaDownloader):
    """A cache of Crehana `courses/categories`"""
    FETCH_BATCH_SIZE = 50

    def __init__(self, slug, api_key, api_secret, api_url_prefix):
        super(CrehanaDataCache, self).__init__(
            slug, api_key, api_secret, api_url_prefix
        )
        self._courses_cache = []
        self._categories_cache = []

    def download(self):
        """
            Downloading resources from crehana server

            *** Throw exception if still get error while downloading after retry ***
        """
        log.info('Crehana resources is downloading...')
        # Caching for `categories`
        # self._categories_cache = self.fetch_all_catalogs()

        # Caching for `courses`
        for i in range(0, 0xffff, self.FETCH_BATCH_SIZE):
            courses = self.fetch_courses(
                offset=i, size=self.FETCH_BATCH_SIZE
            )
            if not courses:
                break

            self._courses_cache.extend(courses)

        log.info(
            'Downloaded, courses count = {}, categories count = {}'.format(
                len(self._courses_cache), len(self._categories_cache)
            )
        )

    @property
    def categories(self):
        """categories cache"""
        return self._categories_cache

    @property
    def courses(self):
        """courses cache"""
        return self._courses_cache
