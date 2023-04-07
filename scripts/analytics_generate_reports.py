import logging
import time
from datetime import datetime
from triboo_analytics.models import generate_today_reports


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


logger.info("Starting Triboo Analytics...")
start_time = datetime.now()

generate_today_reports(multi_process=False)

logger.info("Finished reports after {}".format(datetime.now() - start_time))
