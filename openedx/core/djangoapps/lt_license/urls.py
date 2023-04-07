from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^v0/count/$', views.request_count_license, name='count_license'),
    url(r'^v0/check/$', views.request_check_license, name='check_license'),
    url(r'^v0/send_mail/$', views.request_send_mail_license, name='send_mail_license'),
    ]
