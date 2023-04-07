# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.shortcuts import render_to_response
from django.contrib.auth.models import User
from opaque_keys.edx.keys import CourseKey
from courseware.courses import get_course_with_access
from courseware.access import has_access
from lms.djangoapps.courseware.views.views import get_last_accessed_courseware, registered_for_course
from django.urls import reverse
from django.conf import settings
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.db import transaction
from util.views import ensure_valid_course_key
from django.views.decorators.cache import cache_control
from courseware.masquerade import setup_masquerade
from courseware.access import has_access, has_ccx_coach_role
from lms.djangoapps.ccx.custom_exception import CCXLocatorValidationException


@login_required
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@ensure_valid_course_key
@login_required
def board(request, course_id, student_id=None):
    course_key = CourseKey.from_string(course_id)
    course = get_course_with_access(request.user, "load", course_key)
    if student_id is not None:
        try:
            student_id = int(student_id)
        # Check for ValueError if 'student_id' cannot be converted to integer.
        except ValueError:
            raise Http404

    staff_access = bool(has_access(request.user, 'staff', course))

    masquerade = None
    if student_id is None or student_id == request.user.id:
        # This will be a no-op for non-staff users, returning request.user
        masquerade, student = setup_masquerade(request, course_key, staff_access, reset_masquerade_data=True)
    else:
        try:
            coach_access = has_ccx_coach_role(request.user, course_key)
        except CCXLocatorValidationException:
            coach_access = False

        has_access_on_students_profiles = staff_access or coach_access
        # Requesting access to a different student's profile
        if not has_access_on_students_profiles:
            raise Http404
        try:
            student = User.objects.get(id=student_id)
        except User.DoesNotExist:
            raise Http404

    student = User.objects.prefetch_related("groups").get(id=student.id)
    course_grade = CourseGradeFactory().read(student, course)
    progress_summary = CourseGradeFactory().get_progress(student, course, grade_summary=course_grade)
    show_courseware_link = bool(
        (
            has_access(request.user, 'load', course)
        ) or settings.FEATURES.get('ENABLE_LMS_MIGRATION')
    )

    if has_access(request.user, 'load', course):
        course_target = get_last_accessed_courseware(request, course)
    else:
        course_target = reverse('about_course', args=[text_type(course.id)])

    context = {
        "course": course,
        'staff_access': staff_access,
        "show_courseware_link": show_courseware_link,
        "user": request.user,
        'registered': registered_for_course(course, request.user),
        "course_target": course_target,
        'progress': int(progress_summary['progress'] * 100)

    }

    return render_to_response("courseware/board_articles.html", context)
