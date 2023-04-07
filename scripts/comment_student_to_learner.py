# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import logging
import time

from logging.handlers import TimedRotatingFileHandler
from django_comment_common.models import Role
from xmodule.modulestore.django import modulestore


logger = logging.getLogger("edx.scripts.comment_student_to_learner")
log_handler = TimedRotatingFileHandler("/edx/var/log/lms/comment_student_to_learner.log",
                                       when="W0",
                                       backupCount=5,
                                       encoding="utf-8")
log_formatter = logging.Formatter('%(asctime)s [%(name)s] [%(filename)s:%(lineno)d] %(levelname)s  - %(message)s')
log_formatter.converter = time.gmtime
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)


def student2learner():
    """
    To change student to learner of roles in comment module
    """
    all_courses = modulestore().get_courses()
    course_ids = [course.id for course in all_courses]
    for course_id in course_ids:
        try:
            student_roles = Role.objects.filter(name="Student", course_id=course_id)
            learner_roles = Role.objects.filter(name="Learner", course_id=course_id)
            # Course with both student and learner roles
            if student_roles and learner_roles:
                student_role = student_roles[0]
                learner_role = learner_roles[0]
                additional_relationship = learner_role.users.all()
                student_role.users.add(*additional_relationship)
                learner_role.users.clear()
                learner_role.delete()
            logger.info("course ID: {course_id}, status: success".format(
                course_id=course_id,
            ))
        except Exception as e:
            logger.error("course ID: {course_id}, status: failed, reason: {reason}".format(
                course_id=course_id,
                reason=e.message
            ))
    # Rename all roles of "Student" to "Learner"
    for course_id in course_ids:
        try:
            student_roles = Role.objects.filter(name="Student", course_id=course_id)
            if student_roles:
                student_role = student_roles[0]
                student_role.name = 'Learner'
                student_role.save()
            logger.info("course ID: {course_id}, status: success".format(
                course_id=course_id,
            ))
        except Exception as e:
            logger.error("course ID: {course_id}, status: failed, reason: {reason}".format(
                course_id=course_id,
                reason=e.message
            ))


logger.info("start changing student to learner of roles in comment module...")
student2learner()
logger.info("Done!")
