from django.core.management.base import BaseCommand
from datetime import datetime
from traceback import format_exc
from lms.djangoapps.external_catalog.models import AndersPinkBoard
from ...api import AnderspinkResourcesSynchronizer
from django.core.exceptions import ImproperlyConfigured
from lms.djangoapps.external_catalog.utils import ExternalCatalogLogger
from ...tasks import log
from ...utils import get_anderspink_configuration
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.django import modulestore

logger = ExternalCatalogLogger(r'anderspink_external_catalog_update.log').logger


class Command(BaseCommand):
    help = 'Sync. briefing from anderspink briefing provider into mysql.'

    def _sync_briefing(self):
        anderspink_configuration = get_anderspink_configuration()

        if not all(
                (anderspink_configuration['api_key'], anderspink_configuration['base_url'],
                 anderspink_configuration['api_time'])
        ):
            raise ImproperlyConfigured(
                'In order to use API for Anderspink of the followings must be configured: '
                'ANDERSPINK_CLIENT_KEY, ANDERSPINK_BASE_API_URL'
            )

        AnderspinkResourcesSynchronizer(
            api_key=anderspink_configuration['api_key'],
            base_api_url=anderspink_configuration['base_url'],
            api_time=anderspink_configuration['api_time'],
            is_board_enabled=anderspink_configuration['is_board_enabled']
        ).run()

    def update_course_details(self):
        board_id = []
        user_id = 1  # provide a valid user id for a client

        course_keys = CourseOverview.get_all_course_keys()
        anderspink_boards = AndersPinkBoard.objects.all()
        for board in anderspink_boards:
            board_id.append(str(board.board_id))

        for expected_course_key in course_keys:
            course = modulestore().get_course(expected_course_key)
            course_board_id = str(course.anderspink_boards)
            if course_board_id not in board_id:
                course.anderspink_boards = ""
                modulestore().update_item(course, user_id=user_id)

    def handle(self, *args, **options):
        try:
            log.info(r'Starting requesting the anderspink briefing data...')

            start_time = datetime.now()
            self._sync_briefing()
            self.update_course_details()

            log.info(r'Finished all requests after {}'.format(datetime.now() - start_time))
        except Exception:
            log.error('Unknow exception occured in script, Traceback ===> {}'.format(format_exc()))