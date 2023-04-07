""" Course API URLs. """
from django.conf import settings
from django.conf.urls import url

from cms.djangoapps.contentstore.api.views import (
    course_import,
    course_validation,
    course_quality,
    courses_query,
    course_steps_validation
)


urlpatterns = [
    url(r'^v0/import/{course_id}/$'.format(course_id=settings.COURSE_ID_PATTERN,),
        course_import.CourseImportView.as_view(), name='course_import'),
    url(r'^v1/validation/{course_id}/$'.format(course_id=settings.COURSE_ID_PATTERN,),
        course_validation.CourseValidationView.as_view(), name='course_validation'),
    url(r'^v1/quality/{course_id}/$'.format(course_id=settings.COURSE_ID_PATTERN,),
        course_quality.CourseQualityView.as_view(), name='course_quality'),
    url(
        r'^v1/courses/$',
        courses_query.UserCourseListView.as_view(),
        name='user_courses_query'
    ),
    url(
        r'^v1/steps_validation/{course_id}/$'.format(course_id=settings.COURSE_ID_PATTERN),
        course_steps_validation.CourseStepsValidationView.as_view(), name='course_steps_validation'
    )
]
