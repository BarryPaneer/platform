import logging
from sys import exit as sys_exit
from traceback import format_exc

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.management import BaseCommand

from openedx.core.djangoapps.catalog.cache import (
    PROGRAM_CACHE_KEY_TPL,
    SITE_PROGRAM_UUIDS_CACHE_KEY_TPL
)
from openedx.core.djangoapps.catalog.models import CatalogIntegration
from util.programs import SiteProgramsLoader


logger = logging.getLogger(__name__)
User = get_user_model()  # pylint: disable=invalid-name


class Command(BaseCommand):
    """Management command used to cache program data.

    This command requests every available program from the discovery
    service, writing each to its own cache entry with an indefinite expiration.
    It is meant to be run on a scheduled basis and should be the only code
    updating these cache entries.
    """
    help = "Rebuild the LMS' cache of program data."

    def _cache_data_from_discovery(self, user):
        all_programs = {}

        for site in Site.objects.all():
            # Should be only 1 discovery site. But here we check for all sites.
            site_config = getattr(site, 'configuration', None)
            if site_config is None or not site_config.get_value('COURSE_CATALOG_API_URL'):
                logger.info('Skipping site {domain}. No configuration.'.format(domain=site.domain))
                cache.set(SITE_PROGRAM_UUIDS_CACHE_KEY_TPL.format(domain=site.domain), [], None)
                continue

            # Download programs detail data from site
            site_programs = SiteProgramsLoader(
                user, site,
                current_site_domain=str(site.domain)
            ).get_programs()

            site_uuids = list(site_programs.keys())

            # Build programs cache data
            for uuid, program in site_programs.items():
                logger.info('[UUID] : {}'.format(uuid))
                cache_key = PROGRAM_CACHE_KEY_TPL.format(uuid=uuid)
                all_programs[cache_key] = program

            logger.info(
                'Caching UUIDs for {total} programs for site {site_name}.'.format(
                    total=len(site_uuids),
                    site_name=site.domain,
                )
            )
            # Cache site's uuids
            cache.set(
                SITE_PROGRAM_UUIDS_CACHE_KEY_TPL.format(domain=site.domain), site_uuids, None
            )

        # Cache all programs for sites
        logger.info('Caching details for {} programs.'.format(len(all_programs)))
        cache.set_many(all_programs, None)

    def handle(self, *args, **options):
        try:
            logger.info('populate-multitenant-programs switch is ON')

            try:
                username = CatalogIntegration.current().service_username
                user = User.objects.get(
                    username=username
                )

            except User.DoesNotExist:
                logger.error(
                    'Failed to create API client. Service user {username} does not exist.'.format(username=username)
                )
                raise

            self._cache_data_from_discovery(user)

        except Exception:
            logger.error(
                'Fatal error occur while caching programs data : '.format(format_exc())
            )
            # This will fail a Jenkins job running this command, letting site
            # operators know that there was a problem.
            sys_exit(1)
