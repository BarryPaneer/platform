"""
    Load programs data from service Discovery
    &
    Save them into local Cache

    Service Discovery Rest api root URL as follow:

        COURSE_CATALOG_API_URL = 'http://edx.devstack.discovery:18381/api/v1/'

"""


from openedx.core.djangoapps.catalog.utils import create_catalog_api_client


class SiteProgramsLoader(object):
    """Site's Programs data loader , download data from service discovery
    """
    def __init__(self, user, site=None, current_site_domain=None):
        """Programs data loader for 1 site

            @param user:                login user obj.
            @type user:                 object
            @param site:                site record
            @type site:                 table record
            @param current_site_domain: site domain
            @type current_site_domain:  string
        """
        self._api_client_handler = None
        self._user = user
        self._site = site
        self._current_site_domain = current_site_domain

    @property
    def _api_client(self):
        """Return service discovery programs access api

            @return:            programs data access api
            @rtype:             EdxRestApiClient
        """
        if not self._api_client_handler:
            self._api_client_handler = create_catalog_api_client(
                self._user,
                site=self._site,
                current_site_domain=self._current_site_domain
            )

        return self._api_client_handler

    def _get_programs_uuids(self):
        """Fetch all programs uuids with url:

            http://edx.devstack.discovery:18381/api/v1/programs/

            @return:            programs' uuids list
            @rtype:             list
        """
        querystring = {
            'exclude_utm': 1,
            'status': (
                'active', 'retired',
                'unpublished'
            ),
            'uuids_only': 1,
        }

        return self._api_client.programs.get(**querystring)

    def get_program_by_uuid_with_retry(self, program_uuid, exc_retry_times=2):
        """Fetch a program detail data by program uuid (with exception retry)

            Raise exception if get failure.

            @param program_uuid:        program uuid
            @type program_uuid:         string
            @param exc_retry_times:     retry number (retry POST request after got exception)
            @type exc_retry_times:      integer
            @return:                    programs' detail
            @rtype:                     dict
        """
        for retry_count in range(exc_retry_times):
            try:
                # Fetching program detail with UUID
                return self._api_client.programs(
                    program_uuid
                ).get(
                    exclude_utm=1
                )
            except Exception:
                if retry_count == (exc_retry_times - 1):
                    raise

    def _get_programs_details_by_uuids(self, uuids, exc_retry_times=5):
        """Fetch program detail with url:

            http://edx.devstack.discovery:18381/api/v1/programs/b359a4c4-4a1a-487c-906a-3fb89197e5fe/?exclude_utm=1

            @param uuids:           programs' uuids list
            @type uuids:            list
            @param exc_retry_times: retry number (retry POST request after got exception)
            @type exc_retry_times:  integer
            @return:                programs' detail list, Sample <uuid: program detail data>
            @rtype:                 dict
        """
        programs = {}

        for uuid in uuids:
            program = self.get_program_by_uuid_with_retry(
                program_uuid=uuid,
                exc_retry_times=exc_retry_times
            )
            programs[uuid] = program

        return programs

    def get_programs(self):
        """Fetch all programs detail data in a site

            @return:            programs' detail list, Sample <uuid: program detail data>
            @rtype:             dict
        """
        uuids = self._get_programs_uuids()

        return self._get_programs_details_by_uuids(
            uuids,
            exc_retry_times=3
        )
