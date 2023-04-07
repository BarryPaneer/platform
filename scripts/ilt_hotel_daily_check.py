# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import logging
import os
import time

from logging.handlers import TimedRotatingFileHandler
from courseware.views.views import process_ilt_hotel_check_email, process_ilt_validation_check_email


logger = logging.getLogger("edx.scripts.ilt_hotel_daily_check")

d = os.path.dirname('/edx/var/log/lms/ilt_hotel_daily_check.log')
if not os.path.exists(d):
    os.makedirs(d)

log_handler = TimedRotatingFileHandler("/edx/var/log/lms/ilt_hotel_daily_check.log",
                                       when="W0",
                                       backupCount=5,
                                       encoding="utf-8")
log_formatter = logging.Formatter('%(asctime)s [%(name)s] [%(filename)s:%(lineno)d] %(levelname)s  - %(message)s')
log_formatter.converter = time.gmtime
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)


logger.info("Start ilt hotel booking daily check ...")
process_ilt_hotel_check_email()
logger.info("Finish daily check.")
