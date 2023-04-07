# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import logging
import os
import time

from logging.handlers import TimedRotatingFileHandler
from triboo_analytics.models import LeaderBoardView


logger = logging.getLogger("triboo_analytics")

d = os.path.dirname('/edx/var/log/lms/leaderboard.log')
if not os.path.exists(d):
    os.makedirs(d)

log_handler = TimedRotatingFileHandler("/edx/var/log/lms/leaderboard.log",
                                       when="W0",
                                       backupCount=5,
                                       encoding="utf-8")
log_formatter = logging.Formatter('%(asctime)s [%(name)s] [%(filename)s:%(lineno)d] %(levelname)s  - %(message)s')
log_formatter.converter = time.gmtime
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)
logger.addHandler(log_handler)

logger.info("Start updating leaderboard weekly rank ...")
LeaderBoardView.calculate_last_week_rank()
logger.info("Finish.")
