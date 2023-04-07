from django.conf.urls import url

from .views import DiscoveryRequestProxy


urlpatterns = [
    # Note: please access program in discovery from CMS.
    # Don't use api in Service Discovery directly.
    url(r'^discovery', DiscoveryRequestProxy.as_view(), name='discovery_request_proxy')
]
