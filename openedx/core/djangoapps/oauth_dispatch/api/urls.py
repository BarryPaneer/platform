from django.conf import settings
from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^v0/application/(?P<email>[\w.%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4})$', views.request_user_application, name='user_dot_application'),
    url(r'^v0/application/$', views.request_user_application_action, name='user_dot_application_action'),
    ]
