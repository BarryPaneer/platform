import argparse
import pytz
import time
from datetime import datetime, timedelta
import logging
from triboo_analytics.models import TrackingLogHelper
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview


logger = logging.getLogger("triboo_analytics")
log_handler = logging.handlers.TimedRotatingFileHandler('/edx/var/log/lms/analytics.log',
                                                        when='W0',
                                                        backupCount=5,
                                                        encoding='utf-8')
log_formatter = logging.Formatter('%(asctime)s %(levelname)s  - %(message)s')
log_formatter.converter = time.gmtime
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)
logger.addHandler(log_handler)


if __name__ == '__main__':
    first_day = last_day = None

    parser = argparse.ArgumentParser(description='Calculate the time spent and section of all tracking logs between [first_day, last_day].')
    parser.add_argument('--first', help='the date of the first day, expecting: d m yyyy',
        nargs=3, type=int, required=True)
    parser.add_argument('--last', help='the date of the last day, expecting: d m yyyy',
        nargs=3, type=int, required=True)
    args = parser.parse_args()

    try:
        first_day = datetime(args.first[2], args.first[1], args.first[0], 0, 0, 0, 0, pytz.utc)
        last_day = datetime(args.last[2], args.last[1], args.last[0], 0, 0, 0, 0, pytz.utc)
    except ValueError:
        logger.fatal("Invalid dates")

    if first_day and last_day:
        logger.info("Starting to update tracking logs...")
        start_time = datetime.now()

        overviews = CourseOverview.objects.filter(start__lte=datetime.today())
        course_ids = [o.id for o in overviews]

        helper = TrackingLogHelper(course_ids)

        day = first_day
        while day <= last_day:
            logger.info("update tracking logs for %s" % day)
            helper.update_logs(day)
            day = day + timedelta(days=1)

        logger.info("Finished after {}".format(datetime.now() - start_time))
