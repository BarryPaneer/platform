"""
Grade book view for instructor and pagination work (for grade book)
which is currently use by ccx and instructor apps.
"""
import math

from django.contrib.auth.models import User
from django.urls import reverse
from django.db import transaction
from django.db.models import Q
from django.views.decorators.cache import cache_control
from opaque_keys.edx.keys import CourseKey

from courseware.courses import get_course_with_access
from courseware.views.views import get_last_accessed_courseware
from edxmako.shortcuts import render_to_response
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from lms.djangoapps.instructor.views.api import require_level
from lms.djangoapps.instructor.views.instructor_dashboard import get_instructor_tabs
from xmodule.modulestore.django import modulestore

# Grade book: max students per page
MAX_STUDENTS_PER_PAGE_GRADE_BOOK = 20


def calculate_page_info(offset, total_students):
    """
    Takes care of sanitizing the offset of current page also calculates offsets for next and previous page
    and information like total number of pages and current page number.

    :param offset: offset for database query
    :return: tuple consist of page number, query offset for next and previous pages and valid offset
    """

    # validate offset.
    if not (isinstance(offset, int) or offset.isdigit()) or int(offset) < 0 or int(offset) >= total_students:
        offset = 0
    else:
        offset = int(offset)

    # calculate offsets for next and previous pages.
    next_offset = offset + MAX_STUDENTS_PER_PAGE_GRADE_BOOK
    previous_offset = offset - MAX_STUDENTS_PER_PAGE_GRADE_BOOK

    # calculate current page number.
    page_num = ((offset / MAX_STUDENTS_PER_PAGE_GRADE_BOOK) + 1)

    # calculate total number of pages.
    total_pages = int(math.ceil(float(total_students) / MAX_STUDENTS_PER_PAGE_GRADE_BOOK)) or 1

    if previous_offset < 0 or offset == 0:
        # We are at first page, so there's no previous page.
        previous_offset = None

    if next_offset >= total_students:
        # We've reached the last page, so there's no next page.
        next_offset = None

    return {
        "previous_offset": previous_offset,
        "next_offset": next_offset,
        "page_num": page_num,
        "offset": offset,
        "total_pages": total_pages
    }


def get_grade_book_page(request, course, course_key):
    """
    Get student records per page along with page information i.e current page, total pages and
    offset information.
    """
    # Unsanitized offset
    current_offset = request.GET.get('offset', 0)
    search_query = request.GET.get('learner_name', '')
    enrolled_students = User.objects.filter(
        Q(profile__name__icontains=search_query) | Q(username__icontains=search_query),
        is_active=True,
        courseenrollment__course_id=course_key,
        courseenrollment__is_active=1
    ).order_by('profile__name').select_related("profile")

    total_students = enrolled_students.count()
    page = calculate_page_info(current_offset, total_students)
    offset = page["offset"]
    total_pages = page["total_pages"]

    if total_pages > 1:
        # Apply limit on queryset only if total number of students are greater then MAX_STUDENTS_PER_PAGE_GRADE_BOOK.
        enrolled_students = enrolled_students[offset: offset + MAX_STUDENTS_PER_PAGE_GRADE_BOOK]

    with modulestore().bulk_operations(course.location.course_key):
        student_info = []
        for student in enrolled_students:
            course_grade = CourseGradeFactory().read(student, course)
            grade_summary = course_grade.summary
            graded_subsections = course_grade.graded_subsections_by_format
            section_breakdown = grade_summary['section_breakdown']
            for section in section_breakdown:
                sections_by_format = graded_subsections.get(section.get('category'))
                if sections_by_format:
                    pair = sections_by_format.popitem(last=False)
                    section['usage_key'] = unicode(pair[0])
                    if pair[1].override is not None:
                        section['override'] = True
                        grade_summary['override'] = True
                else:
                    continue
            info = {
                'username': student.profile.name or student.username,
                'id': student.id,
                'email': student.email,
                'grade_summary': grade_summary
            }
            student_info.append(info)
    return student_info, page


@transaction.non_atomic_requests
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_level('staff')
def spoc_gradebook(request, course_id):
    """
    Show the gradebook for this course:
    - Only shown for courses with enrollment < settings.FEATURES.get("MAX_ENROLLMENT_INSTR_BUTTONS")
    - Only displayed to course staff
    """
    course_key = CourseKey.from_string(course_id)
    course = get_course_with_access(request.user, 'staff', course_key, depth=None)
    student_info, page = get_grade_book_page(request, course, course_key)
    sections = get_instructor_tabs(request, request.user, course)

    if request.method == 'GET':
        query_name = ''
        page_url = request.get_full_path()
        if page_url.rfind('offset') > -1:
            page_url = page_url[0:page_url.rfind('offset')]
        else:
            if 'learner_name' in page_url:
                query_name = request.GET.get('learner_name')
                page_url = page_url + '&'
            else:
                page_url = page_url + '?'

        resume_course_url = get_last_accessed_courseware(request, course)
        progress = CourseGradeFactory().get_course_completion_percentage(
                                        request.user, course.id)
        progress = int(progress * 100)

        return render_to_response('instructor/instructor_dashboard_2/gradebook.html', {
            'page': page,
            'page_url': page_url,
            'students': student_info,
            'course': course,
            'course_id': course_key,
            # Checked above
            'staff_access': True,
            'show_courseware_link': True,
            'resume_course_url': resume_course_url,
            'progress': progress,
            'ordered_grades': sorted(course.grade_cutoffs.items(), key=lambda i: i[1], reverse=True),
            'sections': sections,
            'query': query_name
        })
