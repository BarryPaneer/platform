"""
URLs for student app
"""

from django.conf import settings
from django.conf.urls import include, url
from django.contrib.auth.views import password_reset_complete

from . import views
from .rest_api.v1 import urls as v1_urls

urlpatterns = [
    url(r'^logout$', views.LogoutView.as_view(), name='logout'),

    # TODO: standardize login

    # login endpoint used by cms.
    url(r'^login_post$', views.studio_login, name='login_post'),
    # login endpoints used by lms.
    url(r'^login_ajax$', views.login_user, name="login"),
    url(r'^login_ajax/(?P<error>[^/]*)$', views.login_user),

    url(r'^email_confirm/(?P<key>[^/]*)$', views.confirm_email_change, name='confirm_email_change'),

    url(r'^create_account$', views.create_account, name='create_account'),
    url(r'^activate/(?P<key>[^/]*)$', views.activate_account, name="activate"),

    url(r'^accounts/disable_account_ajax$', views.disable_account_ajax, name="disable_account_ajax"),
    url(r'^accounts/manage_user_standing', views.manage_user_standing, name='manage_user_standing'),

    url(r'^change_setting$', views.change_setting, name='change_setting'),
    url(r'^change_email_settings$', views.change_email_settings, name='change_email_settings'),

    # password reset in views (see below for password reset django views)
    url(r'^password_reset/$', views.password_reset, name='password_reset'),
    url(
        r'^password_reset_confirm/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$',
        views.password_reset_confirm_wrapper,
        name='password_reset_confirm',
    ),

    url(r'^password_create_confirm/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$',
        views.password_create_confirm_wrapper,
        name='password_create_confirm'),
    url(r'^password_create_complete/$', views.password_create_complete,
        name='password_create_complete'),


    url(r'accounts/verify_password', views.verify_user_password, name='verify_password'),

    url(r'^course_run/{}/refund_status$'.format(settings.COURSE_ID_PATTERN),
        views.course_run_refund_status,
        name="course_run_refund_status"),
    url(r'^enrolled_ilt_sessions$', views.get_enrolled_ilt, name="enrolled_ilt_sessions"),
    url(r'^download_invitation/(?P<usage_id>(?:i4x://?[^/]+/[^/]+/[^/]+/[^@]+(?:@[^/]+)?)|(?:[^/]+))/'
        r'(?P<session_id>[0-9]+)/$', views.SessionInvitationPdf.as_view(), name='download_invitation'),
    url(r'^admin_panel/users/?$', views.AdminPanel.as_view(), name="admin_panel_user_list"),
    url(r'^admin_panel/users/create/$', views.create_user, name="admin_panel_user_create"),
    url(r'^admin_panel/users/(?P<user_id>[0-9]+)/$', views.edit_user, name="admin_panel_user_edit"),
    url(r'^admin_panel/users/(?P<user_id>[0-9]+)/password/$',
        views.admin_panel_user_password_reset,
        name="admin_panel_user_password_reset"),
    url(r'^admin_panel/csv_registration/?$', views.csv_registration, name="admin_panel_csv_registration"),
    url(r'^admin_panel/batch_enrollment/?$', views.batch_enrollment, name="admin_panel_batch_enrollment"),
    url(r'^admin_panel/csv_registration/register_students_precheck$', views.batch_register_students_precheck,
        name="admin_panel_batch_register_students_precheck"),
    url(r'^admin_panel/csv_registration/register_students$', views.batch_register_students,
        name="admin_panel_batch_register_students"),
    url(r'^admin_panel/csv_registration/update_students$', views.batch_update_students,
        name="admin_panel_batch_update_students"),
    url(r'^admin_panel/csv_registration/send_welcoming_email$', views.batch_send_welcoming_email,
        name="admin_panel_batch_send_welcoming_email"),
    url(r'^admin_panel/batch_enrollment/enroll_in_course$', views.batch_enroll_in_course, name='admin_panel_batch_enroll_in_course'),
    url(r'^admin_panel/batch_enrollment/enroll_in_program$', views.batch_enroll_in_program, name='admin_panel_batch_enroll_in_program'),
    url(r'^admin_panel/platform_configuration/$', views.platform_configuration,
        name="platform_configuration"),
    url(r'^admin_panel/v1/', include(v1_urls))
]

# enable automatic login
if settings.FEATURES.get('AUTOMATIC_AUTH_FOR_TESTING'):
    urlpatterns += [
        url(r'^auto_auth$', views.auto_auth),
    ]

# password reset django views (see above for password reset views)
urlpatterns += [
    # TODO: Replace with Mako-ized views
    url(
        r'^password_reset_complete/$',
        password_reset_complete,
        name='password_reset_complete',
    ),
]
