# -*- coding: utf-8 -*-
from __future__ import unicode_literals


def rename_mcq_blocks():
    from django.contrib.auth.models import User
    from openedx.core.djangoapps.content.block_structure.api import clear_course_from_cache
    from triboo_analytics.models import ANALYTICS_WORKER_USER
    from xmodule.modulestore.django import modulestore
    courses = modulestore().get_courses()
    worker = User.objects.get(username=ANALYTICS_WORKER_USER)
    for course in courses:
        course_key = course.id
        problems = modulestore().get_items(course_key, qualifiers={'category': 'problem'})
        for problem in problems:
            try:
                name = problem.display_name
                if name in ["Multiple Choice", "Checkboxes"]:
                    name = name.replace("Multiple Choice", "MCQ: single answer").replace(
                        "Checkboxes", "MCQ: multiple answers")
                    problem.display_name = name
                    modulestore().update_item(problem, worker.id)
                    modulestore().publish(problem.location, worker.id)
            except Exception as e:
                pass
        clear_course_from_cache(course_key)

rename_mcq_blocks()
