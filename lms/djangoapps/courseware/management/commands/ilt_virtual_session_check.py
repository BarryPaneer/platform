# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import logging
import os
import time

from datetime import datetime
from django.core.management.base import BaseCommand
from logging.handlers import TimedRotatingFileHandler
from courseware.views.views import process_virtual_session_check_email

logger = logging.getLogger("edx.scripts.ilt_virtual_session_check")

d = os.path.dirname('/edx/var/log/lms/ilt_virtual_session_check.log')
if not os.path.exists(d):
    os.makedirs(d)

log_handler = TimedRotatingFileHandler("/edx/var/log/lms/ilt_virtual_session_check.log",
                                       when="W0",
                                       backupCount=5,
                                       encoding="utf-8")
log_formatter = logging.Formatter('%(asctime)s [%(name)s] [%(filename)s:%(lineno)d] %(levelname)s  - %(message)s')
log_formatter.converter = time.gmtime
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)


class Command(BaseCommand):
    help = 'ILT virtual session daily/hourly check'

    def add_arguments(self, parser):
        parser.add_argument('--mode', action='append', type=str)

    def handle(self, *args, **options):
        time_mode = options['mode'][0]
        logger.info("Start ILT virtual session {} check...".format(time_mode))
        start_time = datetime.now()
        process_virtual_session_check_email(time_mode)
        logger.info(u"Finished ILT virtual session {} check after {}".format(time_mode, datetime.now() - start_time))
