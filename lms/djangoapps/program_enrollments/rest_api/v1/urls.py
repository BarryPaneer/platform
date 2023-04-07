""" Program Enrollments API v1 URLs. """


from django.conf.urls import include
from django.conf.urls import url

from rest_framework_nested import routers

from .views import (
    UserProgramsAccessView,
    UserReadView,
    UserProgramCoursesAccessView,
)

app_name = 'v1'


user_router = routers.SimpleRouter()
user_router.register(r'users', UserReadView, base_name=r'users')

user_programs_router = routers.NestedSimpleRouter(user_router, r'users', lookup=r'user')
user_programs_router.register(r'programs', UserProgramsAccessView, base_name=r'programs')

program_courses_router = routers.NestedSimpleRouter(user_programs_router, r'programs', lookup=r'program')
program_courses_router.register(r'courses', UserProgramCoursesAccessView, base_name=r'courses')

urlpatterns = [
    url(r'^', include(user_router.urls)),
    url(r'^', include(user_programs_router.urls)),
    url(r'^', include(program_courses_router.urls)),
]
