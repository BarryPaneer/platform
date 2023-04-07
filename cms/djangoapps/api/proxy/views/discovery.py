"""
    This module is a http request proxy:

        From   CMS api  to   Discovery api

"""
from functools import wraps
from json import loads as json_loads
import logging
from re import compile
from slumber.exceptions import HttpClientError, HttpServerError

from django.conf import settings
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework.parsers import FormParser
from rest_framework.parsers import MultiPartParser
from rest_framework import permissions

from lms.djangoapps.program_enrollments.programs import (
    ProgramListLoader,
    ProgramLoader,
    ProgramCoursesLoader,
    CoursesLoader,
    ProgramCreator,
    ProgramCourseRegister,
    ProgramCourseReorder,
    ProgramPartialUpdate,
    ProgramEraser,
    ProgramCourseEraser
)
from common.djangoapps.util.rest_csrfexempt_session_auth import CsrfExemptSessionAuthentication
from rest_framework.authentication import BasicAuthentication
from opaque_keys.edx.keys import CourseKey
from openedx.core.lib.api.parsers import TypedFileUploadParser
from xmodule.modulestore.django import modulestore
from util.json_request import JsonResponse


log = logging.getLogger(__name__)


class _expose_disapi_response(object):
    """Catch any exception of discovery api and return the Raw Exception Content as json to client

        Because user need to get the raw response from discovery service.
    """
    def __init__(self, *args):
        """args: a exception list which need to be catched."""
        self._exceptions = args

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except self._exceptions as e:
                return JsonResponse(
                    e.content, status=500
                )

        return wrapper


