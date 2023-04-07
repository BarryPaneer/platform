""" Management command to update courses' search index """
import logging
from textwrap import dedent

from django.core.management import BaseCommand, CommandError
from elasticsearch import exceptions
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import CourseLocator
from search.search_engine_base import SearchEngine

from contentstore.courseware_index import CoursewareSearchIndexer
from xmodule.modulestore.django import modulestore

from .prompt import query_yes_no


# Add fields to this value to be used for term-level queries(don't do analyzed to avoid separting words form strs)
NOT_ANALYZED_FIELDS = ['vendor', 'course_category', 'course_country', 'enrollment_learning_groups']


CONFIG_BODY = {
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
                    "filter":  [ "lowercase" ]
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
    "mappings": {
        "course_info": {
            "properties": {
                "content": {
                    "properties": {
                        "display_name": {
                            "type": "string",
                            "analyzer": "partword",
                            "fields": {
                                "raw_display_name": {
                                    "type": "string",
                                    "analyzer": "case_insensitive_sort"
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

CONFIG_BODY['mappings']['course_info']['properties'].update({key: {"type": "string", "index": "not_analyzed"} for key in NOT_ANALYZED_FIELDS})


class Command(BaseCommand):
    """
    Command to re-index courses

    Examples:

        ./manage.py reindex_course <course_id_1> <course_id_2> ... - reindexes courses with provided keys
        ./manage.py reindex_course --all - reindexes all available courses
        ./manage.py reindex_course --all --reconfig - reconfigures es index and reindexes all available courses
        ./manage.py reindex_course --setup - reindexes all courses for devstack setup
    """
    help = dedent(__doc__)
    CONFIRMATION_PROMPT = u"Re-indexing all courses might be a time consuming operation. Do you want to continue?"

    def add_arguments(self, parser):
        parser.add_argument('course_ids',
                            nargs='*',
                            metavar='course_id')
        parser.add_argument('--all',
                            action='store_true',
                            help='Reindex all courses')
        parser.add_argument('--reconfig',
                            action='store_true',
                            help='Do the index configuration')
        parser.add_argument('--setup',
                            action='store_true',
                            help='Reindex all courses on developers stack setup')

    def _parse_course_key(self, raw_value):
        """ Parses course key from string """
        try:
            result = CourseKey.from_string(raw_value)
        except InvalidKeyError:
            raise CommandError("Invalid course_key: '%s'." % raw_value)

        if not isinstance(result, CourseLocator):
            raise CommandError(u"Argument {0} is not a course key".format(raw_value))

        return result

    def config_index(self, index, body):
        """Reconfig es configuration according config body.
        """
        searcher = SearchEngine.get_search_engine(index)
        searcher._es.indices.close(index)
        searcher._es.indices.delete(index)
        searcher._es.indices.create(index, body=body)

    def handle(self, *args, **options):
        """
        By convention set by Django developers, this method actually executes command's actions.
        So, there could be no better docstring than emphasize this once again.
        """
        course_ids = options['course_ids']
        all_option = options['all']
        reconfig_option = options['reconfig']
        setup_option = options['setup']
        index_all_courses_option = all_option or setup_option

        if (not len(course_ids) and not index_all_courses_option) or \
                (len(course_ids) and index_all_courses_option):
            raise CommandError("reindex_course requires one or more <course_id>s OR the --all or --setup flags.")

        store = modulestore()

        index_name = CoursewareSearchIndexer.INDEX_NAME
        if index_all_courses_option:
            doc_type = CoursewareSearchIndexer.DOCUMENT_TYPE
            if setup_option:
                try:
                    # try getting the ElasticSearch engine
                    searcher = SearchEngine.get_search_engine(index_name)
                except exceptions.ElasticsearchException as exc:
                    logging.exception('Search Engine error - %s', exc)
                    return

                index_exists = searcher._es.indices.exists(index=index_name)  # pylint: disable=protected-access
                doc_type_exists = searcher._es.indices.exists_type(  # pylint: disable=protected-access
                    index=index_name,
                    doc_type=doc_type
                )

                index_mapping = searcher._es.indices.get_mapping(  # pylint: disable=protected-access
                    index=index_name,
                    doc_type=doc_type
                ) if index_exists and doc_type_exists else {}

                if index_exists and index_mapping:
                    return

            # if reindexing is done during devstack setup step, don't prompt the user
            if setup_option or query_yes_no(self.CONFIRMATION_PROMPT, default="no"):
                # in case of --setup or --all, get the list of course keys from all courses
                # that are stored in the modulestore
                course_keys = [course.id for course in modulestore().get_courses()]
            else:
                return
        else:
            # in case course keys are provided as arguments
            course_keys = map(self._parse_course_key, course_ids)

        if reconfig_option:
            self.config_index(index_name, CONFIG_BODY)

        for course_key in course_keys:
            CoursewareSearchIndexer.do_course_reindex(store, course_key)
