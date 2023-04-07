from celery import task
from .views import InitialSlack

from celery.utils.log import get_task_logger

log = get_task_logger(__name__)


@task()
def default_slack_message():
    default_slack_message_result = InitialSlack()
    default_slack_message_result.slack_send_message()