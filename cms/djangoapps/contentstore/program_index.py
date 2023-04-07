"""
    A program index creator, support hot fix & displace index

    - Create a new program index
    - Link new index into ES Alias

"""
from __future__ import absolute_import

import logging
from time import strftime

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from search.search_engine_base import SearchEngine

from eventtracking import tracker
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.catalog.models import CatalogIntegration
from openedx.core.djangoapps.models.course_details import CourseDetails
from util.programs import SiteProgramsLoader


log = logging.getLogger('edx.modulestore')


class ProgramESIndex(object):
    """Class to perform indexing for programs search
        or
        Add new document into Index by Alias Name.

        Usages:
            [Reindex all programs]:
                - Create a new program index with Current Datetime.
                - Link this new index with Alias `program_index`
                - Remove expired index from Alias `program_index`

                ProgramESIndex(specified_program_ids).run_hot_index()

            [Add new program data into Index with `Alias Name`]
                - Query Index name by `Alias Name`
                - Put new program data into That Index.

                ProgramESIndex(
                    specified_program_ids,
                    alias=ProgramESIndex.INDEX_ALIAS_NAME
                ).add_new_program(
                    {
                        "uuid": "36f090c1-a5f9-4d26-a87e-b0eb9da4d58c___abc_______4",
                        "language": "en-us",
                        "courses_count": 0,
                        "title": "barry_test_program_aaaaaaaaa___abc_______4",
                        "duration": 3600,
                        "type": "",
                        ...
                    }
                )

    """
    INDEX_ALIAS_NAME = "program_index"
    DOCUMENT_TYPE = "content"

    INDEX_EVENT = {
        'name': 'edx.program.index.reindexed',
        'category': 'program_index'
    }

    INDEX_MAPPING_SETTINGS = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "partword": {
                        "type": "custom",
                        "tokenizer": "partword_tokenizer",
                        "filter": [
                            "lowercase"
                        ]
                    },
                    "case_insensitive_sort": {
                        "tokenizer": "keyword",
                        "filter":  ["lowercase"]
                    }
                },
                "tokenizer": {
                    "partword_tokenizer": {
                        "type": "nGram",
                        "min_gram": 1,
                        "max_gram": 50
                    }
                }
            }
        },
        'mappings': {
            DOCUMENT_TYPE: {
                'properties': {
                    'title': {
                        'type': 'string',
                        'analyzer': 'partword',
                        'fields': {
                            'raw_title': {
                                'type': 'string',
                                'analyzer': 'case_insensitive_sort'
                            }
                        }
                    },
                }
            }
        }
    }

    def __init__(self, specified_program_ids=None, alias=None, current_site_domain=None):
        """Program index maintainer.

            @param specified_program_ids:   program filters
            @type specified_program_ids:    list
            @param alias:                   index alias name of ES, the index name by alias
            @type alias:                    string
            @param current_site_domain:     site domain
            @type current_site_domain:      string
        """
        self._current_site_domain = current_site_domain
        self._specified_program_ids = set(specified_program_ids) \
            if specified_program_ids \
            else set({})

        if not alias:
            # Generate New Index name by current datetime.
            self._new_index_name = ProgramESIndex.INDEX_ALIAS_NAME + '_{}'.format(
                strftime('%Y%m%d%H%M%S')
            )       # Generate a new program index name (time related unique name)
        else:
            # Assign with `None`, Fetch Existed Index name by `alias`.
            self._new_index_name = None

        self._searcher = SearchEngine.get_search_engine(
            index=self._new_index_name,
            index_mappings=self.INDEX_MAPPING_SETTINGS,
            alias=alias
        )
        # Assign with new index name.
        self._new_index_name = self._searcher.index_name \
            if alias \
            else self._new_index_name

    @staticmethod
    def _gen_es_program_with_program_detail(program):
        """Convert program detail to ES program data format

            @param program:     program detail data which fetched from discovery service
            @type program:      dict
        """
        def _fetch_course_detail_ignore_exception(course_id):
            try:
                return CourseDetails.fetch(
                    CourseKey.from_string(course_id)
                ).vendor
            except Exception:
                return []

        course_tags = [] \
            if not program['courses'] \
            else \
            {
                tag
                for course in program['courses']
                for course_run in course['course_runs']
                for tag in _fetch_course_detail_ignore_exception(
                    course_run['key']
                )
            }
        course_tags = list(course_tags) \
            if isinstance(course_tags, set) \
            else course_tags

        return {
            'title': program['title'],
            'uuid': program['uuid'],
            'courses_count': len(program['courses']),
            'language': program['language'],
            'vendor': course_tags,
            'card_image_url': program['card_image_url'],
            'duration': program['duration'],
            'type': '' if not program['type'] else program['type'],
            'released_date': program['released_date'],
            'start': program['start'],
            'end': program['end'],
            'status': program['status'],
            'partner': program['partner'],
            'visibility': program['visibility']
        }

    def add_new_program(self, program_or_uuid):
        """Add new program record into ES.

            @param program:     `program detail data` OR `program uuid`
            @type program:      `dict` OR `string`
        """
        if isinstance(program_or_uuid, dict):
            # Add program data directly.
            self._searcher.index(
                self.DOCUMENT_TYPE, [program_or_uuid]
            )
        else:
            # Query by program uuid, then add into index.
            service_user = get_user_model().objects.get(
                username=CatalogIntegration.current().service_username
            )

            program = SiteProgramsLoader(
                service_user,
                current_site_domain=self._current_site_domain
            ).get_program_by_uuid_with_retry(
                program_or_uuid
            )

            self._searcher.index(
                self.DOCUMENT_TYPE,
                [self._gen_es_program_with_program_detail(program)]
            )

    def update_program(self, program_uuid):
        """Update program record of Indeex by `program uuid`

            @param program_uuid:     program uuid
            @type program_uuid:      string
        """
        self.delete_program(program_uuid)
        self.add_new_program(program_uuid)

    def delete_program(self, program_uuid):
        """Delete program record from ES index.

            @param program_uuid:     program uuid
            @type program_uuid:      string
        """
        response = self._searcher.search(
            doc_type=self.DOCUMENT_TYPE,
            field_dictionary={'uuid': program_uuid}
        )

        result_ids = [
            result['_id']
            for result in response['results']
        ]

        if result_ids:
            self._searcher.remove(self.DOCUMENT_TYPE, result_ids)

    @classmethod
    def _track_index_request(cls, event_name, category, indexed_count):
        """Track content index requests.

        Arguments:
            event_name (str):  Name of the event to be logged.
            category (str): category of indexed items
            indexed_count (int): number of indexed items
        Returns:
            None

        """
        data = {
            "indexed_count": indexed_count,
            'category': category,
        }

        tracker.emit(
            event_name,
            data
        )

    def get_index_name(self):
        """Return program index name

            Sample: `program_index_20210604090102`
        """
        return self._new_index_name

    def _get_all_programs_from_sites(self):
        """Return all programs from all sites (remove duplicated program)

            There is only 1 discovery service url of site provide programs data.
            But it's ok. We iterate from all sites
        """
        programs_of_sites = {}

        service_user = get_user_model().objects.get(
            username=CatalogIntegration.current().service_username
        )
        for site in Site.objects.all():
            # Should be only 1 discovery site. But here we check for all sites.
            site_config = getattr(site, 'configuration', None)
            if site_config is None or not site_config.get_value('COURSE_CATALOG_API_URL'):
                log.info('Skipping site {domain}. No configuration.'.format(domain=site.domain))
                continue

            try:
                site_programs = SiteProgramsLoader(
                    service_user,
                    site,
                    current_site_domain=str(site.domain)
                ).get_programs()

                log.info('Fetching data from site {domain}...'.format(domain=str(site.domain)))
                for uuid, program in site_programs.items():
                    if uuid not in programs_of_sites:
                        log.info(
                            r'Program: {}, title: {}'.format(
                                uuid,
                                unicode(program['title']).encode('utf-8')
                            )
                        )
                        programs_of_sites[uuid] = program
            except Exception as e:
                print(e)
                log.info('Failed to fetch data from {domain}'.format(domain=site.domain))

        return programs_of_sites

    def _create_new_index(self):
        """
            Create new program index.
            tracking the fact that a full reindex has taken place
        """
        indexed_count = 0
        programs_of_sites = self._get_all_programs_from_sites()

        programs = map(
            lambda p: self._gen_es_program_with_program_detail(p),
            (
                program
                for uuid, program in programs_of_sites.items()
                if uuid in self._specified_program_ids or not self._specified_program_ids
            )
        )
        self._searcher.index(self.DOCUMENT_TYPE, programs)

        if programs:
            self._track_index_request(
                self.INDEX_EVENT['name'], self.INDEX_EVENT['category'], len(programs)
            )

        return indexed_count

    def run_hot_index(self):
        """
        (Re)index all content within the given programs, tracking the fact that a full reindex has taken place
        """
        # Generate new program index
        log.info('creating new index...')
        self._create_new_index()

        # Displace alias's index with a new program index name
        # Return unlinked program index list which was linked with this Alias before.
        log.info('linking new index with alias...')
        existing_indexs = self._searcher.displace_index_to_alias(
            self._new_index_name,
            self.INDEX_ALIAS_NAME
        )

        # Delete expired program index from ES
        log.info('removing expired index...')
        for old_index in existing_indexs:
            self._searcher.remove_by_index_name(old_index)
