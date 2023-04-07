# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import OrderedDict
import json
import logging

from branding.api import get_logo_url
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.http import int_to_base36
from django.utils.translation import gettext_lazy as _
from edx_rest_framework_extensions.paginators import DefaultPagination
from enrollment.views import EnrollmentUserThrottle
from instructor.enrollment import get_user_email_language
from instructor.views.api import students_bulk_enroll, _split_input_list
from instructor.views.tools import get_student_from_identifier
from triboo_analytics.models import IltSession
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework import viewsets, mixins
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from social_django.models import UserSocialAuth
from util.disable_rate_limit import can_disable_rate_limit
from util.json_request import JsonResponse
from xmodule.modulestore.django import modulestore

from lms.djangoapps.instructor.enrollment import send_mail_to_student
from lms.djangoapps.program_enrollments.persistance.programs import PartialProgram
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.content.course_structures.api.v0.api import course_structure
from openedx.core.djangoapps.programs.models import ProgramsApiConfig
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.core.lib.api.authentication import OAuth2AuthenticationAllowInactiveUser
from .permissions import IsStaffAndOrgMember
from .serializers import (
    BulkEnrollmentSerializer,
    CourseProgressSerializer,
    CourseSerializer,
    ILTLearnerReportSerializer,
    RetrieveListUserSerializer,
    UserProgressSerializer,
    UserSerializer,
    UserSSOSerializer,
    SSO_PROVIDER
)

logger = logging.getLogger('extended_api')

User = get_user_model()  # pylint:disable=invalid-name


class ByUsernameMixin:
    lookup_field = 'username'
    lookup_value_regex = "[^%&',;=?$\x22]+"


class ByEmailMixin:
    lookup_field = 'email'
    lookup_value_regex = "[^%&',;=?$\x22]+"


class UserFilterMixin:
    queryset_filter = {}
    filter_by_supervisor = False

    def get_queryset(self):
        """
        Restricts the returned users, by filtering by `user_id` query parameter.
        """
        queryset = self.serializer_class.Meta.model.objects.filter(profile__org=self.request.user.profile.org).exclude(
            profile__org=None).exclude(profile__org='')
        user_ids = [int(_id) for _id in self.request.query_params.get('user_id', '').split(',') if
                    _id.strip().isdigit()]
        usernames = [u.strip() for u in self.request.query_params.get('username', '').split(',') if u.strip()]
        emails = [u.strip() for u in self.request.query_params.get('email', '').split(',') if u.strip()]

        self.queryset_filter = {}
        if user_ids:
            self.queryset_filter = {'pk__in': user_ids}
            logger.info(u'Get user(s) with user_ids: {}'.format(user_ids))
        elif usernames:
            self.queryset_filter = {'username__in': usernames}
            logger.info(u'Get user(s) with usernames: {}'.format(usernames))
        elif emails:
            self.queryset_filter = {'email__in': emails}
            logger.info(u'Get user(s) with emails: {}'.format(emails))
        elif self.filter_by_supervisor:
            supervisors = [u.strip() for u in self.request.query_params.get('supervisor', '').split(',') if u.strip()]
            self.queryset_filter = supervisors and {'profile__lt_supervisor__in': supervisors} or {}
            logger.info(u'Get user(s) with supervisors: {}'.format(supervisors))
        return queryset.filter(**self.queryset_filter)


class ListUserThrottle(UserRateThrottle):
    """Limit the number of requests users can make to the API."""

    THROTTLE_RATES = {
        'user': '10/minute',
        'staff': '20/minute',
    }

    def allow_request(self, request, view):
        # Use a special scope for staff to allow for a separate throttle rate
        user = request.user
        if user.is_authenticated and (user.is_staff or user.is_superuser):
            self.scope = 'staff'
            self.rate = self.get_rate()
            self.num_requests, self.duration = self.parse_rate(self.rate)

        return super(ListUserThrottle, self).allow_request(request, view)


