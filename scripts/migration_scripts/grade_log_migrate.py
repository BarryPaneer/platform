#!/usr/bin/env python
"""
This script is to migrate the grade_log in courseenrollment to PersistentCourseGradeOverride
"""

from __future__ import unicode_literals
import logging
import os
import time
import json

from logging.handlers import TimedRotatingFileHandler


logger = logging.getLogger("edx.scripts.grade_log_migration")

log_handler = TimedRotatingFileHandler("/edx/var/log/lms/grade_migration.log",
                                       when="W0",
                                       backupCount=5,
                                       encoding="utf-8")
log_formatter = logging.Formatter('%(asctime)s [%(name)s] [%(filename)s:%(lineno)d] %(levelname)s  - %(message)s')
log_formatter.converter = time.gmtime
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)

with open('/edx/app/edxapp/edx-platform/scripts/sitel_migration/data.json') as json_file:
    grade_logs = json.load(json_file)

course_subsections_by_format = {}
failed_data = {}


def collect_data():
    import json
    from student.models import CourseEnrollment
    from xmodule.modulestore.django import modulestore
    global grade_logs
    global course_subsections_by_format
    global failed_data
    enrollments = CourseEnrollment.objects.filter(id__in=grade_logs)
    enrollment_ids = [str(i.id) for i in enrollments]
    bulk_request = {}
    for i in grade_logs:
        if i not in enrollment_ids:
            failed_data[i] = grade_logs[i]
    for i in enrollments:
        course_key = i.course_id
        user = i.user
        if course_key in course_subsections_by_format:
            pass
        else:
            try:
                course_subsections_by_format[course_key] = {}
                blocks = modulestore().get_items(course_key)
                blocks = [b for b in blocks if b.category == "sequential" and b.graded]
                for b in blocks:
                    if b.format in course_subsections_by_format[course_key]:
                        course_subsections_by_format[course_key][b.format].append(b.location)
                    else:
                        course_subsections_by_format[course_key][b.format] = []
                        course_subsections_by_format[course_key][b.format].append(b.location)

            except Exception as e:
                pass

        grade_log = json.loads(grade_logs[str(i.id)])
        usage_keys_by_format = course_subsections_by_format[course_key]

        if course_key in bulk_request:
            pass
        else:
            bulk_request[course_key] = {}

        if 'all_pass' in grade_log:
            keys = []
            for value in usage_keys_by_format.values():
                keys += value
        else:
            keys = []
            for x, y in grade_log.items():
                if x in usage_keys_by_format:

                    if 'Avg' in y:
                        keys += usage_keys_by_format[x]
                    elif len(y) == 1 and not y[0].isdigit():
                        keys += usage_keys_by_format[x]
                    else:
                        for index in y:
                            if index.isdigit():
                                position = int(index) - 1
                                if position < len(usage_keys_by_format[x]):
                                    keys.append(usage_keys_by_format[x][position])
                else:
                    pass

        bulk_request[course_key][user] = keys
    return bulk_request


def migrate_grade_log(bulk_request):
    import json
    from django.contrib.auth.models import User
    from lms.djangoapps.grades.api.v1.gradebook_views import bulk_grade_override
    from xmodule.modulestore.django import modulestore
    global logger
    request_user, _ = User.objects.get_or_create(username='staff')
    for course_key, user_dict in bulk_request.items():
        course = modulestore().get_course(course_key)
        for user, usage_keys in user_dict.items():
            try:
                bulk_grade_override(course, course_key, request_user, user, usage_keys)
            except Exception as e:
                logger.error("Failed to migration grade for user: {user_id}, course: {course_id}".format(
                    user_id=user.id,
                    course_id=unicode(course_key)
                ))
    with open("/edx/var/log/lms/failed_data.json", "w") as outfile:
        json.dump(failed_data, outfile)


logger.info("start migrating grade_log ...")
bulk_request = collect_data()
migrate_grade_log(bulk_request)
logger.info("Done")
