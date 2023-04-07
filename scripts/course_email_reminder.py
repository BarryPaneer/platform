#!/usr/bin/env python
"""
This script is to check courses that have reminder settings.

It will be send email to students who have enrolled in the course
when the difference between the enrollment data and today matches one
of the reminders.

And when students automatically enrolled in the course, we send them
email and reset his/her status on this course and send remind email
again when the data matches
"""
from __future__ import division

import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler

from courseware.views.views import CourseReminder


logger = logging.getLogger("edx.scripts.course_email_reminder")

d = os.path.dirname('/edx/var/log/lms/course_email_reminder.log')
if not os.path.exists(d):
    os.makedirs(d)

log_handler = TimedRotatingFileHandler("/edx/var/log/lms/course_email_reminder.log",
                                       when="W0",
                                       backupCount=5,
                                       encoding="utf-8")
log_formatter = logging.Formatter('%(asctime)s [%(name)s] [%(filename)s:%(lineno)d] %(levelname)s  - %(message)s')
log_formatter.converter = time.gmtime
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)


logger.info("start to send reminder emails...")
CourseReminder().process_email()
logger.info("finish sending reminder emails.")
