# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db.models import IntegerField, Case, Value, When, Q
from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, pgettext
from django.views.generic import ListView
from edxmako.shortcuts import render_to_response
from lms.djangoapps.courseware.courses import get_courses
from lms.djangoapps.program_enrollments.persistance.programs import PartialProgram
from oauth2_provider.models import get_application_model
from openedx.core.djangoapps.api_admin.models import ApiAccessConfig, ApiAccessRequest
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.core.djangoapps.programs.models import ProgramsApiConfig
from student.roles import STUDIO_ADMIN_ACCESS_GROUP, LT_DEVELOPER, LT_TESTER, LT_SERVICE
from django.urls import reverse
from util.views import require_global_staff


Application = get_application_model()


class AdminPanel(ListView):
    model = User
    paginate_by = 100
    template_name = "admin_panel/admin_panel.html"
    template_engine = "mako"
    context_object_name = "user_list"
    order_types = {
        'u': 'username', '-u': '-username', 'e': 'email', '-e': '-email',
        'f': 'first_name', '-f': '-first_name', 'l': 'last_name', '-l': '-last_name',
        's': 'is_active', '-s': '-is_active', 'a': 'level', '-a': '-level'
    }
    current_order = 'u'

    def get(self, request, *args, **kwargs):
        response = super(AdminPanel, self).get(request, *args, **kwargs)
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"  # HTTP 1.1.
        response["Pragma"] = "no-cache"  # HTTP 1.0.
        response["Expires"] = "0"  # Proxies.
        return response

    def get_context_data(self, **kwargs):
        context = super(AdminPanel, self).get_context_data(**kwargs)
        context['route'] = "user_list"
        context['search_string'] = self.request.GET.get('name', '')
        context['current_order'] = self.current_order
        context['list_table_downloads_url'] = reverse('list_table_downloads', kwargs={'report': 'users'})
        return context

    def get_queryset(self):
        orgs = configuration_helpers.get_current_site_orgs()
        orgs = "+".join(orgs)
        user_filter = Q(profile__org=orgs) | Q(profile__org=None)
        if self.request.user.profile.org in [LT_DEVELOPER, LT_TESTER]:
            user_filter = user_filter | Q(profile__org=LT_TESTER)
        object_list = self.model.objects.filter(user_filter).prefetch_related("groups")
        name = self.request.GET.get('name', '')
        if name:
            object_list = object_list.filter(
                Q(username__icontains=name) |
                Q(email__icontains=name) |
                Q(first_name__icontains=name) |
                Q(last_name__icontains=name)
            )
        object_list = object_list.exclude(email__icontains="example.com")
        order = self.request.GET.get('order', 'u')
        if order not in self.order_types:
            order = 'u'
        self.current_order = order
        if order in ['a', '-a']:
            platform_admins = object_list.filter(Q(is_staff=True) | Q(is_superuser=True)).annotate(level=Case(
                When(is_superuser=True, then=Value(3)),
                default=Value(2),
                output_field=IntegerField()
            ))
            studio_admins = object_list.exclude(Q(is_staff=True) | Q(is_superuser=True)).filter(
                groups__name=STUDIO_ADMIN_ACCESS_GROUP
            ).annotate(level=Value(1, output_field=IntegerField()))
            learners = object_list.exclude(
                Q(is_staff=True) | Q(is_superuser=True) | Q(groups__name=STUDIO_ADMIN_ACCESS_GROUP)
            ).annotate(level=Value(0, output_field=IntegerField()))

            object_list = learners.union(studio_admins, platform_admins)
        ordering = self.order_types.get(order, 'username')
        if ordering != 'username':
            ordering = [ordering, 'username']
        else:
            ordering = ['username']
        object_list = object_list.order_by(*ordering)

        return object_list

    @method_decorator(staff_member_required(login_url='/login'))
    def dispatch(self, request, *args, **kwargs):
        return super(AdminPanel, self).dispatch(request, *args, **kwargs)


def get_date_format():
    date_format = _("NUMBERIC_SHORT_DATE_SLASH")
    if date_format == "NUMBERIC_SHORT_DATE_SLASH":
        date_format = "%Y/%m/%d"
    js_date_format = date_format.replace("%Y", 'yy').replace("%m", "mm").replace("%d", "dd")
    return date_format, js_date_format