class ListCourseThrottle(UserRateThrottle):
    """Limit the number of requests users can make to the API."""
    # The course list endpoint is likely being inefficient with how it's querying
    # various parts of the code and can take courseware down, it needs to be rate
    # limited.

    THROTTLE_RATES = {
        'user': '5/minute',
        'staff': '10/minute',
    }

    def allow_request(self, request, view):
        # Use a special scope for staff to allow for a separate throttle rate
        user = request.user
        if user.is_authenticated and (user.is_staff or user.is_superuser):
            self.scope = 'staff'
            self.rate = self.get_rate()
            self.num_requests, self.duration = self.parse_rate(self.rate)

        return super(ListCourseThrottle, self).allow_request(request, view)


class UsersViewSet(UserFilterMixin, viewsets.ModelViewSet):
    authentication_classes = (OAuth2AuthenticationAllowInactiveUser,)
    permission_classes = (IsStaffAndOrgMember,)
    serializer_class = UserSerializer
    pagination_class = DefaultPagination
    pagination_class.max_page_size = 1000
    throttle_classes = ListUserThrottle,

    DEACTIVATE_STATUSES = {
        True: 'user_deactivated',
        False: 'user_already_inactive',
        None: 'user_not_found'
    }

    def check_status(self, request, default_status):
        resp = {'status': default_status}
        queryset = self.get_queryset()
        lookup_field = self.lookup_url_kwarg or self.lookup_field
        lookup_filter = {lookup_field: self.kwargs.get(lookup_field)}

        _status = status.HTTP_409_CONFLICT
        if lookup_filter[lookup_field] and not queryset.filter(**lookup_filter).exists():
            _status = status.HTTP_404_NOT_FOUND
            resp = {'detail': 'Not found.'}
        elif lookup_filter[lookup_field] and queryset.filter(is_active=False, **lookup_filter).exists():
            resp = {'detail': 'User inactive'}
        elif lookup_filter[lookup_field] and queryset.filter(is_superuser=True, **lookup_filter).exists():
            resp = {'detail': 'User is superuser'}
        elif queryset.filter(username=request.data.get('username')).exists():
            resp = {'detail': 'Username already used'}
        elif queryset.filter(email=request.data.get('email')).exists():
            resp = {'detail': 'Email already used'}
        else:
            # All check passed
            logger.info(u'Check for user: {}, {}'.format(lookup_filter, resp))
            return resp
        logger.warning(u'Check for user: {}, {}'.format(lookup_filter, resp))
        return Response(resp, status=_status)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        # Always set 'is_active' to True when creating a user
        data['is_active'] = True
        serializer = self.get_serializer(data=data)
        logger.info(u'Creating users with data: {}'.format(data))
        resp = self.check_status(request, 'user_created')
        if not isinstance(resp, dict):
            return resp

        serializer.is_valid(raise_exception=True)

        client_service_id = configuration_helpers.get_value('CLIENT_SERVICE_ID', None)
        if 'profile' in serializer.validated_data:
            serializer.validated_data['profile']['org'] = request.user.profile.org
            if client_service_id:
                serializer.validated_data['profile']['service_id'] = client_service_id
        elif client_service_id:
            serializer.validated_data['profile'] = {'org': request.user.profile.org, 'service_id': client_service_id}
        else:
            serializer.validated_data['profile'] = {'org': request.user.profile.org}
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        resp.update(serializer.data)
        logger.info(u'User created: {}'.format(serializer.data))
        user = User.objects.get(email=resp['email'])
        resp['password_reset_link'] = '{protocol}://{site}{link}'.format(
            protocol='https' if request.is_secure() else 'http',
            site=configuration_helpers.get_value('SITE_NAME', settings.SITE_NAME),
            link=reverse('password_reset_confirm', kwargs={
                'uidb36': int_to_base36(user.id),
                'token': default_token_generator.make_token(user),
            }),
        )
        return Response(resp, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        self.serializer_class.Meta.extra_kwargs = {"username": {"required": False}}
        partial = kwargs.pop('partial', False)

        instance = self.get_object()
        if request.data.get('is_active', False) and not instance.is_active and not instance.is_superuser:
            instance.is_active = True
            instance.save()

        resp = self.check_status(request, 'user_updated')
        if not isinstance(resp, dict):
            return resp

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        logger.info(u'Update user with data: {}'.format(request.data))
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        resp.update(serializer.data)
        return Response(resp)

    def retrieve(self, request, *args, **kwargs):
        logger.info(u'Retrieve user(s) with filter: {}'.format(kwargs))
        self.serializer_class = RetrieveListUserSerializer
        return super(UsersViewSet, self).retrieve(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        self.serializer_class = RetrieveListUserSerializer
        return super(UsersViewSet, self).list(request, *args, **kwargs)

    def perform_destroy(self, instance):
        logger.info(u'Deactivating user: {}'.format(instance))
        instance.is_active = False
        instance.save()

    def delete(self, request, *args, **kwargs):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        if lookup_url_kwarg not in kwargs:
            return self.bulk_destroy(request, *args, **kwargs)
        return self.destroy(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_superuser:
            return Response({'detail': 'User is superuser'}, status=status.HTTP_409_CONFLICT)
        preview_is_active = instance.is_active
        if not preview_is_active:
            return Response({'detail': 'User already inactive'}, status=status.HTTP_409_CONFLICT)

        resp = self.check_status(request, 'user_deactivated')
        if not isinstance(resp, dict):
            return resp

        self.perform_destroy(instance)
        resp = {
            'user_id': instance.id,
            'username': instance.username,
            'status': self.DEACTIVATE_STATUSES[preview_is_active]
        }
        logger.info(u'User deactivated: {}'.format(resp))
        return Response(resp, status=status.HTTP_200_OK)

    def bulk_destroy(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if self.queryset_filter:
            preview_statuses = dict(queryset.values_list('id', 'is_active'))
            users = self.queryset_filter.get('pk__in', self.queryset_filter.get('username__in', []))
            mapping_fields = ('id', 'username') if 'pk__in' in self.queryset_filter else ('username', 'id')
            mapping = dict(queryset.values_list(*mapping_fields))

            superusers = {}
            for user in queryset:
                if user.is_superuser:
                    superusers[user.id] = 'user_is_superuser'
            queryset.exclude(is_superuser=True).update(is_active=False)

            resp = []
            for u in users:
                user_id = mapping_fields[0] == 'id' and u or mapping.get(u)
                username = mapping_fields[0] == 'username' and u or mapping.get(u, '')
                resp.append({
                    'user_id': user_id,
                    'username': username,
                    'status': superusers.get(user_id, self.DEACTIVATE_STATUSES[preview_statuses.get(user_id)])
                })
            logger.info(u'Deactivated users: {}'.format(resp))
            return Response(resp, status=status.HTTP_200_OK)
        else:
            logger.warning(u'Cannot bulk deactivate all users')
            return Response({'detail': 'You cannot deactivate all users.'}, status=status.HTTP_400_BAD_REQUEST)


class UserSSOViewSet(UserFilterMixin, viewsets.ModelViewSet):
    authentication_classes = (OAuth2AuthenticationAllowInactiveUser,)
    permission_classes = (IsStaffAndOrgMember,)
    serializer_class = UserSSOSerializer
    pagination_class = DefaultPagination
    pagination_class.max_page_size = 1000
    throttle_classes = ListUserThrottle,

    def check_status(self, request, user=None):
        resp = {'status': 'OK'}
        queryset = self.get_queryset()
        lookup_field = self.lookup_url_kwarg or self.lookup_field
        lookup_filter = {lookup_field: self.kwargs.get(lookup_field)}
        logger.info(u'Check for user SSO: {}, {}'.format(lookup_filter, resp))

        _status = status.HTTP_409_CONFLICT
        if lookup_filter[lookup_field] and not queryset.filter(**lookup_filter).exists():
            _status = status.HTTP_404_NOT_FOUND
            resp = {'detail': 'Not found.'}
            return Response(resp, status=_status)
        if lookup_filter[lookup_field] and queryset.filter(is_active=False, **lookup_filter).exists():
            resp = {'detail': 'User inactive'}
            return Response(resp, status=_status)
        if lookup_filter[lookup_field] and queryset.filter(is_superuser=True, **lookup_filter).exists():
            resp = {'detail': 'User is superuser'}
            return Response(resp, status=_status)

        uid_list = dict(request.data).get('uid') or []
        # check if all UID are valid
        if not uid_list or not isinstance(uid_list, (list, tuple)) or not all([':' in i for i in uid_list]):
            resp = {'detail': 'Invalid UID'}
            return Response(resp, status=_status)
        # if all are valid:
        uid_list = [i.strip() for i in uid_list]
        if user:
            # check that all the UID are already set for this user (Unknown UID)
            for uid in uid_list:
                if not UserSocialAuth.objects.filter(user=user, provider=SSO_PROVIDER, uid=uid).exists():
                    resp = {'detail': 'Unknown UID'}
                    return Response(resp, status=_status)
        else:
            # check that none of the UID is already set (Conflicting)
            if UserSocialAuth.objects.filter(provider=SSO_PROVIDER, uid__in=uid_list).exists():
                resp = {'detail': 'Conflicting UID'}
                return Response(resp, status=_status)
        # All check passed
        return resp

    def post(self, request, *args, **kwargs):
        data = dict(request.data)
        user = self.get_object()
        logger.info(u'Adding user SSO with data: {}'.format(request.data))
        resp = self.check_status(request)
        if not isinstance(resp, dict):
            return resp

        uid_list = data.get('uid', [])
        set_sso(user, uid_list)

        return self.retrieve(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        data = dict(request.data)
        user = self.get_object()
        logger.info(u'Deleting user SSO with data: {}'.format(request.data))
        resp = self.check_status(request, user)
        if not isinstance(resp, dict):
            return resp

        uid_list = data.get('uid', [])
        unset_sso(user, uid_list)

        return self.retrieve(request, *args, **kwargs)


class UsersByUsernameViewSet(ByUsernameMixin, UsersViewSet):
    pass


class UserSSOByUsernameViewSet(ByUsernameMixin, UserSSOViewSet):
    pass


class UsersByEmailViewSet(ByEmailMixin, UsersViewSet):
    pass


class CoursesViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    authentication_classes = (OAuth2AuthenticationAllowInactiveUser,)
    permission_classes = (IsStaffAndOrgMember,)
    serializer_class = CourseSerializer
    pagination_class = DefaultPagination
    pagination_class.max_page_size = 1000
    throttle_classes = ListCourseThrottle,

    def get_queryset(self):
        course_org_filter = self.request.user.profile.org.split("+") or []
        logger.info(u'Get courses in org: {}'.format(self.request.user.profile.org))
        queryset = self.serializer_class.Meta.model.objects.filter(org__in=course_org_filter).exclude(
            org=None).exclude(org='')
        to_exclude = []
        for course in queryset:
            course_id = course.id
            if modulestore().get_course(course_id) is None:
                to_exclude.append(course_id)
        queryset = queryset.exclude(id__in=to_exclude)
        return queryset


class CourseOutlineViewSet(viewsets.GenericViewSet):
    authentication_classes = (OAuth2AuthenticationAllowInactiveUser,)
    permission_classes = (IsStaffAndOrgMember,)
    throttle_classes = ListCourseThrottle,

    def retrieve(self, request, pk=None):
        api_user = request.user
        COURSE_ID = pk

        try:
            course_key = CourseKey.from_string(COURSE_ID)
            overview = CourseOverview.objects.get(id=course_key)
        except (InvalidKeyError, CourseOverview.DoesNotExist):
            raise ValidationError({'detail': 'Not found'})

        api_course_org_filters = api_user.profile.org.split("+") or []
        if overview.org not in api_course_org_filters:
            raise ValidationError({'detail': 'Not found'})

        course_outline = OrderedDict()
        course_outline['course_id'] = COURSE_ID

        chapter_sections = {}
        course_chapters = []
        section_id_name = {}
        structure = course_structure(course_key)
        for block_id, block in structure['blocks'].iteritems():
            if block['type'] == 'course':
                course_outline['course_title'] = block['display_name']
                course_chapters = block['children']
            elif block['type'] == 'chapter':
                chapter_sections[block['id']] = [block['display_name'], block['children']]
            elif block['type'] == 'sequential':
                section_id_name[block['id']] = block['display_name']

        outline = []
        # for loop to preserve the order of the chapters
        for chapter_id in course_chapters:
            sections = []
            for section_id in chapter_sections[chapter_id][1]:
                sections.append(section_id_name[section_id])
            outline.append({chapter_sections[chapter_id][0]: sections})

        course_outline['outline'] = outline
        return Response(course_outline)


class CourseProgressViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    authentication_classes = (OAuth2AuthenticationAllowInactiveUser,)
    permission_classes = (IsStaffAndOrgMember,)
    serializer_class = CourseProgressSerializer
    throttle_classes = ListCourseThrottle,

    def get_queryset(self):
        course_org_filter = self.request.user.profile.org.split("+") or []
        logger.info(u'Get courses in org: {}'.format(self.request.user.profile.org))
        try:
            course_key = CourseKey.from_string(self.kwargs.get('pk'))
        except InvalidKeyError:
            raise ValidationError({'detail': 'Not found.'})

        self.kwargs = {'pk': course_key}
        queryset = self.serializer_class.Meta.model.objects.filter(org__in=course_org_filter).exclude(org=None).exclude(
            org='')

        return queryset


class ILTLearnerReportViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    authentication_classes = (OAuth2AuthenticationAllowInactiveUser,)
    permission_classes = (IsStaffAndOrgMember,)
    serializer_class = ILTLearnerReportSerializer
    pagination_class = DefaultPagination
    pagination_class.max_page_size = 1000
    throttle_classes = ListCourseThrottle,

    def get_queryset(self):
        org_filter = self.request.user.profile.org.split("+") or []
        sessions = IltSession.objects.filter(org__in=org_filter)
        module_ids = sessions.values_list('ilt_module_id', flat=True)
        queryset = self.serializer_class.Meta.model.objects.filter(ilt_module_id__in=module_ids)
        return queryset


class UserProgressViewSet(UserFilterMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    authentication_classes = (OAuth2AuthenticationAllowInactiveUser,)
    permission_classes = (IsStaffAndOrgMember,)
    serializer_class = UserProgressSerializer
    filter_by_supervisor = True
    throttle_classes = ListCourseThrottle,

    def get_queryset(self):
        logger.info(u'Get course progress of user: {}, org: {}'.format(self.kwargs, self.request.user.profile.org))
        queryset = self.serializer_class.Meta.model.objects.filter(
            profile__org=self.request.user.profile.org
        ).exclude(
            profile__org=None
        ).exclude(
            profile__org=''
        )
        return queryset


class UserProgressByUsernameViewSet(ByUsernameMixin, UserProgressViewSet):
    pass


class UserProgressByEmailViewSet(ByEmailMixin, UserProgressViewSet):
    pass


@can_disable_rate_limit
class BulkEnrollView(APIView):
    """
    **Use Case**

        Enroll multiple users in one or more courses.

    **Example Request**

        POST /api/extended/v1/bulk_enroll/ {
            "email_students": true,
            "action": "enroll",
            "courses": "course-v1:edX+Demo+123,course-v1:edX+Demo2+456",
            "identifiers": "brandon@example.com,yamilah@example.com"
        }

        **POST Parameters**

          A POST request can include the following parameters.

          * email_students: When set to `true`, students will be sent email
            notifications upon enrollment.
          * action: Can either be set to "enroll" or "unenroll". This determines the behabior

    **Response Values**

        If the supplied course data is valid and the enrollments were
        successful, an HTTP 200 "OK" response is returned.

        The HTTP 200 response body contains a list of response data for each
        enrollment. (See the `instructor.views.api.students_update_enrollment`
        docstring for the specifics of the response data available for each
        enrollment)
    """

    authentication_classes = (OAuth2AuthenticationAllowInactiveUser,)
    permission_classes = (IsStaffAndOrgMember,)
    throttle_classes = EnrollmentUserThrottle,

    def post(self, request):
        serializer = BulkEnrollmentSerializer(data=request.data)
        if serializer.is_valid():
            # Setting the content type to be form data makes Django Rest Framework v3.6.3 treat all passed JSON data as
            # POST parameters. This is necessary because this request is forwarded on to the student_update_enrollment
            # view, which requires all of the parameters to be passed in via POST parameters.
            metadata = request._request.META  # pylint: disable=protected-access
            metadata['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'

            email_students = serializer.data.get('email_students')
            action = serializer.data.get('action')
            response_dict = {
                'email_students': email_students,
                'action': action,
                'courses': {}
            }

            usernames_raw = serializer.data.get('usernames')
            usernames = _split_input_list(usernames_raw) if usernames_raw else []

            emails_raw = serializer.data.get('emails')
            emails = _split_input_list(emails_raw) if emails_raw else []

            user_ids_raw = serializer.data.get('user_ids')
            user_ids = _split_input_list(user_ids_raw) if user_ids_raw else []

            identifiers = []
            if not usernames and not emails and not user_ids:
                return JsonResponse(
                    {
                        'action': action,
                        'results': [{'error': True, 'message': 'A username or email or user_id must be provided'}],
                    }, status=400)
            else:
                [identifiers.append({'username': u}) for u in usernames]
                [identifiers.append({'email': e}) for e in emails]
                [identifiers.append({'user_id': i}) for i in user_ids]
            self.request.data['identifiers'] = identifiers

            course_names = []
            succeed_users = []
            courses = serializer.data.get('courses')
            for course in courses:
                response = students_bulk_enroll(self.request, course_id=course)
                response = json.loads(response.content)
                response_dict['courses'][course] = response

                if email_students:
                    course_id = CourseKey.from_string(course)
                    display_name = CourseOverview.objects.get(id=course_id).display_name
                    course_names.append(display_name)
                    [succeed_users.append(r['identifier']) for r in response['results'] if
                     'before' and 'after' in r.keys()]

            if email_students:
                # remove duplicate
                succeed_users = [i for n, i in enumerate(succeed_users) if i not in succeed_users[n + 1:]]
                for identifier in succeed_users:
                    send_email_to_learner(identifier, course_names, action)
            return Response(data=response_dict, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def send_email_to_learner(identifier, course_names, action):
    # First try to get a user object from the identifier
    user = None
    email = None
    language = None
    name = None

    try:
        if 'user_id' in identifier.keys():
            user = User.objects.get(id=identifier['user_id'])
        else:
            username_or_email = identifier.get('username') or identifier.get('email')
            user = get_student_from_identifier(username_or_email)
    except (ValueError, User.DoesNotExist):
        pass
    else:
        email = user.email
        language = get_user_email_language(user)
        name = user.profile.name or user.username

    if user:
        stripped_site_name = configuration_helpers.get_value('SITE_NAME', settings.SITE_NAME)
        path = ''
        if not ProgramsApiConfig.is_student_dashboard_enabled() or not PartialProgram.count_published_only():
            path = reverse('my_courses', kwargs={'tab': 'all-courses'})
        else:
            path = reverse('my_training_overview')
        url = u'{proto}://{site}{path}'.format(
            proto="https",
            site=stripped_site_name,
            path=path
        )
        logo_url = get_logo_url()

        params = {"name": name, "course_names": course_names, "logo_url": logo_url, "url": url, "site_name": None}
        if action == 'enroll':
            params['message'] = 'bulk_enroll'
        else:
            params['message'] = 'bulk_unenroll'

        send_mail_to_student(email, params, language=language)


def set_sso(user, uid_list):
    for uid in uid_list:
        UserSocialAuth(user=user, provider=SSO_PROVIDER, uid=uid, extra_data={}).save()
    logger.info(u'SSO added for user: {}, {}'.format(user, uid_list))


def unset_sso(user, uid_list):
    UserSocialAuth.objects.filter(user=user, provider=SSO_PROVIDER, uid__in=uid_list).delete()
    logger.info(u'SSO deleted for user: {}, {}'.format(user, uid_list))
