from django.db import transaction

from lms.djangoapps.external_catalog.utils import ExternalCatalogLogger
from ...models import CrehanaLanguage
from ...models import CrehanaResource
from .resources_downloader import CrehanaDataCache
from ..utils import print_error_arguments


log = ExternalCatalogLogger.getLoggerByName()


class ResourcesSynchronizer(object):
    """Download & Save resources from crehana server into mysql"""
    def __init__(self, slug, api_key, api_secret, api_url_prefix):
        self.__data_cache = CrehanaDataCache(
            slug,
            api_key, api_secret,
            api_url_prefix
        )
        self.__time_of_first_inserting = None

    @print_error_arguments
    def _save_course(self, course):
        """Write into table `languages` & `resources`"""
        langs_array = []
        for lang in course.get('languages', ()):
            lang = lang.encode('utf-8').lower()
            # lang_id:      'bc'--> 102,       'fr'-->517
            _language_id = reduce(lambda x, y: x * 100 + (ord(y) - ord('a')), lang, 0)  # algorithm for <int>id
            _lauguage, _ = CrehanaLanguage.objects.update_or_create(
                language_id=_language_id,
                defaults={
                    'language': lang
                }
            )
            langs_array.append(_language_id)

        _course, _ = CrehanaResource.objects.update_or_create(
            resource_id=int(course['id']),
            defaults={
                'languages': r','.join(map(str, langs_array)),   # Sample:   `fr,en,pt`
                'title': course['title'].encode('utf-8'),
                'description': course.get('description', u'').encode('utf-8'),
                'duration': int(course.get('duration', 0)),
                'image': course.get('image', {'url': u''})['url'].encode('utf-8'),
                'rating': float(course.get('rating', {'average': 0.}).get('average', 0.)),
                'url': course.get('url', u'').encode('utf-8')
            }
        )
        if not self.__time_of_first_inserting:
            self.__time_of_first_inserting = _course.modified
            log.info('Generated minimum time_t({}) in db'.format(self.__time_of_first_inserting))

    def _clear_invalid_records(self):
        """Remove the invalid records which are taken earlier timestamp"""
        if self.__time_of_first_inserting:
            log.info('Deleting records which earlier than {}'.format(self.__time_of_first_inserting))
            CrehanaResource.objects.filter(modified__lt=self.__time_of_first_inserting)
            CrehanaLanguage.objects.filter(modified__lt=self.__time_of_first_inserting)
            self.__time_of_first_inserting = None       # clean time_t flag

    def run(self):
        """Download data from server & store the data into mysql."""
        log.info('Crehana resources synchronizer is running...')
        # 0. Downloading & Caching data from server
        self.__data_cache.download()

        with transaction.atomic():
            # 1. Updating / Creating resources into mysql
            # for category in self.__data_cache.categories:
            #     self._save_categories(category, data_updated_time)
            for course in self.__data_cache.courses:
                self._save_course(course)

            # 2. Deleting records with invalid date(field `updated_at`) in tables.
            self._clear_invalid_records()

        log.info('Crehana resources synchronizer quit.')
