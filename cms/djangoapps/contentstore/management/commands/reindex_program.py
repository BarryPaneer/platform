"""
    Management command to update Program' search index.

    Checking for programs index details with command as follow:
        `curl --header 'Content-Type: application/json' -XGET http://edx.devstack.elasticsearch:9200/program_index/_search?pretty=true`

    Listing for all programs index with command as follow:
        `curl --header 'Content-Type: application/json' -XGET http://edx.devstack.elasticsearch:9200/_cat/indices/program_index_*?pretty=true`

"""
import logging
from textwrap import dedent

from django.core.management import BaseCommand, CommandError

from contentstore.program_index import ProgramESIndex
from .prompt import query_yes_no


class Command(BaseCommand):
    """Command to re-index programs


        Supporting for Hot re-index:

            - Create a new program index ( Unique index Name: `program_index_20210604090102` )
            - Setup index mapping for this new index in ES.
            - Relate this new index with ES Alias ( Index Alias Name: `program_index` )
            - Remove the expired index from ES.


        Usages:

        ./manage.py reindex_program <program_uuid_1> <program_uuid_2> ...   - reindexes programs with provided keys

        ./manage.py reindex_program --all       - reindexes all available programs

    """
    help = dedent(__doc__)

    def add_arguments(self, parser):
        parser.add_argument(
            'program_ids',
            nargs='*',
            metavar='program_id'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Reindex all programs'
        )

    def handle(self, *args, **options):
        """Reindex Programs by options"""
        specified_program_ids = options['program_ids']
        index_all_programs_flag = options['all']

        if (not len(specified_program_ids) and not index_all_programs_flag) \
                or \
                (len(specified_program_ids) and index_all_programs_flag):
            raise CommandError('reindex_program requires one or more <program_uuid>s OR the --all flags.')

        if not query_yes_no(
            'Re-indexing all programs might be a time consuming operation. Do you want to continue?', default="no"
        ):
            return

        # Reindex Programs as follow...
        program_index = ProgramESIndex(specified_program_ids)

        logging.info(
            'Begin to reindex programs into ES..., with new index name [{}] ---> alias name [{}]'.format(
                program_index.get_index_name(),
                ProgramESIndex.INDEX_ALIAS_NAME
            )
        )

        program_index.run_hot_index()

        logging.info('Done.')
