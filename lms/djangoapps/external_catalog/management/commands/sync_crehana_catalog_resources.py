from django.core.management.base import BaseCommand
from datetime import datetime
from traceback import format_exc

from ...api import CrehanaResourcesSynchronizer
from django.core.exceptions import ImproperlyConfigured
from lms.djangoapps.external_catalog.utils import ExternalCatalogLogger
from ...utils import get_crehana_configuration


log = ExternalCatalogLogger(r'crehana_external_catalog_update.log').logger


class Command(BaseCommand):
    help = 'Sync. resources from crehana courses provider into mysql.'

    def _sync_resources(self):
        crehana_configuration = get_crehana_configuration()
        if not all(
                list(crehana_configuration.values())
        ):
            raise ImproperlyConfigured(
                'In order to use API for Crehana of the followings must be configured: '
                'CREHANA_CLIENT_KEY, CREHANA_CLIENT_SECRET, CREHANA_CLIENT_SLUG, CREHANA_BASE_API_URL'
            )

        CrehanaResourcesSynchronizer(
            slug=crehana_configuration['client_slug'],
            api_key=crehana_configuration['client_key'],
            api_secret=crehana_configuration['client_secret'],
            api_url_prefix=crehana_configuration['base_api_url']
        ).run()

    def handle(self, *args, **options):
        try:
            log.info(r'Starting requesting the crehana catalog data...')

            start_time = datetime.now()
            self._sync_resources()

            log.info(r'Finished all requests after {}'.format(datetime.now() - start_time))
        except Exception:
            log.error('Unknow exception occured in script, Traceback ===> {}'.format(format_exc()))
