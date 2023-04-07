#!/usr/bin/env python
"""
This script is to migrate the grade_log in courseenrollment to PersistentCourseGradeOverride
"""

from __future__ import unicode_literals
import logging
import time

from logging.handlers import RotatingFileHandler


logger = logging.getLogger("edx.scripts.progress_migration")

log_handler = RotatingFileHandler("/edx/var/log/lms/progress_migration.log",
                                  maxBytes=1024*1024*1024*5,
                                  backupCount=5,
                                  encoding="utf-8"
                                  )
log_formatter = logging.Formatter('%(asctime)s [%(name)s] [%(filename)s:%(lineno)d] %(levelname)s  - %(message)s')
log_formatter.converter = time.gmtime
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)


def flush():
    import psutil
    from django.core.cache import cache
    from openedx.core.djangoapps.request_cache import middleware
    mem = psutil.virtual_memory()
    usage = float(mem.used) / float(mem.total)
    if usage > 0.95:
        cache.clear()
        middleware.RequestCache.clear_request_cache()


def migrate_none_all_pass_enrollment(lock, course_possible_score_dict, enroll_id):
    from lms.djangoapps.grades.course_grade_factory import (
        calculate_eucalyptus_progress, CourseGradeFactory, get_total_score_possible)
    from lms.djangoapps.grades.models import PersistentSubsectionGrade, PersistentCourseProgress
    from openedx.core.lib.gating.api import complete_subsection
    from student.models import CourseEnrollment
    from xmodule.modulestore.django import modulestore

    try:
        # lock.acquire()
        enrollment = CourseEnrollment.objects.get(id=enroll_id)
        course_key = enrollment.course_id
        user = enrollment.user
        progress = PersistentCourseProgress.objects.filter(course_id=course_key, user_id=user.id)
        progress.delete()
        try:
            course_grade = CourseGradeFactory().read(user, course_key=course_key)
        except Exception as e:
            logger.error("Can't get course grade for CourseEnrollment: {}".format(enrollment.id))
            # lock.release()
            return
        subsection_grades = PersistentSubsectionGrade.objects.filter(
            user_id=user.id,
            course_id=course_key,
            possible_graded__gt=0
        )

        if not subsection_grades:
            logger.debug("enrollment: {enroll_id} has 0 score".format(enroll_id=enrollment.id))
            # lock.release()
            return
        if course_key in course_possible_score_dict:
            chapter_grades, possible_score = course_possible_score_dict[course_key]
        else:
            chapter_grades, possible_score = get_total_score_possible(course_key, user, course_grade=course_grade)
            course_possible_score_dict[course_key] = (chapter_grades, possible_score)
        del course_grade

        old_progress = calculate_eucalyptus_progress(possible_score, subsection_grades)
        old_progress = round(old_progress, 2)
        if old_progress == 1:
            course_usage_key = modulestore().make_course_usage_key(course_key)
            complete_subsection(course_usage_key, user)
        elif old_progress == 0:
            logger.debug("enrollment: {enroll_id} has 0 progress".format(enroll_id=enrollment.id))
            # lock.release()
            return
        else:
            for chapter, info in chapter_grades.items():
                subsection_keys = info['subsections']
                if not subsection_keys:
                    continue
                sub_grades = subsection_grades.filter(usage_key__in=subsection_keys)
                if sub_grades.count() == len(subsection_keys):
                    complete_subsection(chapter, user)
                else:
                    for i in sub_grades:
                        complete_subsection(i.usage_key, user)
        logger.info("CourseEnrollment: {} DONE".format(enroll_id))
        flush()
        # lock.release()
    except Exception as e:
        flush()
        logger.error("CourseEnrollment: {} FAILED, reason: {}".format(enroll_id, e))


def migrate_all_pass_enrollment(enroll_id):
    from lms.djangoapps.grades.models import PersistentCourseProgress
    from openedx.core.lib.gating.api import complete_subsection
    from student.models import CourseEnrollment
    from xmodule.modulestore.django import modulestore

    enrollment = CourseEnrollment.objects.get(id=enroll_id)
    course_key = enrollment.course_id
    user = enrollment.user

    progress = PersistentCourseProgress.objects.filter(course_id=course_key, user_id=user.id)
    if progress.exists():
        return

    try:
        course_usage_key = modulestore().make_course_usage_key(course_key)
        complete_subsection(course_usage_key, user)
        #logger.info("CourseEnrollment: {} ALL_PASS DONE".format(enroll_id))
    except Exception as e:
        logger.error("Fail to complete all for enrollment: {enroll_id}".format(
            enroll_id=enroll_id
        ))
    flush()


def migrate_progress():
    from functools import partial
    from django.db import connections
    from multiprocessing import Pool, cpu_count, Manager
    import sys
    import json
    from student.models import CourseEnrollment

    global migrate_none_all_pass_enrollment
    global migrate_all_pass_enrollment
    global flush

    global logger
    grade_logs = {}

    active_enrollments = CourseEnrollment.objects.all()
    all_pass_enrollments_id = [x for x, y in grade_logs.items() if "all_pass" in y]

    all_pass_enrollments = active_enrollments.filter(
        id__in=all_pass_enrollments_id).values_list('id', flat=True)
    all_pass_enrollments_id = [i for i in all_pass_enrollments]
    none_all_pass_enrollments_id = active_enrollments.exclude(
        id__in=all_pass_enrollments_id).values_list('id', flat=True)
    none_all_pass_enrollments_id = [i for i in none_all_pass_enrollments_id]
    all_pass_count = len(all_pass_enrollments_id)
    other_count = len(none_all_pass_enrollments_id)

    course_possible_score_dict = {}
    connections.close_all()

    pool = Pool(processes=cpu_count())
    m = Manager()
    lock = m.Lock()
    func = partial(migrate_none_all_pass_enrollment, lock, course_possible_score_dict)

    pool_counter = 0
    while True:
        pool_counter += 1
        try:
            for a, _ in enumerate(
                    pool.imap_unordered(func, none_all_pass_enrollments_id)):
                logger.info("round ({counter}) -- {x} / {y} completed, size: {z}".format(
                    counter=pool_counter, x=a, y=other_count, z=sys.getsizeof(course_possible_score_dict)))
        except Exception as e:
            # pool.terminate()
            # pool.join()
            # pool = Pool(processes=cpu_count())
            continue
        else:
            break

    pool.close()
    pool.join()

    pool_0 = Pool(processes=cpu_count())
    pool_0_counter = 0
    while True:
        pool_0_counter += 1
        try:
            for b, _ in enumerate(
                    pool_0.imap_unordered(
                        migrate_all_pass_enrollment, all_pass_enrollments_id)
            ):
                logger.info("round ({counter}) -- {x} / {y} all pass completed".format(
                    counter=pool_0_counter, x=b, y=all_pass_count))
        except Exception as e:
            pool_0.terminate()
            continue
        else:
            break
    pool_0.close()
    pool_0.join()


logger.info("start migrating progress ...")
migrate_progress()
logger.info("Done")