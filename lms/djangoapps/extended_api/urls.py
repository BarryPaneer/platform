from django.conf.urls import include
from django.conf.urls import url
from rest_framework.routers import DefaultRouter

from .views import (
    BulkEnrollView,
    CourseOutlineViewSet,
    CourseProgressViewSet,
    CoursesViewSet,
    ILTLearnerReportViewSet,
    UsersByEmailViewSet,
    UsersByUsernameViewSet,
    UserSSOByUsernameViewSet,
    UserSSOViewSet,
    UsersViewSet,
    UserProgressByEmailViewSet,
    UserProgressByUsernameViewSet,
    UserProgressViewSet,
)

router = DefaultRouter()
router.register(r'users', UsersViewSet, base_name='users')
router.register(r'users_by_username', UsersByUsernameViewSet, base_name='users_by_username')
router.register(r'users_by_email', UsersByEmailViewSet, base_name='users_by_email')
router.register(r'courses', CoursesViewSet, base_name='courses')
router.register(r'ilt_learner_report', ILTLearnerReportViewSet, base_name='ilt_learner_report')
router.register(r'course_outline', CourseOutlineViewSet, base_name='course_outline')
router.register(r'user_progress_report', UserProgressViewSet, base_name='user_progress_report')
router.register(r'course_progress_report', CourseProgressViewSet, base_name='course_progress_report')
router.register(
    r'user_progress_report_by_username', UserProgressByUsernameViewSet, base_name='user_progress_report_by_username'
)
router.register(
    r'user_progress_report_by_email', UserProgressByEmailViewSet, base_name='user_progress_report_by_email'
)
router.register(r'user_sso', UserSSOViewSet, base_name='user_sso')
router.register(r'user_sso_by_username', UserSSOByUsernameViewSet, base_name='user_sso_by_username')

urlpatterns = [
    url(r'^v1/', include(router.urls)),
    url(r'^v1/bulk_enroll', BulkEnrollView.as_view(), name='bulk_enroll'),
]