class DiscoveryRequestProxy(APIView):
    """A http request proxy for `discovery service api`

        - Permissions checking in CMS.
        - Perform additional logic in CMS.
        - Commit request to Discovery Service api.

    """
    REGEX_PROGRAM_UUID_PATTERN = compile(r'([A-Fa-f0-9-]{20,})')

    REGEX_GET_COURSES_PATTERN = compile(r'/api/v1/courses/')
    REGEX_GET_PROGRAM_PATTERN = compile(r'/api/v1/programs/([A-Fa-f0-9-]+)/')
    REGEX_PATCH_PROGRAM_PATTERN = compile(r'/api/v1/programs/([A-Fa-f0-9-]+)/')
    REGEX_DEL_PROGRAM_PATTERN = compile(r'/api/v1/programs/([A-Fa-f0-9-]+)/')
    REGEX_GET_PROGRAM_COURSES_PATTERN = compile(r'/api/v1/programs/([A-Fa-f0-9-]+)/courses/')
    REGEX_POST_PROGRAM_COURSES_PATTERN = compile(r'/api/v1/programs/([A-Fa-f0-9-]+)/courses/')
    REGEX_PATCH_PROGRAM_COURSES_PATTERN = compile(r'/api/v1/programs/([A-Fa-f0-9-]+)/courses/')
    REGEX_DEL_PROGRAM_COURSES_PATTERN = compile(r'/api/v1/programs/([A-Fa-f0-9-]+)/courses/')

    # View Settings (UploadFiles & Permissions)
    parser_classes = (JSONParser, FormParser, MultiPartParser, TypedFileUploadParser)
    authentication_classes = (CsrfExemptSessionAuthentication, BasicAuthentication)
    permission_classes = (permissions.IsAuthenticated,)

    @classmethod
    def get_sub_url(cls, full_url):
        return full_url.replace(r'/api/proxy/discovery', '')

    @classmethod
    def get_site_domain(cls, request):
        return request.site.configuration.get_value('site_domain', settings.SITE_NAME)
        # return configuration_helpers.get_value('site_domain', settings.SITE_NAME)

    @method_decorator(_expose_disapi_response(HttpServerError, HttpClientError))
    def get(self, request):
        """GET method for [discovery] api:
            - api/v1/programs/
            - api/v1/programs/xxxxxxx(program_uuid)/courses/
        """
        current_site_domain = self.get_site_domain(request)
        sub_url = self.get_sub_url(request.path_info)

        if '/api/v1/programs/' == sub_url:
            # http://0.0.0.0:18010/api/proxy/discovery/api/v1/programs/

            proxy_response = ProgramListLoader(
                request.user,
                current_site_domain
            ).execute()

            return JsonResponse(proxy_response)

        elif self.REGEX_GET_PROGRAM_COURSES_PATTERN.match(sub_url):
            matched_list = self.REGEX_PROGRAM_UUID_PATTERN.findall(sub_url)
            if 1 == len(matched_list):
                # http://0.0.0.0:18010/api/proxy/discovery/api/v1/programs/b6ca79cf0b5f408ea999e8c0589be5b0/courses/

                proxy_response = ProgramCoursesLoader(
                    request.user,
                    program_uuid=matched_list[0],
                    query_data=request.query_params,
                    current_site_domain=current_site_domain
                ).execute()

                for course in proxy_response:
                    for course_run in course['course_runs']:
                        course_descriptor = modulestore().get_course(CourseKey.from_string(course_run['key']))
                        if course_descriptor:
                            course_run['catalog_visibility'] = course_descriptor.catalog_visibility
                        else:
                            course_run['catalog_visibility'] = 'both'

                return JsonResponse(proxy_response)

        elif self.REGEX_GET_PROGRAM_PATTERN.match(sub_url):
            matched_list = self.REGEX_PROGRAM_UUID_PATTERN.findall(sub_url)
            if 1 == len(matched_list):
                # http://0.0.0.0:18010/api/proxy/discovery/api/v1/programs/b6ca79cf0b5f408ea999e8c0589be5b0/

                proxy_response = ProgramLoader(
                    request.user,
                    program_uuid=matched_list[0],
                    current_site_domain=current_site_domain
                ).execute()

                return JsonResponse(proxy_response)

        elif self.REGEX_GET_COURSES_PATTERN.match(sub_url):
            # http://0.0.0.0:18010/api/proxy/discovery/api/v1/courses/

            proxy_response = CoursesLoader(
                request.user,
                request.data,
                current_site_domain=current_site_domain
            ).execute()

            return JsonResponse(proxy_response)

        return JsonResponse(
            {
                'api_error_message': '[{}] invalid url path : {}'.format(current_site_domain, sub_url)
            },
            status=404
        )

    @method_decorator(_expose_disapi_response(HttpServerError, HttpClientError))
    def post(self, request, *args, **kwargs):
        """POST method for [discovery] api:
            - api/v1/programs/
            - api/v1/programs/xxxxxxx(program_uuid)/courses/
        """
        current_site_domain = self.get_site_domain(request)
        sub_url = self.get_sub_url(request.path_info)
        if '/api/v1/programs/' == sub_url:
            # http://0.0.0.0:18010/api/proxy/discovery/api/v1/programs/
            with ProgramCreator(
                request.user,
                request.data,
                request.FILES,
                current_site_domain=current_site_domain
            ) as creator:
                proxy_response = creator.execute()

                return JsonResponse(
                    proxy_response, status=201
                )

        elif self.REGEX_POST_PROGRAM_COURSES_PATTERN.match(sub_url):
            matched_list = self.REGEX_PROGRAM_UUID_PATTERN.findall(sub_url)
            if 1 == len(matched_list):
                # http://0.0.0.0:18010/api/proxy/discovery/api/v1/programs/b6ca79cf0b5f408ea999e8c0589be5b0/courses/

                proxy_response = ProgramCourseRegister(
                    request.user,
                    program_uuid=matched_list[0],
                    post_data=request.data,
                    current_site_domain=current_site_domain
                ).execute()

                return JsonResponse(
                    proxy_response, status=201
                )

        return JsonResponse(
            {
                'api_error_message': '[{}] invalid url path : {}'.format(current_site_domain, sub_url)
            },
            status=404
        )

    @method_decorator(_expose_disapi_response(HttpServerError, HttpClientError))
    def patch(self, request, *args, **kwargs):
        """PATCH method for [discovery] api:
            - api/v1/programs/xxxxxxx(program_uuid)/
            - api/v1/programs/xxxxxxx(program_uuid)/courses/
        """
        current_site_domain = self.get_site_domain(request)
        sub_url = self.get_sub_url(request.path_info)

        if self.REGEX_PATCH_PROGRAM_COURSES_PATTERN.match(sub_url):
            matched_list = self.REGEX_PROGRAM_UUID_PATTERN.findall(sub_url)
            if 1 == len(matched_list):
                # http://0.0.0.0:18010/api/proxy/discovery/api/v1/programs/b6ca79cf0b5f408ea999e8c0589be5b0/courses/

                proxy_response = ProgramCourseReorder(
                    request.user,
                    program_uuid=matched_list[0],
                    post_data=json_loads(request.body),
                    current_site_domain=current_site_domain
                ).execute()

                return JsonResponse(proxy_response)

        elif self.REGEX_PATCH_PROGRAM_PATTERN.match(sub_url):
            matched_list = self.REGEX_PROGRAM_UUID_PATTERN.findall(sub_url)
            if 1 == len(matched_list):
                # http://0.0.0.0:18010/api/proxy/discovery/api/v1/programs/b6ca79cf0b5f408ea999e8c0589be5b0/

                proxy_response = ProgramPartialUpdate(
                    request.user,
                    program_uuid=matched_list[0],
                    request_obj=request,
                    current_site_domain=current_site_domain
                ).execute()

                return JsonResponse(proxy_response)

        return JsonResponse(
            {
                'api_error_message': '[{}] invalid url path : {}'.format(current_site_domain, sub_url)
            },
            status=404
        )

    @method_decorator(_expose_disapi_response(HttpServerError, HttpClientError))
    def delete(self, request, *args, **kwargs):
        """DELETE method for [discovery] api:
            - api/v1/programs/xxxxxxx(program_uuid)/
            - api/v1/programs/xxxxxxx(program_uuid)/courses/
        """
        current_site_domain = self.get_site_domain(request)
        sub_url = self.get_sub_url(request.path_info)

        if self.REGEX_DEL_PROGRAM_COURSES_PATTERN.match(sub_url):
            matched_list = self.REGEX_PROGRAM_UUID_PATTERN.findall(sub_url)
            if 1 == len(matched_list):
                # http://0.0.0.0:18010/api/proxy/discovery/api/v1/programs/b6ca79cf0b5f408ea999e8c0589be5b0/courses/
                proxy_response = ProgramCourseEraser(
                    request.user,
                    program_uuid=matched_list[0],
                    params=request.data,
                    current_site_domain=current_site_domain
                ).execute()

                return JsonResponse(proxy_response)

        elif self.REGEX_DEL_PROGRAM_PATTERN.match(sub_url):
            matched_list = self.REGEX_PROGRAM_UUID_PATTERN.findall(sub_url)
            if 1 == len(matched_list):
                # http://0.0.0.0:18010/api/proxy/discovery/api/v1/programs/b6ca79cf0b5f408ea999e8c0589be5b0/

                proxy_response = ProgramEraser(
                    request.user,
                    program_uuid=matched_list[0],
                    current_site_domain=current_site_domain
                ).execute()

                return JsonResponse(proxy_response)

        return JsonResponse(
            {
                'api_error_message': '[{}] invalid url path : {}'.format(current_site_domain, sub_url)
            },
            status=404
        )