@staff_member_required(login_url='/login')
def create_user(request):
    profile_fields = configuration_helpers.get_value(
        'ANALYTICS_USER_PROPERTIES',
        settings.FEATURES.get('ANALYTICS_USER_PROPERTIES', {})
    )

    program_feature_enabled = ProgramsApiConfig.is_student_dashboard_enabled()
    platform_level_options = [
        {'text': pgettext('admin panel', 'Learner'), 'value': '0'},
        {'text': _('Studio Admin') if not program_feature_enabled else _('Studio Admin - Courses'), 'value': '1'},
        {'text': _('Platform Admin'), 'value': '2'}
    ]

    if program_feature_enabled:
        platform_level_options.insert(
            2, {'text': _('Studio Super Admin - Courses and Learning Paths'), 'value': '4'}
        )
    if request.user.is_superuser:
        platform_level_options.append({'text': _('Platform Super Admin'), 'value': '3'})

    context = {
        'route': 'user_create',
        'user_id': "",
        'profile_fields': profile_fields,
        'date_format': get_date_format()[1],
        'platform_level_options': platform_level_options,
        'program_feature_enabled': program_feature_enabled
    }

    return render_to_response("admin_panel/admin_panel.html", context)


@require_global_staff
def edit_user(request, user_id):
    user = User.objects.get(id=user_id)
    if user.is_superuser and not request.user.is_superuser:
        raise PermissionDenied

    _orgs = configuration_helpers.get_current_site_orgs()
    _orgs = ['+'.join(_orgs)] if _orgs else []
    if request.user.profile and request.user.profile.org in (LT_DEVELOPER, LT_TESTER):
        _orgs.append(LT_TESTER)
    _orgs.append(None)
    if user.profile and user.profile.org not in _orgs:
        raise Http404

    profile_fields = configuration_helpers.get_value(
        'ANALYTICS_USER_PROPERTIES',
        settings.FEATURES.get('ANALYTICS_USER_PROPERTIES', {})
    )

    program_feature_enabled = ProgramsApiConfig.is_student_dashboard_enabled()
    platform_level_options = [
        {'text': pgettext('admin panel', 'Learner'), 'value': '0'},
        {'text': _('Studio Admin') if not program_feature_enabled else _('Studio Admin - Courses'), 'value': '1'},
        {'text': _('Platform Admin'), 'value': '2'}
    ]

    if program_feature_enabled:
        platform_level_options.insert(
            2, {'text': _('Studio Super Admin - Courses and Learning Paths'), 'value': '4'}
        )
    if request.user.is_superuser:
        platform_level_options.append({'text': _('Platform Super Admin'), 'value': '3'})

    context = {
        'route': 'user_edit',
        'user_id': user_id,
        'profile_fields': profile_fields,
        'date_format': get_date_format()[1],
        'platform_level_options': platform_level_options,
        'program_feature_enabled': program_feature_enabled,
        'user_joined_date': user.date_joined.strftime("%Y-%m-%d %H:%M:%S %Z") if user.date_joined else '—',
        'user_last_login': user.last_login.strftime("%Y-%m-%d %H:%M:%S %Z") if user.last_login else '—'
    }

    return render_to_response("admin_panel/admin_panel.html", context)


@staff_member_required(login_url='/login')
def csv_registration(request):
    context = {
        'route': 'csv_registration',
        'reverse_urls': {
            'precheck_upload_student_csv_button_url': reverse('admin_panel_batch_register_students_precheck'),
            'upload_student_csv_button_url': reverse('admin_panel_batch_register_students'),
            'update_student_csv_button_url': reverse('admin_panel_batch_update_students'),
            'send_welcoming_email_url': reverse('admin_panel_batch_send_welcoming_email'),
        }
    }

    return render_to_response("admin_panel/admin_panel.html", context)


@staff_member_required(login_url='/login')
def batch_enrollment(request):
    programs = [program.to_dict() for program in
                PartialProgram.query(loading_policy=PartialProgram.POLICY_LOAD_LP_ONLY)]
    
    context = {
        'route': 'batch_enrollment',
        'courses': [["%s" % overview.id, overview.display_name_with_default] for overview in get_courses(request.user)],
        'programs': [[p['uuid'], p['title']] for p in programs],
        'reverse_urls': {
            'course_enroll_button_url': reverse('admin_panel_batch_enroll_in_course'),
            'program_enroll_button_url': reverse('admin_panel_batch_enroll_in_program'),
        }
    }

    return render_to_response("admin_panel/admin_panel.html", context)


def admin_api_credentials():
    """
    :return: API Credentials of api_user
    """
    if ApiAccessConfig.current().enabled:
        api_user = User.objects.filter(username="api_user")
        if api_user.exists():
            try:
                api_request = ApiAccessRequest.objects.get(user=api_user)
                application = Application.objects.filter(user=api_user)
                if api_request.status == ApiAccessRequest.APPROVED and application.exists():
                    application = application.first()
                    client_id = application.client_id
                    client_secret = application.client_secret
                    return client_id, client_secret
            except ApiAccessRequest.DoesNotExist:
                pass
    return None


@staff_member_required(login_url='/login')
def platform_configuration(request):
    credentials = admin_api_credentials()
    if credentials:
        client_id = credentials[0]
        client_secret = credentials[1]
        context = {"route": "platform_configuration", "client_id": client_id, "client_secret": client_secret}
        return render_to_response("admin_panel/admin_panel.html", context)
    else:
        raise Http404
