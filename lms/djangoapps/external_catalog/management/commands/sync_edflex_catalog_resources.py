from django.core.management.base import BaseCommand

from datetime import datetime
from lms.djangoapps.external_catalog.tasks import get_resources
from lms.djangoapps.external_catalog.utils import ExternalCatalogLogger


logger = ExternalCatalogLogger(r'edflex_external_catalog_update.log').logger


class Command(BaseCommand):
    help = 'Get resources from external provider'

    def handle(self, *args, **options):
        logger.info(u"Starting requesting the catalog data...")
        start_time = datetime.now()

        get_resources()

        logger.info(u"Finished all requests after {}".format(datetime.now() - start_time))
