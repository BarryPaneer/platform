#!/usr/bin/env python
"""
This script must run under cms.settings environment
"""

from __future__ import unicode_literals
import logging
import os
import time

from logging.handlers import TimedRotatingFileHandler


logger = logging.getLogger("edx.scripts.badge_name_split")
d = os.path.dirname('/edx/var/log/cms/badge_name_split.log')
if not os.path.exists(d):
    os.makedirs(d)

log_handler = TimedRotatingFileHandler("/edx/var/log/cms/badge_name_split.log",
                                       when="W0",
                                       backupCount=5,
                                       encoding="utf-8")
log_formatter = logging.Formatter('%(asctime)s [%(name)s] [%(filename)s:%(lineno)d] %(levelname)s  - %(message)s')
log_formatter.converter = time.gmtime
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)


def split_name_and_threshold():
    from django.contrib.auth.models import User
    from xmodule.modulestore.django import modulestore
    global logger
    staff, _ = User.objects.get_or_create(username="staff")
    courses = modulestore().get_courses()
    for course in courses:
        update_course = False
        graders = course.raw_grader
        try:
            for grader in graders:
                short_label = grader.get("short_label")
                if short_label:
                    tmp = short_label.rsplit("_", 1)
                    if len(tmp) > 1 and tmp[-1].isdigit():
                        update_course = True
                        grader['short_label'] = tmp[0]
                        grader['threshold'] = float(tmp[-1]) / 100
            if update_course:
                modulestore().update_item(course, staff.id)
                logger.info("Finished splitting badge name and threshold for course: {course_id}".format(
                    course_id=unicode(course.id)
                ))
        except Exception as e:
            logger.error("Failed to split badge name and threshold for course: {course_id}, error: {error}".format(
                course_id=unicode(course.id),
                error=e.message
            ))


logger.info("Start splitting badge and threshold ...")
split_name_and_threshold()
logger.info("Finish splitting badge and threshold.")
