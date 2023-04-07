from django.conf.urls import include, url

from . import views


urlpatterns = [
    url(r'^v1/', include('cms.djangoapps.api.v1.urls', namespace='v1')),
    url(r'^upload_local/(?P<upload_video_name>.+)$', views.request_upload_local_file, name='upload_local_file'),
    url(r'^proxy/', include('cms.djangoapps.api.proxy.urls', namespace='proxy')),
    url(r'^all_languages$', views.all_languages, name='all_languages'),
    url(
        r'^system_released_languages$',
        views.system_released_languages,
        name='system_released_languages'
    ),
    # Program Teams Api
    url(
        r'^team/',
        include('lms.djangoapps.teams.program_api_urls')
    ),
]
