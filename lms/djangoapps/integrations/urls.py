from django.conf.urls import include, url
from . import views

urlpatterns = [
    url(r'^slack/message$', views.request_slack_send_message, name='send_slack_message'),
    url(r'^slack/lookup/$', views.request_slack_lookup_email, name='find_slack_user'),
]