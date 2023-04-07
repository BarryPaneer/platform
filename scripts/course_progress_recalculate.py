#!/usr/bin/env python
"""
This script is to recalcualte course progress for learners whose score was overridden by
gradebook edit before.
"""
from __future__ import unicode_literals

import logging

from django.contrib.auth.models import User
from django.utils import timezone
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from lms.djangoapps.grades.models import PersistentSubsectionGradeOverride
from lms.djangoapps.grades.signals.signals import GRADE_EDITED
from student.models import CourseEnrollment

log = logging.getLogger(__name__)


def recalculate_progress():
    all_overrides = PersistentSubsectionGradeOverride.objects.all().select_related('grade')
    course_key_user_pairs = [(i.grade.course_id, i.grade.user_id) for i in all_overrides]
    course_key_user_pairs = list(set(course_key_user_pairs))
    total = len(course_key_user_pairs)
    n = 0
    for key, user_id in course_key_user_pairs:
        user = User.objects.get(id=user_id)
        enrollment = CourseEnrollment.get_enrollment(user, key)
        if enrollment is None:
            continue
        CourseGradeFactory().update_course_completion_percentage(key, user, enrollment=enrollment)
        GRADE_EDITED.send(
            sender=None,
            user_id=user_id,
            course_id=key,
            modified=timezone.now(),
        )
        n += 1
        log.info("course_key: {k}, user: {u}, {x} / {y} finished".format(
            k=unicode(key),
            u=user_id,
            x=n,
            y=total
        ))
