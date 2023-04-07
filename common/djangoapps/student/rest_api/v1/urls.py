""" Users API v1 URLs. """

from django.conf.urls import include
from django.conf.urls import url

from rest_framework_nested import routers

from .views import StudentsView


app_name = 'v1'


user_router = routers.SimpleRouter()
user_router.register(r'students', StudentsView, base_name=r'students')


urlpatterns = (
    url(r'^', include(user_router.urls)),
)
