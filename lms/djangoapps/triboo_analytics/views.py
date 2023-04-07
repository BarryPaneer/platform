# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from functools import wraps
import hashlib
import json
import logging
import operator
import collections
from six import text_type
from pytz import utc
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.urlresolvers import reverse
from django.db import transaction
from django.db.models import Max, Q, Subquery
from django.http import HttpResponseNotFound, Http404
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import pgettext_lazy
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from django_countries import countries
from django_tables2 import RequestConfig
from django_tables2.export import TableExport
from edxmako.shortcuts import render_to_response
from opaque_keys import InvalidKeyError
from opaque_keys.edx.django.models import CourseKeyField
from opaque_keys.edx.keys import CourseKey, UsageKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.content.course_structures.api.v0 import api
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.core.djangoapps.user_api.accounts.image_helpers import get_profile_image_urls_for_user
from courseware.courses import get_course_by_id
from courseware.module_render import toc_for_course
from lms.djangoapps.external_catalog.utils import (
is_edflex_enabled,
is_crehana_enabled,
is_anderspink_enabled,
is_founderz_enabled,
is_siemens_enabled
    )
from lms.djangoapps.grades.constants import ScoreDatabaseTableEnum
from lms.djangoapps.grades.course_data import CourseData
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from lms.djangoapps.grades.events import SUBSECTION_GRADE_CALCULATED, subsection_grade_calculated
from lms.djangoapps.grades.models import (
    PersistentSubsectionGrade,
    PersistentSubsectionGradeOverride,
    PersistentSubsectionGradeOverrideHistory,
)
from lms.djangoapps.grades.signals.signals import GRADE_EDITED
from lms.djangoapps.grades.subsection_grade import CreateSubsectionGrade
from lms.djangoapps.grades.tasks import recalculate_subsection_grade_v3
from lms.djangoapps.instructor.enrollment import get_user_email_language, send_mail_to_student
from lms.djangoapps.instructor.views.api import require_level
from lms.djangoapps.instructor_task.api_helper import submit_task, AlreadyRunningError
from lms.djangoapps.instructor_task.models import ReportStore
from student.models import CourseEnrollment, WaiverRequest, PendingRequestExitsError, RequestAlreadyApprovedError
from student.roles import CourseInstructorRole, CourseStaffRole, LEARNING_PATH_ADMIN_ACCESS_GROUP, \
    STUDIO_ADMIN_ACCESS_GROUP, LT_DEVELOPER, LT_TESTER
from student.triboo_groups import (
    CATALOG_DENIED_GROUP,
    EDFLEX_DENIED_GROUP,
    CREHANA_DENIED_GROUP,
    ANDERSPINK_DENIED_GROUP,
    LEARNLIGHT_DENIED_GROUP,
    LINKEDIN_DENIED_GROUP,
    UDEMY_DENIED_GROUP,
    FOUNDERZ_DENIED_GROUP,
    SIEMENS_DENIED_GROUP
)
from track.event_transaction_utils import (
    create_new_event_transaction_id,
    get_event_transaction_id,
    get_event_transaction_type,
    set_event_transaction_type
)
from util.json_request import JsonResponse, JsonResponseBadRequest
from util.date_utils import to_timestamp, strftime_localized
from xmodule.modulestore.django import modulestore
from .forms import (
    UserPropertiesHelper,
    TableFilterForm,
    UserPropertiesForm,
    AVAILABLE_CHOICES,
)
from .models import (
    ANALYTICS_ACCESS_GROUP,
    ANALYTICS_LIMITED_ACCESS_GROUP,
    get_combined_org,
    Badge,
    CountryDailyReport,
    CourseDailyReport,
    IltLearnerReport,
    IltModule,
    IltSession,
    LearnerBadgeJsonReport,
    LearnerCourseJsonReport,
    LearnerDailyReport,
    LearnerSectionJsonReport,
    LearnerVisitsDailyReport,
    MicrositeDailyReport,
    ReportLog,
    TrackingLogHelper,
    LeaderBoard,
    LeaderBoardView
)
from .tables import (
    get_progress_table_class,
    get_time_spent_table_class,
    TranscriptTable,
    TranscriptTableWithGradeLink,
    LearnerDailyTable,
    CourseTable,
    IltTable,
    IltLearnerTable,
    CustomizedCourseTable,
    UserBaseTable,
    UserTable
)
from .tasks import generate_export_table as generate_export_table_task, links_for_all, \
    send_waiver_request_email, generate_leaderboard_report_task, generate_users_list_report_task, links_for_users, \
    links_for_leaderboard

DEFAULT_LEADERBOARD_TOP = 10
LEADERBOARD_DASHBOARD_TOP = 5

logger = logging.getLogger('triboo_analytics')


def analytics_on(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not configuration_helpers.get_value('ENABLE_ANALYTICS', settings.FEATURES.get('ENABLE_ANALYTICS', False)):
            raise Http404
        else:
            return func(request, *args, **kwargs)
    return wrapper


def analytics_member_required(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        user_groups = [group.name for group in request.user.groups.all()]
        if (request.user.is_staff or ANALYTICS_ACCESS_GROUP in user_groups or ANALYTICS_LIMITED_ACCESS_GROUP in user_groups):
            return func(request, *args, **kwargs)
        raise PermissionDenied
    return wrapper


def analytics_full_member_required(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_staff or ANALYTICS_ACCESS_GROUP in [group.name for group in request.user.groups.all()]:
            return func(request, *args, **kwargs)
        raise PermissionDenied
    return wrapper


def day2str(day):
    return day.strftime("%Y-%m-%d") if day else ''


def dt2str(daytime):
    return daytime.strftime("%Y-%m-%d %H:%M:%S %Z") if daytime else ''


def config_tables(request, *tables):
    config = RequestConfig(request, paginate={'per_page': 20})
    for t in tables:
        config.configure(t)


@analytics_on
@analytics_member_required
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def list_table_downloads(_request, report='', course_id=None):
    report_store = ReportStore.from_config(config_name='TRIBOO_ANALYTICS_REPORTS')
    if report == "leaderboard":
        links = links_for_leaderboard(report_store.storage, _request.user)
    elif report == 'users':
        links = links_for_users(report_store.storage, _request.user)
    else:
        links = links_for_all(report_store.storage, _request.user)

    response_payload = {'download': links}
    return JsonResponse(response_payload)


class UnsupportedExportFormatError(Exception):
    pass


def new_request_copy(request_copy):
    if request_copy.has_key('clear') or request_copy.has_key('delete'):
        for k in request_copy.keys():
            if 'queried_field' in k or 'query_string' in k:
                del request_copy[k]
    return request_copy


def get_kwargs(data):
    kwargs = {}

    if 'query_tuples' in data.keys():
        for queried_string, field in data.get('query_tuples'):
            if queried_string:
                prop = field.split('_', 1)[1]
                db_prefix = "user__"
                if prop not in ['email', 'username', 'date_joined', 'first_name', 'last_name']:
                    db_prefix += "profile__"
                queried_field = db_prefix + prop

                if queried_field == "user__profile__country":
                    queried_country = queried_string.lower()
                    country_code_by_name = {name.lower(): code for code, name in list(countries)}
                    country_codes = []
                    for country_name in country_code_by_name.keys():
                        if queried_country in country_name:
                            country_codes.append(country_code_by_name[country_name])
                    if country_codes:
                        kwargs['user__profile__country__in'] = country_codes
                    else:
                        kwargs['invalid'] = True
                elif queried_field == "user__profile__lt_gdpr":
                    queried_str = queried_string.lower()
                    if queried_str == "true":
                        kwargs[queried_field] = True
                    elif queried_str == "false":
                        kwargs[queried_field] = False
                    else:
                        kwargs['invalid'] = True
                else:
                    kwargs[queried_field + '__icontains'] = queried_string

    all_properties = ["user_%s" % prop for prop in AVAILABLE_CHOICES.keys()]
    config_properties = configuration_helpers.get_value('ANALYTICS_USER_PROPERTIES',
                                                        settings.FEATURES.get('ANALYTICS_USER_PROPERTIES', {}))
    selected_properties = data.get('selected_properties')
    if selected_properties:
        selected_properties += ['user_name']
    else:
        selected_properties = ['user_name']
        for prop in AVAILABLE_CHOICES.keys():
            if prop in config_properties.keys() and config_properties[prop] == "default":
                selected_properties.append("user_%s" % prop)
    exclude = set(all_properties) - set(selected_properties)

    return kwargs, exclude


def get_period_kwargs(data, course_id=None, as_string=False):
    kwargs, exclude = get_kwargs(data)

    if course_id:
        kwargs['course_id'] = "%s" % course_id if as_string else course_id

    from_day = data.get('from_day')
    to_day = data.get('to_day')
    logger.info("ANALYTICS -- requesting period %s - %s" % (from_day, to_day))
    from_date = utc.localize(datetime.strptime(from_day, '%Y-%m-%d')) if from_day else None
    to_date = utc.localize(datetime.strptime(to_day, '%Y-%m-%d')) + timedelta(days=1) if to_day else None
    if to_day:
        period_end_reportlog = ReportLog.get_latest(from_date=from_date, to_date=to_date)
        if period_end_reportlog:
            period_end = period_end_reportlog.created
            kwargs['to_date'] = day2str(period_end) if as_string else period_end.date()
            logger.info("ANALYTICS -- searching for last analytics success in [%s - %s] => %s" % (
                from_date, to_date, kwargs['to_date']))
    if from_day:
        period_start_reportlog = ReportLog.get_latest(to_date=from_date)
        if period_start_reportlog:
            period_start = period_start_reportlog.created
            kwargs['from_date'] = day2str(period_start) if as_string else period_start.date()
            logger.info("ANALYTICS -- searching for last analytics success in [… - %s] => %s" % (
                from_date, kwargs['from_date']))

    return kwargs, exclude


def get_ilt_period_kwargs(data, orgs, as_string=False):
    kwargs, exclude = get_kwargs(data)

    kwargs['org__in'] = orgs

    from_day = data.get('from_day')
    to_day = data.get('to_day')
    if from_day and to_day:
        kwargs['ilt_period_range'] = json.dumps((from_day, to_day))

    courses_ids = data.get('selected_courses', None)
    if courses_ids:
        # POST parameter from ILT Report Page
        kwargs['courses_ids'] = courses_ids.split(',')
    else:
        courses_selected = data.get('courses_selected', None)
        if courses_selected:
            # POST parameter from Customized Report Page
            kwargs['courses_ids'] = courses_selected.split(',')

    return kwargs, exclude


def get_transcript_table(orgs, user_id, last_update, request=None, html_links=False, sort=None, with_gradebook_link=False):
    queryset = LearnerCourseJsonReport.objects.none()
    for org in orgs:
        new_queryset = LearnerCourseJsonReport.filter_by_day(org=org, user_id=user_id)
        queryset = queryset | new_queryset
    order_by = get_order_by(TranscriptTable, sort)
    if with_gradebook_link:
        return TranscriptTableWithGradeLink(queryset, html_links=html_links, order_by=order_by, request=request), queryset
    return TranscriptTable(queryset, html_links=html_links, order_by=order_by), queryset


def get_course_sections(course_key):
    chapters = []
    sections = {}
    course_structure = api.course_structure(course_key)

    for block in course_structure['blocks'].keys():
        if course_structure['blocks'][block]['type'] == "chapter":
            chapter_url = TrackingLogHelper.get_chapter_url(course_structure['blocks'][block]['id'])
            chapter_name = course_structure['blocks'][block]['display_name']
            sections[chapter_url] = {'name': chapter_name, 'sections': []}
            for child in course_structure['blocks'][block]['children']:
                section_url = TrackingLogHelper.get_section_url(child)
                section_key = "%s/%s" % (chapter_url, section_url)
                sections[chapter_url]['sections'].append((section_key, chapter_name))
        else:
            if course_structure['blocks'][block]['type'] == "course":
                for child in course_structure['blocks'][block]['children']:
                    chapters.append(TrackingLogHelper.get_chapter_url(child))
    ordered_chapters = []
    ordered_sections = []
    for chapter in chapters:
        chapter_name = sections[chapter]['name']
        nb_sections_in_chapter = len(sections[chapter]['sections'])
        ordered_chapters.append({'key': chapter, 'name': chapter_name, 'colspan': nb_sections_in_chapter})
        ordered_sections += sections[chapter]['sections']
    return ordered_chapters, ordered_sections


def get_customized_table(report_cls, filter_kwargs, table_cls, exclude):
    if filter_kwargs.pop('invalid', False):
        return table_cls([]), 0

    querysets = report_cls.filter_by_period(**filter_kwargs)
    row_count = len(querysets)
    table = table_cls(querysets, exclude=exclude)
    return table, row_count


def get_order_by(table_cls, sort):
    if sort:
        order = "-" if sort[:1] == "-" else ""
        order_by = sort[1:].encode('utf-8')
        return "%s%s" % (order, table_cls.get_field_from_verbose(order_by))
    return None


def get_table_data(report_cls, table_cls, filter_kwargs, exclude, by_period=False, html_links=False,
                   sort=None):
    if filter_kwargs.pop('invalid', False):
        return []

    dataset = report_cls.objects.none()
    if by_period:
        dataset = report_cls.filter_by_period(**filter_kwargs)
    else:
        dataset = report_cls.filter_by_day(**filter_kwargs)

    order_by = get_order_by(table_cls, sort)
    if html_links:
        return table_cls(dataset, exclude=exclude, html_links=True, order_by=order_by)
    return table_cls(dataset, exclude=exclude, order_by=order_by)


def get_progress_table_data(course_key, filter_kwargs, exclude, sort=None):
    if filter_kwargs.pop('invalid', False):
        return []

    course_filter = filter_kwargs.pop('course_id')
    filter_kwargs['badge__course_id'] = course_filter
    dataset = LearnerBadgeJsonReport.filter_by_period(**filter_kwargs)

    _badges = Badge.objects.filter(course_id=course_key).order_by('order')
    badges = [(b.badge_hash, b.grading_rule, b.section_name) for b in _badges]
    ProgressTable = get_progress_table_class(badges)
    columns = []
    for b in _badges:
        badge_name = "%s ▸ %s" % (b.grading_rule, b.section_name)
        columns.append("%s / %s" % (badge_name, _('Success')))
        columns.append("%s / %s" % (badge_name, _('Score')))
        columns.append("%s / %s" % (badge_name, _('Date')))
    order_by = get_order_by(ProgressTable, sort)
    return ProgressTable(dataset, exclude=exclude, order_by=order_by), columns


def get_time_spent_table_data(course_key, filter_kwargs, exclude, sort=None):
    if filter_kwargs.pop('invalid', False):
        return []

    dataset, sections = LearnerSectionJsonReport.filter_by_period(**filter_kwargs)

    ordered_chapters, ordered_sections = get_course_sections(course_key)
    table_sections = []
    columns = []
    for section_key, chapter_name in ordered_sections:
        if section_key in sections.keys():
            section_name = sections[section_key]
            columns.append(section_name)
            table_sections.append({'key': section_key,
                                   'name': section_name,
                                   'chapter': chapter_name})

    TimeSpentTable = get_time_spent_table_class(ordered_chapters, table_sections)
    order_by = get_order_by(TimeSpentTable, sort)
    return TimeSpentTable(dataset, exclude=exclude, order_by=order_by), columns


def get_ilt_global_table_data(filter_kwargs, sort=None):
    if filter_kwargs.pop('invalid', False):
        return []

    if filter_kwargs.get('ilt_period_range', False):
        from_day, to_day = json.loads(filter_kwargs.pop('ilt_period_range', None))
        if from_day and to_day:
            from_date = utc.localize(datetime.strptime(from_day, '%Y-%m-%d'))
            to_date = utc.localize(datetime.strptime(to_day, '%Y-%m-%d')) + timedelta(days=1)
            period_filter = (from_date, to_date)
            filter_kwargs['start__range'] = period_filter

    courses_ids = filter_kwargs.pop('courses_ids', None)
    if courses_ids:
        reports = IltSession.objects.filter(
            ilt_module__in=Subquery(
                IltModule.objects.filter(
                    course_id__in=[CourseKey.from_string(course_id) for course_id in courses_ids]
                ).values('id')
            ),
            **filter_kwargs
        )
    else:
        reports = IltSession.objects.filter(**filter_kwargs)
    order_by = get_order_by(IltTable, sort)
    return IltTable(reports, order_by=order_by)


def get_ilt_learner_table_data(filter_kwargs, exclude, sort=None):
    if filter_kwargs.pop('invalid', False):
        return []

    org_filter = filter_kwargs.pop('org__in')
    courses_ids = filter_kwargs.pop('courses_ids', None)
    if courses_ids:
        sessions = IltSession.objects.filter(
            org__in=org_filter,
            ilt_module__in=Subquery(
                IltModule.objects.filter(
                    course_id__in=[CourseKey.from_string(course_id) for course_id in courses_ids]
                ).values('id')
            )
        )
    else:
        sessions = IltSession.objects.filter(org__in=org_filter)
    module_ids = sessions.values_list('ilt_module_id', flat=True)

    if filter_kwargs.get('ilt_period_range', None):
        from_day, to_day = json.loads(filter_kwargs.pop('ilt_period_range', None))
        if from_day and to_day:
            from_date = utc.localize(datetime.strptime(from_day, '%Y-%m-%d'))
            to_date = utc.localize(datetime.strptime(to_day, '%Y-%m-%d')) + timedelta(days=1)
            period_filter = (from_date, to_date)
            filter_kwargs['ilt_session__start__range'] = period_filter

    reports = IltLearnerReport.objects.filter(ilt_module_id__in=module_ids, **filter_kwargs).prefetch_related('user__profile')
    order_by = get_order_by(IltLearnerTable, sort)
    return IltLearnerTable(reports, exclude=exclude, order_by=order_by)


def users_list_export_table(orgs):
    reports = User.objects.filter(profile__org=orgs).order_by('profile__name')
    for user in reports:
        user_groups = [group.name for group in user.groups.all()]

        user.analytics_access = "None"
        if ANALYTICS_ACCESS_GROUP in user_groups:
            user.analytics_access = "Full Access"
        if ANALYTICS_LIMITED_ACCESS_GROUP in user_groups:
            user.analytics_access = "Restricted"

        user.platform_level = "Learner"
        if user.is_superuser:
            user.platform_level = "Platform Super Admin"
            user.analytics_access = "Full Access"
        elif user.is_staff:
            user.platform_level = "Platform Admin"
            user.analytics_access = "Full Access"
        else:
            if LEARNING_PATH_ADMIN_ACCESS_GROUP in user_groups and STUDIO_ADMIN_ACCESS_GROUP in user_groups:
                user.platform_level = "Studio Super Admin"
            elif STUDIO_ADMIN_ACCESS_GROUP in user_groups:
                user.platform_level = "Studio Admin"

        user.internal_catalog_access = False if CATALOG_DENIED_GROUP in user_groups else True
        user.edflex_access = False if EDFLEX_DENIED_GROUP in user_groups else True
        user.crehana_access = False if CREHANA_DENIED_GROUP in user_groups else True
        user.anderspink_access = False if ANDERSPINK_DENIED_GROUP in user_groups else True
        user.learnlight_access = False if LEARNLIGHT_DENIED_GROUP in user_groups else True
        user.linkedin_access = False if LINKEDIN_DENIED_GROUP in user_groups else True
        user.udemy_access = False if UDEMY_DENIED_GROUP in user_groups else True
        user.founderz_access = False if FOUNDERZ_DENIED_GROUP in user_groups else True
        user.siemens_access = False if SIEMENS_DENIED_GROUP in user_groups else True

    return UserTable(data=reports)


def json_response(table, page={'no': 1, 'size': 20}, summary_columns=[], column_order=[]):
    if isinstance(table, list) and len(table) == 0:
        return JsonResponse({'list': [],
                             'total': 0,
                             'pagination': {'rowsCount': 0}})
    try:
        rowsCount = len(table.data)
        logger.info("ANALYTICS -- rowsCount=%d" % rowsCount)
        if not rowsCount:
            return JsonResponse({'list': [],
                                 'total': 0,
                                 'pagination': {'rowsCount': 0}})
        total = {}
        for column in table.columns:
            if column.footer or column.footer == 0:
                total[column.verbose_name] = column.footer

        table.paginate(page=page['no'], per_page=page['size'])

        table_response = []
        for row in table.page.object_list:
            new_row = {}
            for column in table.columns:
                if column.name.startswith("user_") and column.name not in ("user_name", "user_last_login"):
                    new_row[column.name] = row.get_cell_value(column.name)
                else:
                    new_row[column.verbose_name] = row.get_cell_value(column.name)
            # logger.info("ANALYTICS -- %s" % new_row)
            table_response.append(new_row)

        response = {'list': table_response,
                    'total': total,
                    'pagination': {'rowsCount': rowsCount}}
        if column_order:
            response['columns'] = column_order
        logger.info("ANALYTICS -- %s" %  response)
        return JsonResponse(response)
    except Exception as e:
        logger.exception(e)
        return JsonResponseBadRequest({"message": "Unable to fetch data."})


def _transcript_view(user, request, template, report_type, with_gradebook_link=False):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return HttpResponseNotFound()

    if len(orgs) == 1:
        org = orgs[0]
    else:
        org = get_combined_org(orgs)

    courses = []
    course_contents = {}
    last_update = None
    learner_report_enrollments = 0
    learner_report_average_final_score = 0
    learner_report_badges = "0 / 0"
    learner_report_posts = 0
    learner_report_finished = 0
    learner_report_failed = 0
    learner_report_in_progress = 0
    learner_report_not_started = 0
    learner_report_total_time_spent = 0
    learner_course_table = None

    last_reportlog = ReportLog.get_latest()
    if last_reportlog:
        last_update = last_reportlog.created

        learner_report = LearnerDailyReport.get_by_day(date_time=last_update, user=user, org=org)
        if learner_report:
            learner_report_enrollments = learner_report.enrollments
            learner_report_average_final_score = learner_report.average_final_score
            learner_report_badges = learner_report.badges
            learner_report_posts = learner_report.posts
            learner_report_finished = learner_report.finished
            learner_report_failed = learner_report.failed
            learner_report_not_started = learner_report.not_started
            learner_report_in_progress = learner_report.in_progress
            learner_report_total_time_spent = learner_report.total_time_spent

        learner_course_table, learner_course_reports = get_transcript_table(orgs,
                                                                            user.id,
                                                                            last_update,
                                                                            request=request,
                                                                            html_links=True,
                                                                            with_gradebook_link=with_gradebook_link)
        config_tables(request, learner_course_table)

        all_overviews = CourseOverview.objects.all()
        report_courses = [report.course_id for report in learner_course_reports]
        for overview in all_overviews:
            if overview.id in report_courses:
                courses.append({'id': overview.id, 'display_name': overview.display_name_with_default})

        if configuration_helpers.get_value("ENABLE_WAIVER_REQUEST", False) and report_type == "my_transcript":
            for report in learner_course_reports:
                content = toc_for_course(
                            user, request, modulestore().get_course(report.course_id), None, None, None)
                if 'chapters' in content:
                    for chapter in content['chapters']:
                        chapter['disabled'] = True
                        for section in chapter['sections']:
                            section.pop('due', None)
                            if section['graded']:
                                chapter['disabled'] = False

                    course_contents[unicode(report.course_id)] = content
            course_contents = json.dumps(course_contents)

    return render_to_response(
            template,
            {
                'course_contents': course_contents,
                'courses': courses,
                'last_update': dt2str(last_update),
                'learner_report_enrollments': learner_report_enrollments if learner_report_enrollments else None,
                'learner_report_average_final_score': learner_report_average_final_score,
                'learner_report_badges': learner_report_badges,
                'learner_report_posts': learner_report_posts,
                'learner_report_finished': learner_report_finished,
                'learner_report_failed': learner_report_failed,
                'learner_report_in_progress': learner_report_in_progress,
                'learner_report_not_started': learner_report_not_started,
                'learner_report_total_time_spent': learner_report_total_time_spent,
                'learner_course_table': learner_course_table,
                'list_table_downloads_url': reverse('list_table_downloads', kwargs={'report': report_type}),
                'user_profile_name': user.profile.name,
                'user_id': user.id,
            }
        )


def _transcript_view_data(request, with_gradebook_link=False):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return JsonResponseBadRequest({"message": _("Response Not Found.")})

    if len(orgs) == 1:
        org = orgs[0]
    else:
        org = get_combined_org(orgs)

    body_data = request.body.decode('utf-8')
    data = json.loads(body_data)
    user_id = data.get('user_id', request.user.id)

    table = []
    summary_columns = []
    column_order = []

    last_reportlog = ReportLog.get_latest()
    if last_reportlog:
        last_update = last_reportlog.created

        learner_course_table, learner_course_reports = get_transcript_table(orgs,
                                                                            user_id,
                                                                            last_update,
                                                                            request=request,
                                                                            html_links=True,
                                                                            sort=data.get('sort'),
                                                                            with_gradebook_link=with_gradebook_link)
        summary_columns = ['Progress',
                           'Current Score',
                           'Badges',
                           'Total Time Spent']

    return json_response(learner_course_table,
                         data.get('page', {}),
                         summary_columns,
                         column_order)


@transaction.non_atomic_requests
@analytics_on
@analytics_member_required
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def transcript_view_data(request):
    return _transcript_view_data(request, with_gradebook_link=True)


@transaction.non_atomic_requests
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def my_transcript_view_data(request):
    return _transcript_view_data(request)


@login_required
@ensure_csrf_cookie
def my_transcript_view(request):
    return _transcript_view(request.user, request, "triboo_analytics/my_transcript.html", "my_transcript")


@login_required
@ensure_csrf_cookie
def my_transcript_view_pdf(request):
    return _transcript_view(request.user, request, "triboo_analytics/my_transcript_pdf.html", "my_transcript")


@analytics_on
@login_required
@ensure_csrf_cookie
def transcript_view(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except (ValueError, User.DoesNotExist):
        return render_to_response(
                "triboo_analytics/transcript.html",
                {"error_message": _("Invalid User ID")}
            )
    return _transcript_view(user, request, "triboo_analytics/transcript.html", "transcript", with_gradebook_link=True)


@analytics_on
@login_required
@ensure_csrf_cookie
def transcript_view_pdf(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except (ValueError, User.DoesNotExist):
        return render_to_response(
                "triboo_analytics/transcript.html",
                {"error_message": _("Invalid User ID")}
            )
    return _transcript_view(user, request, "triboo_analytics/transcript_pdf.html", "transcript")


@require_POST
@login_required
@ensure_csrf_cookie
def waiver_request_view(request):
    """
    This request accepts POST method only, it creates a waiver request,
    and send email to instructor
    """
    course_id = request.POST.get('course_id')
    sections = request.POST.get('sections')
    description = request.POST.get('description')

    try:
        enrollment = CourseEnrollment.get_enrollment(request.user, CourseKey.from_string(course_id))
        waiver_request = WaiverRequest.create_waiver_request(enrollment=enrollment,
                                                             description=description,
                                                             sections=sections)
        course_key = CourseKey.from_string(course_id)

        # if instructor information is set in site conf, we send email to that instructor
        instructor_name = configuration_helpers.get_value('INSTRUCTOR_NAME', "")
        instructor_email = configuration_helpers.get_value('INSTRUCTOR_EMAIL', None)
        if instructor_email:
            users = [{'name': instructor_name, 'email': instructor_email,
                      'language': None}]
            email_type = 'forced_waiver_request'
        else:
            email_type = 'waiver_request'
            instructors = CourseInstructorRole(course_key).users_with_role()
            users = []
            if instructors:
                for user in instructors:
                    users.append({'name': user.profile.name, 'email': user.email,
                                  'language': get_user_email_language(user)})
            else:
                staffs = CourseStaffRole(course_key).users_with_role()
                for user in staffs:
                    users.append({'name': user.profile.name, 'email': user.email,
                                  'language': get_user_email_language(user)})

        sections = json.loads(sections)
        if isinstance(sections, list):
            sections = None
        else:
            sections = ', '.join(sections)

        param_dict = {'course_name': enrollment.course.display_name_with_default,
                      'site_theme': request.site_theme.id,
                      'sections': sections,
                      'description': description,
                      'email_type': email_type,
                      'learner_name': request.user.profile.name,
                      'username': request.user.username,
                      'country': request.user.profile.lt_custom_country or request.user.profile.country or 'Unknown',
                      'location': request.user.profile.location or 'Unknown',
                      'platform_name': configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME),
                      'accept_link': request.build_absolute_uri(reverse('process_waiver_request', kwargs={
                          'course_id': course_id,
                          'waiver_id': waiver_request.id
                      })) + '?accept=1',
                      'deny_link': request.build_absolute_uri(reverse('process_waiver_request', kwargs={
                          'course_id': course_id,
                          'waiver_id': waiver_request.id
                      })) + '?accept=0'}
        send_waiver_request_email.delay(users, param_dict)
    except PendingRequestExitsError:
        message = _("There can only be one exiting pending task!")
        return JsonResponse({"message": message}, status=409)
    except RequestAlreadyApprovedError:
        message = _("The request is already approved by the instructor!")
        return JsonResponse({"message": message}, status=409)
    except Exception:
        message = _("Unknown error. Please contact the support!")
        return JsonResponse({"message": message}, status=400)

    return JsonResponse({"message": _("Request sent successfully!")}, status=201)


@require_GET
@login_required
@require_level('staff')
def process_waiver_request(request, course_id, waiver_id):
    """
    The view process the waiver request, and send notification email to learner.

    It will return to the processing waiver request page to show the result and
    then redirect to the transcript page
    """
    waiver_request = WaiverRequest.objects.get(id=waiver_id)
    accept_state = request.GET.get('accept')
    instructor = request.user

    if waiver_request.approved is None:
        enrollment = waiver_request.enrollment
        request_sections = json.loads(waiver_request.sections)
        if isinstance(request_sections, dict):
            usage_ids = []
            sections = ', '.join(request_sections)
            for i in request_sections:
                usage_ids += request_sections[i]
        else:
            usage_ids = request_sections
            sections = None
        if accept_state == '1':
            course_key = CourseKey.from_string(course_id)
            course = get_course_by_id(course_key, depth=None)
            grade_models = []
            user = enrollment.user

            for requested_usage_id in usage_ids:
                try:
                    usage_key = UsageKey.from_string(requested_usage_id)
                except InvalidKeyError as exc:
                    logger.info("GradeOverride for User: {} has failed, Reason: {}".format(
                        user.id,
                        exc
                    ))
                    continue
                try:
                    subsection_grade_model = PersistentSubsectionGrade.objects.get(
                        user_id=user.id,
                        course_id=course_key,
                        usage_key=usage_key
                    )
                    if subsection_grade_model.earned_all == subsection_grade_model.possible_all and \
                            subsection_grade_model.earned_graded == subsection_grade_model.possible_graded and \
                            subsection_grade_model.earned_all == subsection_grade_model.earned_graded:
                        usage_ids.remove(requested_usage_id)
                        continue
                    else:
                        grade_models.append(subsection_grade_model)
                except PersistentSubsectionGrade.DoesNotExist:
                    subsection = course.get_child(usage_key)
                    if subsection:
                        subsection_grade_model = create_subsection_grade(user, course, subsection)
                        if subsection_grade_model.earned_all == subsection_grade_model.possible_all and \
                                subsection_grade_model.earned_graded == subsection_grade_model.possible_graded and \
                                subsection_grade_model.earned_all == subsection_grade_model.earned_graded:
                            usage_ids.remove(requested_usage_id)
                            continue
                        else:
                            grade_models.append(subsection_grade_model)
                    else:
                        continue
            if grade_models:
                for obj in grade_models:
                    override_data = {
                        "earned_all_override": obj.possible_all,
                        "possible_all_override": obj.possible_all,
                        "earned_graded_override": obj.possible_all,
                        "possible_graded_override": obj.possible_all
                    }
                    override = create_override(instructor, obj, **override_data)
                    logger.info("GradeOverride succeeded for User: {}, Usage_id: {}, Instrucotr: {}".format(
                        user.id,
                        obj.usage_key,
                        instructor.id
                    ))

            waiver_request.approved = True
            waiver_request.instructor = instructor
            waiver_request.save()
            message = _("The waiver request has been accepted!")
            send_mail_to_student(enrollment.user.email, {'message': 'waiver_request_approved',
                                                         'name': enrollment.user.profile.name,
                                                         'sections': sections,
                                                         'course_name': enrollment.course.display_name_with_default,
                                                         'transcript': request.build_absolute_uri(
                                                             reverse('analytics_my_transcript')),
                                                         'site_name': None
                                                         },
                                 language=get_user_email_language(enrollment.user))

        elif accept_state == '0':
            waiver_request.approved = False
            waiver_request.instructor = instructor
            waiver_request.save()
            message = _("The waiver request has been denied!")
            send_mail_to_student(enrollment.user.email, {'message': 'waiver_request_denied',
                                                         'name': enrollment.user.profile.name,
                                                         'sections': sections,
                                                         'course_name': enrollment.course.display_name_with_default,
                                                         'site_name': None
                                                         },
                                 language=get_user_email_language(enrollment.user))
        else:
            return redirect('spoc_gradebook', course_id)

    else:
        if waiver_request.approved:
            message = _("The waiver request is already accepted by {name}").format(
                name=waiver_request.instructor.profile.name
            )
        else:
            message = _("The waiver request is already denied by {name}").format(
                name=waiver_request.instructor.profile.name
            )

    grade_page_url = reverse('spoc_gradebook', kwargs={'course_id': course_id})
    return render_to_response(
        'triboo_analytics/process_waiver_request.html',
        {
            'message': message,
            'grade_page_url': grade_page_url
        }
    )


def create_subsection_grade(user, course, subsection):
    course_data = CourseData(user, course=course)
    subsection_grade = CreateSubsectionGrade(subsection, course_data.structure, {}, {})
    return subsection_grade.update_or_create_model(user, force_update_subsections=True)


def create_override(request_user, subsection_grade_model, **override_data):
    """
    Helper method to create a `PersistentSubsectionGradeOverride` object
    and send a `GRADE_EDITED` signal.
    """
    override = PersistentSubsectionGradeOverride.update_or_create_override(
        requesting_user=request_user,
        subsection_grade_model=subsection_grade_model,
        feature=PersistentSubsectionGradeOverrideHistory.GRADEBOOK,
        **override_data
    )

    GRADE_EDITED.send(
        sender=None,
        user_id=subsection_grade_model.user_id,
        course_id=subsection_grade_model.course_id,
        modified=override.modified,
    )

    set_event_transaction_type(SUBSECTION_GRADE_CALCULATED)
    create_new_event_transaction_id()

    recalculate_subsection_grade_v3.apply(
        kwargs=dict(
            user_id=subsection_grade_model.user_id,
            anonymous_user_id=None,
            course_id=text_type(subsection_grade_model.course_id),
            usage_id=text_type(subsection_grade_model.usage_key),
            only_if_higher=False,
            expected_modified_time=to_timestamp(override.modified),
            score_deleted=False,
            event_transaction_id=unicode(get_event_transaction_id()),
            event_transaction_type=unicode(get_event_transaction_type()),
            score_db_table=ScoreDatabaseTableEnum.overrides,
            force_update_subsections=True,
        )
    )
    # Emit events to let our tracking system to know we updated subsection grade
    subsection_grade_calculated(subsection_grade_model)
    return override


@analytics_on
@login_required
@analytics_full_member_required
@ensure_csrf_cookie
def microsite_view(request):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return HttpResponseNotFound()

    microsite_report_org = orgs[0]
    if len(orgs) > 1:
        microsite_report_org = get_combined_org(orgs)

    last_reportlog = ReportLog.get_latest()
    last_update = ""
    if last_reportlog:
        last_update = last_reportlog.created
        microsite_report = MicrositeDailyReport.get_by_day(date_time=last_update, org=microsite_report_org)

        from_date = request.GET.get('from_day')
        from_date = datetime.strptime(from_date, "%Y-%m-%d").date() if from_date else None
        to_date = request.GET.get('to_day')
        to_date = datetime.strptime(to_date, "%Y-%m-%d").date() if to_date else None
        unique_visitors_csv, users_csv, average_time_spent_csv = MicrositeDailyReport.get_csv_data(
                                                                    microsite_report_org,
                                                                    from_date,
                                                                    to_date)
        # logger.info("ANALYTICS -- unique_visitors_csv = %s" % unique_visitors_csv)
        # logger.info("ANALYTICS -- users_csv = %s" % users_csv)
        # logger.info("ANALYTICS -- average_time_spent_csv = %s" % average_time_spent_csv)

        users_by_country_csv = ""
        country_reports = CountryDailyReport.filter_by_day(date_time=last_update, org=microsite_report_org)
        for report in country_reports:
            country_code = report.country.numeric
            if country_code:
                if (country_code / 100) == 0:
                    if (country_code / 10) == 0:
                        country_code = "00%d" % country_code
                    else:
                        country_code = "0%d" % country_code
                else:
                    country_code = "%d" % country_code
                users_by_country_csv += "%s,%s,%d\\n" % (country_code, report.country.name, report.nb_users)

        return render_to_response(
                "triboo_analytics/microsite.html",
                {
                    'last_update': dt2str(last_update),
                    'microsite_report': microsite_report,
                    'unique_visitors_csv': unique_visitors_csv,
                    'users_csv_data': users_csv,
                    'average_time_spent_csv': average_time_spent_csv,
                    'users_by_country_csv': users_by_country_csv,
                    'list_table_downloads_url': reverse('list_table_downloads', kwargs={'report': 'global'}),
                }
            )

    return render_to_response(
        "triboo_analytics/microsite.html",
        {
            'last_update': "",
            'microsite_report': None,
            'unique_visitors_csv': "",
            'users_by_country_csv': "",
            'list_table_downloads_url': reverse('list_table_downloads', kwargs={'report': 'global'}),
        }
    )


def get_all_courses(request, orgs):
    course_overviews = CourseOverview.objects.none()

    for org in orgs:
        org_course_overviews = CourseOverview.objects.filter(org=org, start__lte=timezone.now())
        course_overviews = course_overviews | org_course_overviews

    overviews = []
    if ANALYTICS_LIMITED_ACCESS_GROUP in [group.name for group in request.user.groups.all()]:
        for overview in course_overviews:
            instructors = set(CourseInstructorRole(overview.id).users_with_role())
            # staff should be a superset of instructors. Do a union to ensure.
            staff = set(CourseStaffRole(overview.id).users_with_role()).union(instructors)
            if request.user in staff:
                overviews.append(overview)
    else:
        overviews = course_overviews

    courses = {"%s" % overview.id: overview.display_name_with_default for overview in overviews}
    courses_list = sorted(courses.items(), key=operator.itemgetter(1))

    return courses, courses_list


@login_required
@analytics_on
@analytics_member_required
@ensure_csrf_cookie
def course_view(request):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return HttpResponseNotFound()

    course_overviews = CourseOverview.objects.none()

    for org in orgs:
        org_course_overviews = CourseOverview.objects.filter(org=org, start__lte=timezone.now())
        course_overviews = course_overviews | org_course_overviews

    overviews = []
    if ANALYTICS_LIMITED_ACCESS_GROUP in [group.name for group in request.user.groups.all()]:
        for overview in course_overviews:
            instructors = set(CourseInstructorRole(overview.id).users_with_role())
            # staff should be a superset of instructors. Do a union to ensure.
            staff = set(CourseStaffRole(overview.id).users_with_role()).union(instructors)
            if request.user in staff:
                overviews.append(overview)
    else:
        overviews = course_overviews

    courses = {"%s" % overview.id: overview.display_name_with_default for overview in overviews}
    courses_list = sorted(courses.items(), key=operator.itemgetter(1))

    course_id = request.GET.get('course_id', None)
    if not course_id:
        return render_to_response(
                'triboo_analytics/course.html',
                {
                    'courses': courses_list,
                    'course_id': None,
                    'list_table_downloads_url': reverse('list_table_downloads', kwargs={'report': 'course'}),
                }
            )

    if course_id in courses.keys():
        course_key = CourseKey.from_string(course_id)

        course_report = None
        unique_visitors_csv = None
        average_complete_time_csv = None
        last_update = None

        last_reportlog = ReportLog.get_latest()
        if last_reportlog:
            last_update = last_reportlog.course
            course_report = CourseDailyReport.get_by_day(date_time=last_update, course_id=course_key)
            unique_visitors_csv, average_complete_time_csv = CourseDailyReport.get_csv_data(course_key, None, None)
            last_update = dt2str(last_update)

        # logger.info("ANALYTICS -- unique_visitors_csv = %s" % unique_visitors_csv)
        # logger.info("ANALYTICS -- average_complete_time_csv = %s" % average_complete_time_csv)

        return render_to_response(
            "triboo_analytics/course.html",
            {
                'courses': courses_list,
                'course_id': course_id,
                'course_name': courses.get(course_id),
                'last_update': last_update,
                'course_report': course_report,
                'unique_visitors_csv': unique_visitors_csv,
                'average_complete_time_csv': average_complete_time_csv,
                'list_table_downloads_url': reverse('list_table_downloads', kwargs={'report': 'course'}),
            }
        )
    else:
        return render_to_response(
            "triboo_analytics/course.html",
            {'error_message': _("Invalid Course ID")}
        )


@transaction.non_atomic_requests
@analytics_on
@analytics_member_required
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def course_view_data(request):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return JsonResponseBadRequest({"message": _("Response Not Found.")})

    body_data = request.body.decode('utf-8')
    data = json.loads(body_data)
    report = data.get('report_type', 'course_summary')
    if report not in ['course_summary', 'course_progress', 'course_time_spent']:
        return JsonResponseBadRequest({"message": _("Response Not Found.")})

    try:
        course_key = CourseKey.from_string(data.get('course_id', None))

    except InvalidKeyError:
        return JsonResponseBadRequest({"message": _("Invalid course id.")})

    table = []
    summary_columns = []
    column_order = []

    last_reportlog = ReportLog.get_latest()
    if last_reportlog:
        last_update = last_reportlog.course
        filter_kwargs, exclude = get_period_kwargs(data, course_id=course_key)

        if report == "course_summary":
            logger.info("ANALYTICS -- Course Summary kwargs=%s" % filter_kwargs)
            table = get_table_data(LearnerCourseJsonReport, CourseTable, filter_kwargs, exclude,
                                   by_period=True, sort=data.get('sort'))
            summary_columns = ['Progress',
                               'Current Score',
                               'Badges',
                               'Posts',
                               'Total Time Spent']

        elif report == "course_progress":
            table, column_order = get_progress_table_data(course_key, filter_kwargs, exclude, sort=data.get('sort'))

        elif report == "course_time_spent":
            table, column_order = get_time_spent_table_data(course_key, filter_kwargs, exclude, sort=data.get('sort'))

    return json_response(table,
                         data.get('page'),
                         summary_columns,
                         column_order)


@login_required
@analytics_on
@analytics_full_member_required
@ensure_csrf_cookie
def learner_view(request):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return HttpResponseNotFound()

    last_update = None
    last_reportlog = ReportLog.get_latest()
    if last_reportlog:
        last_update = dt2str(last_reportlog.learner)

    return render_to_response(
        "triboo_analytics/learner.html",
        {
            'list_table_downloads_url': reverse('list_table_downloads', kwargs={'report': 'learner'}),
            'last_update': last_update
        }
    )


@transaction.non_atomic_requests
@analytics_on
@analytics_full_member_required
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def learner_view_data(request):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return JsonResponseBadRequest({"message": _("Response Not Found.")})

    learner_report_org = orgs[0]
    if len(orgs) > 1:
        learner_report_org = get_combined_org(orgs)

    body_data = request.body.decode('utf-8')
    data = json.loads(body_data)

    table = []
    summary_columns = ['Enrollments',
                       'Successful',
                       'Unsuccessful',
                       'Not Started',
                       'Average Final Score',
                       'Badges',
                       'Posts',
                       'Total Time Spent',
                       'In Progress']

    last_reportlog = ReportLog.get_latest()
    if last_reportlog:
        last_update = last_reportlog.learner
        filter_kwargs, exclude = get_period_kwargs(data)
        filter_kwargs['org'] = learner_report_org
        if 'to_date' not in filter_kwargs.keys():
            filter_kwargs['to_date'] = last_update.date()
        if 'to_date' in filter_kwargs.keys():
            table = get_table_data(LearnerDailyReport, LearnerDailyTable, filter_kwargs, exclude,
                                   by_period=True, html_links=True, sort=data.get('sort'))
    return json_response(table,
                         data.get('page'),
                         summary_columns)


@analytics_on
@login_required
@analytics_full_member_required
@ensure_csrf_cookie
def ilt_view(request):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return HttpResponseNotFound()

    last_update = None
    last_reportlog = ReportLog.get_latest()
    if last_reportlog:
        last_update = dt2str(last_reportlog.country)

    return render_to_response(
        "triboo_analytics/ilt.html",
        {
            'list_table_downloads_url': reverse('list_table_downloads', kwargs={'report': 'ilt'}),
            'last_update': last_update
        }
    )


@transaction.non_atomic_requests
@analytics_on
@analytics_full_member_required
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def ilt_view_data(request):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return JsonResponseBadRequest({"message": _("Response Not Found.")})

    body_data = request.body.decode('utf-8')
    data = json.loads(body_data)
    report = data.get('report_type', 'ilt_global')
    if report not in ['ilt_global', 'ilt_learner']:
        return JsonResponseBadRequest({"message": _("Response Not Found.")})

    table = []

    last_reportlog = ReportLog.get_latest()
    if last_reportlog:
        last_update = last_reportlog.created
        filter_kwargs, exclude = get_ilt_period_kwargs(data, orgs)

        if report == "ilt_global":
            table = get_ilt_global_table_data(filter_kwargs, sort=data.get('sort'))

        elif report == "ilt_learner":
            table = get_ilt_learner_table_data(filter_kwargs, exclude, sort=data.get('sort'))

    return json_response(table,
                         data.get('page'),
                         [])


@login_required
@analytics_on
@analytics_full_member_required
@ensure_csrf_cookie
def customized_view(request):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return HttpResponseNotFound()

    report_type = request.GET.get('report_type', None)
    courses_selected = request.GET.get('courses_selected', None)
    report_types = [
        ('course_summary', _('Course Summary Report'), 'multiple'),
        ('course_progress', _('Course Grade Report'), 'single'),
        ('course_time_spent', _('Course Time Spent Report'), 'single'),
        ('learner', _('Learner Report'), ''),
        ('ilt_global', _('ILT Global Report'), 'multiple'),
        ('ilt_learner', _('ILT Learner Report'), 'multiple'),
    ]
    export_formats = ['csv', 'xls', 'json']
    courses, courses_list = get_all_courses(request, orgs)
    last_reportlog = ReportLog.get_latest()
    last_update = last_reportlog.created

    course_triples = []
    for course_id, course_name in courses_list:
        course_key = CourseKey.from_string(course_id)
        course_report = CourseDailyReport.get_by_day(date_time=last_update, course_id=course_key)
        triple = (course_id, course_name, course_report.enrollments if course_report else None, None)
        course_triples.append(triple)

    course_ids_mapping = {}         # {course_id, [course_title, set<ilt_module_id>]}
    used_ilt_module_ids = {}        # {ilt_module_id, set<session_id>}
    ilt_module_id_2_reports = {}    # {ilt_module_id, reports}
    # 1 course_id ==> ilt_module_ids ==> session ids count
    for ss in IltSession.objects.values('id', 'ilt_module_id'):
        if ss['ilt_module_id'] not in used_ilt_module_ids:
            used_ilt_module_ids[ss['ilt_module_id']] = set([ss['id']])
        else:
            used_ilt_module_ids[ss['ilt_module_id']].add(ss['id'])

    for ilt_of_course in IltModule.objects.filter(
        id__in=Subquery(IltSession.objects.values('ilt_module_id'))
    ).values('id', 'course_id', 'course_display_name'):
        _id = ilt_of_course['id']
        if _id not in used_ilt_module_ids:
            continue

        course_id = str(ilt_of_course['course_id'])
        if course_id not in course_ids_mapping:
            course_ids_mapping[course_id] = [ilt_of_course['course_display_name'], set([_id])]
        else:
            course_ids_mapping[course_id][1].add(_id)

    for ilt_learner_report in IltLearnerReport.objects.filter(
        ilt_module_id__in=list(used_ilt_module_ids.keys())
    ).values('id', 'ilt_module_id'):
        ilt_module_id = ilt_learner_report['ilt_module_id']
        if ilt_module_id not in ilt_module_id_2_reports:
            ilt_module_id_2_reports[ilt_module_id] = set([ilt_learner_report['id']])
        else:
            ilt_module_id_2_reports[ilt_module_id].add(ilt_learner_report['id'])

    def _count_items_by_dict_key(dict_obj, _key):
        if _key not in dict_obj:
            return 0
        else:
            return len(dict_obj[_key])

    for course_id, params in course_ids_mapping.items():
        course_display_name = params[0]
        ilt_module_ids = params[1]
        report_lines_count = sum(
            [_count_items_by_dict_key(used_ilt_module_ids, module_id) for module_id in ilt_module_ids]
        )
        triple = (
            course_id, course_display_name, report_lines_count, 'ilt_global'
        )
        course_triples.append(triple)

    for course_id, params in course_ids_mapping.items():
        course_display_name = params[0]
        ilt_module_ids = params[1]
        report_lines_count = sum(
            [_count_items_by_dict_key(ilt_module_id_2_reports, module_id) for module_id in ilt_module_ids]
        )
        triple = (
            course_id, course_display_name, report_lines_count, 'ilt_learner'
        )
        course_triples.append(triple)

    user_properties_helper = UserPropertiesHelper()

    request_copy = request.GET.copy()
    request_copy = new_request_copy(request_copy)
    filter_form = TableFilterForm(request_copy, user_properties_helper.get_possible_choices())
    user_properties_form = UserPropertiesForm(request_copy,
                                              user_properties_helper.get_possible_choices(False),
                                              user_properties_helper.get_initial_choices())

    return render_to_response(
        "triboo_analytics/customized.html",
        {
            'report_types': report_types,
            'report_type': report_type,
            'courses': course_triples,
            'courses_selected': courses_selected,
            'filter_form': filter_form,
            'user_properties_form': user_properties_form,
            'export_formats': export_formats,
            'list_table_downloads_url': reverse('list_table_downloads', kwargs={'report': 'course'}),
        }
    )


def _export_table(request, course_key, report_name, report_args):
    try:
        task_type = 'triboo_analytics_export_table'
        task_class = generate_export_table_task
        export_format = request.POST.get('format', None) if request.method == "POST" else request.GET.get('_export', None)
        if not export_format:
            body_data = request.body.decode('utf-8')
            data = json.loads(body_data)
            export_format = data.get('format', None)
        task_input = {
            'user_id': request.user.id,
            'report_name': report_name,
            'export_format': export_format,
            'report_args': report_args
        }
        task_key = ""
        submit_task(request, task_type, task_class, course_key, task_input, task_key)

    except UnsupportedExportFormatError:
        return JsonResponseBadRequest({"message": _("Invalid export format.")})
    except AlreadyRunningError:
        return JsonResponse({'message': 'task is already running.'})

    return JsonResponse({"message": _("The report is being exported. Note that this operation can take "
                                      "several minutes. When the report will be ready, it will appear "
                                      "in the list of reports ready to download under the cloud icon "
                                      "in the menu bar and you will be able to download it.")})


def _transcript_export_table(request, user):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return JsonResponseBadRequest({"message": _("Response Not Found.")})

    last_reportlog = ReportLog.get_latest()
    if last_reportlog:
        report_args = {
            'orgs': orgs,
            'user_id': user.id,
            'username': user.username,
            'last_update': dt2str(last_reportlog.created)
        }
        return _export_table(request, CourseKeyField.Empty, 'transcript', report_args)
    return JsonResponseBadRequest({"message": _("No report to export.")})

@transaction.non_atomic_requests
@analytics_on
@analytics_full_member_required
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def my_transcript_export_table(request):
    return _transcript_export_table(request, request.user)


@transaction.non_atomic_requests
@analytics_on
@analytics_full_member_required
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def transcript_export_table(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except (ValueError, User.DoesNotExist):
        return JsonResponseBadRequest({"message": _("Invalid User ID")})
    return _transcript_export_table(request, user)


@transaction.non_atomic_requests
@analytics_on
@analytics_member_required
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def course_export_table(request):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return JsonResponseBadRequest({"message": _("Response Not Found.")})

    body_data = request.body.decode('utf-8')
    data = json.loads(body_data)
    report = data.get('report_type', 'course_summary')
    if report not in ['course_summary', 'course_progress', 'course_time_spent']:
        return JsonResponseBadRequest({"message": _("Response Not Found.")})

    try:
        course_key = CourseKey.from_string(data.get('course_id', None))
    except InvalidKeyError:
        return JsonResponseBadRequest({"message": _("Invalid course id.")})

    last_reportlog = ReportLog.get_latest()
    if not last_reportlog:
        return None

    last_update = last_reportlog.course

    filter_kwargs, exclude = get_period_kwargs(data,
                                               course_id=course_key,
                                               as_string=True)

    report_args = {
        'filter_kwargs': filter_kwargs,
        'exclude': list(exclude)
    }

    if report == "course_summary":
        report_args.update({
            'report_cls': LearnerCourseJsonReport.__name__,
            'table_cls': CourseTable.__name__
        })
        return _export_table(request, course_key, 'summary_report', report_args)

    elif report == "course_progress":
        return _export_table(request, course_key, 'progress_report', report_args)

    elif report == "course_time_spent":
        return _export_table(request, course_key, 'time_spent_report', report_args)


@transaction.non_atomic_requests
@analytics_on
@analytics_full_member_required
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def learner_export_table(request):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return JsonResponseBadRequest({"message": _("Response Not Found.")})

    learner_report_org = orgs[0]
    if len(orgs) > 1:
        learner_report_org = get_combined_org(orgs)

    body_data = request.body.decode('utf-8')
    data = json.loads(body_data)

    last_reportlog = ReportLog.get_latest()
    if not last_reportlog:
        return None

    last_update = last_reportlog.learner
    filter_kwargs, exclude = get_period_kwargs(data, as_string=True)
    filter_kwargs['org'] = learner_report_org
    if 'to_date' not in filter_kwargs.keys():
        filter_kwargs['to_date'] = day2str(last_update)

    report_args = {
        'report_cls': LearnerDailyReport.__name__,
        'table_cls': LearnerDailyTable.__name__,
        'filter_kwargs': filter_kwargs,
        'exclude': list(exclude)
    }
    return _export_table(request, CourseKeyField.Empty, 'learner_report', report_args)


@transaction.non_atomic_requests
@analytics_on
@analytics_member_required
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def ilt_export_table(request):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return JsonResponseBadRequest({"message": _("Response Not Found.")})

    body_data = request.body.decode('utf-8')
    data = json.loads(body_data)
    report = data.get('report_type', 'ilt_global')
    if report not in ['ilt_global', 'ilt_learner']:
        return JsonResponseBadRequest({"message": _("Response Not Found.")})

    last_reportlog = ReportLog.get_latest()
    if not last_reportlog:
        return None

    last_update = last_reportlog.created
    filter_kwargs, exclude = get_ilt_period_kwargs(data, orgs, as_string=True)

    report_args = {
        'filter_kwargs': filter_kwargs,
        'exclude': list(exclude)
    }

    if report == "ilt_global":
        return _export_table(request, CourseKeyField.Empty, 'ilt_global_report', report_args)

    elif report == "ilt_learner":
        return _export_table(request, CourseKeyField.Empty, 'ilt_learner_report', report_args)


def get_customized_kwargs(request_dict):
    kwargs = {}
    query_tuples = request_dict.get('query_tuples')
    for queried_string, field in query_tuples:
        if queried_string:
            prop = field.split('_', 1)[1]
            db_prefix = "user__"
            if prop not in ['email', 'username', 'date_joined']:
                db_prefix += "profile__"
            queried_field = db_prefix + prop

            if queried_field == "user__profile__country":
                queried_country = queried_string.lower()
                country_code_by_name = {name.lower(): code for code, name in list(countries)}
                country_codes = []
                for country_name in country_code_by_name.keys():
                    if queried_country in country_name:
                        country_codes.append(country_code_by_name[country_name])
                if country_codes:
                    kwargs['user__profile__country__in'] = country_codes
                else:
                    kwargs['invalid'] = True
            elif queried_field == "user__profile__lt_gdpr":
                queried_str = queried_string.lower()
                if queried_str == "true":
                    kwargs[queried_field] = True
                elif queried_str == "false":
                    kwargs[queried_field] = False
                else:
                    kwargs['invalid'] = True
            else:
                kwargs[queried_field + '__icontains'] = queried_string

    all_properties = ["user_%s" % prop for prop in AVAILABLE_CHOICES.keys()]
    config_properties = configuration_helpers.get_value('ANALYTICS_USER_PROPERTIES',
                                                        settings.FEATURES.get('ANALYTICS_USER_PROPERTIES', {}))
    selected_properties = request_dict.get('selected_properties')
    if selected_properties:
        selected_properties += ['user_name']
    else:
        selected_properties = ['user_name']
        for prop in AVAILABLE_CHOICES.keys():
            if prop in config_properties.keys() and config_properties[prop] == "default":
                selected_properties.append("user_%s" % prop)
    exclude = set(all_properties) - set(selected_properties)

    return kwargs, exclude


def get_customized_period_kwargs(request_dict, kwargs, course_id=None, as_string=False, with_period_start=False):
    if course_id:
        kwargs['course_id'] = "%s" % course_id if as_string else course_id

    from_day = request_dict.get('from_day')
    to_day = request_dict.get('to_day')
    if from_day and to_day:
        from_date = utc.localize(datetime.strptime(from_day, '%Y-%m-%d'))
        to_date = utc.localize(datetime.strptime(to_day, '%Y-%m-%d')) + timedelta(days=1)
        last_reportlog = ReportLog.get_latest(from_date=from_date, to_date=to_date)
        if last_reportlog:
            last_analytics_success = last_reportlog.created
            user_ids = LearnerVisitsDailyReport.get_active_user_ids(from_date,
                                                                    to_date,
                                                                    course_id)
            kwargs.update({
                'date_time': day2str(last_analytics_success) if as_string else last_analytics_success,
                'user_id__in': user_ids
            })
            if with_period_start:
                period_start_reportlog = ReportLog.get_latest(to_date=from_date)
                if period_start_reportlog:
                    period_start = period_start_reportlog.created
                    kwargs['period_start'] = day2str(period_start) if as_string else period_start

    return kwargs


@transaction.non_atomic_requests
@analytics_on
@analytics_member_required
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def customized_export_table(request):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return HttpResponseNotFound()

    body_data = request.body.decode('utf-8')
    data = json.loads(body_data)
    report_type = data.get('report_type', 'course_summary')
    courses_selected = data.get('courses_selected', None)

    last_reportlog = ReportLog.get_latest()
    if not last_reportlog:
        return None

    if report_type in ['course_summary', 'course_progress', 'course_time_spent']:
        last_update = last_reportlog.course

        if report_type == "course_summary":
            filter_kwargs, exclude = get_period_kwargs(data, course_id=None, as_string=True)
            report_args = {
                'report_cls': LearnerCourseJsonReport.__name__,
                'filter_kwargs': filter_kwargs,
                'courses_selected': courses_selected,
                'table_cls': CustomizedCourseTable.__name__,
                'exclude': list(exclude)
            }
            return _export_table(request, CourseKeyField.Empty, 'summary_report_multiple', report_args)

        else:
            try:
                course_key = CourseKey.from_string(courses_selected)
            except InvalidKeyError:
                return JsonResponseBadRequest({"message": _("Invalid course id.")})

            filter_kwargs, exclude = get_period_kwargs(data, course_id=course_key, as_string=True)

            report_args = {
                'filter_kwargs': filter_kwargs,
                'exclude': list(exclude)
            }
            if report_type == "course_progress":
                return _export_table(request, course_key, 'progress_report', report_args)
            elif report_type == "course_time_spent":
                return _export_table(request, course_key, 'time_spent_report', report_args)

    elif report_type == 'learner':
        return learner_export_table(request)

    elif report_type in ['ilt_global', 'ilt_learner']:
        return ilt_export_table(request)


@transaction.non_atomic_requests
@analytics_on
@analytics_member_required
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def export_tables(request):
    """
    :param data:
        Filter condition to get query for table.
        Example:
            "{
                'report_type': 'course_summary',
                'courses_selected': 'course-v1:edX+DemoX+Demo_Course',
                'query_tuples': [['Yu', 'user_name'], ['China', 'user_country']],
                'from_day': '',
                'to_day': '',
                'selected_properties': ['user_lt_address', 'user_country'],
                'format': 'csv',
                'csrfmiddlewaretoken': 'nDou5pR169v76UwtX4XOpbQsSTLu6SexeWyd0ykjGR2ahYMV0OY7nddkYQqnT6ze',
                'page': '',
            }"
    :return:
        Serialized table data
    """

    body_data = request.body.decode('utf-8')
    data = json.loads(body_data)
    report_type = data.get('report_type', None)

    if report_type in ["course_summary", "course_progress", "course_time_spent"]:
        return course_export_table(request)

    elif report_type == "learner":
        return learner_export_table(request)

    elif report_type in ["ilt_global", "ilt_learner"]:
        return ilt_export_table(request)

    elif report_type == 'transcript':
        user_id = data.get('user_id', request.user.id)
        return transcript_export_table(request, user_id)


@analytics_on
def get_properties(request):
    user_properties_helper = UserPropertiesHelper()
    filters_data = user_properties_helper.get_possible_choices2(False)
    json_string = """
    {
        "status":1,
        "message":"",
        "list": [],
        "courses": []
    }
    """
    jsonData = json.loads(json_string)
    for item in filters_data:
        jsonData['list'].append(
            {
                'text': item[1],
                'value': item[0],
                'type': item[2]
            }
        )

    for ilt_of_course in IltModule.objects.filter(
        id__in=Subquery(IltSession.objects.values('ilt_module_id'))
    ).values('course_id', 'course_display_name').distinct():
        jsonData['courses'].append(
            {
                'text': ilt_of_course['course_display_name'],
                'value': str(ilt_of_course['course_id'])
            }
        )

    return JsonResponse(jsonData)


@login_required
@require_GET
def leaderboard_data(request):
    if not configuration_helpers.get_value("ENABLE_LEADERBOARD", False):
        return JsonResponse(status=404)
    period = request.GET.get('period')
    top = int(request.GET.get('top', DEFAULT_LEADERBOARD_TOP))
    orgs = configuration_helpers.get_current_site_orgs()
    orgs = "+".join(orgs)
    data = _leaderboard_data(request, period, orgs, top)
    return JsonResponse(data)


@login_required
def leaderboard_view(request):
    user_groups = [group.name for group in request.user.groups.all()]
    able_to_download = request.user.is_staff or ANALYTICS_ACCESS_GROUP in user_groups or \
                    ANALYTICS_LIMITED_ACCESS_GROUP in user_groups
    if not configuration_helpers.get_value("ENABLE_LEADERBOARD", False):
        raise Http404
    data = {"able_to_download": able_to_download}
    return render_to_response("triboo_analytics/leaderboard.html", data)


def _leaderboard_data(request, period, orgs, top=None):
    data = {}
    top_list = []
    query_set = LeaderBoardView.objects.filter(
        (Q(user__profile__org=orgs) | Q(user__profile__org=None)) &
        Q(user__is_staff=False)).select_related('user__profile')
    total_user = query_set.count()
    if period in ['week', 'month']:
        order_by = '-current_{}_score'.format(period)
        query_set = query_set.order_by(order_by)
    else:
        query_set = query_set.order_by('-total_score')

    result_set = query_set[:top] if top is not None and top <= total_user else query_set
    if top == LEADERBOARD_DASHBOARD_TOP:
        for i in result_set:
            try:
                name = i.user.profile.name or i.user.username
            except:
                name = i.user.username
            detail = {"Points": i.total_score, "Name": name,
                      "Portrait": get_profile_image_urls_for_user(i.user, request=request)["medium"],
                      "DateStr": strftime_localized(i.user.date_joined, "NUMBERIC_DATE_TIME")}
            top_list.append(detail)

    else:
        request_user_included = False
        real_time_rank = 0
        for i in result_set:
            status = None
            real_time_rank += 1
            if period == "month":
                point = i.current_month_score
                if i.last_month_rank == 0 or i.last_month_rank > real_time_rank:
                    status = "up"
                elif i.last_month_rank == real_time_rank:
                    status = "eq"
                else:
                    status = "down"
            elif period == "week":
                point = i.current_week_score
                if i.last_week_rank == 0 or i.last_week_rank > real_time_rank:
                    status = "up"
                elif i.last_week_rank == real_time_rank:
                    status = "eq"
                else:
                    status = "down"
            else:
                point = i.total_score

            try:
                name = i.user.profile.name or i.user.username
            except:
                name = i.user.username

            if top is None:
                detail = {"position": real_time_rank, "first_name": i.user.first_name,
                          "last_name": i.user.last_name,
                          "date_of_user_creation": strftime_localized(i.user.date_joined, "NUMBERIC_SHORT_DATE"),
                          "points": point}
            else:
                detail = {"Points": point, "Name": name, "Rank": real_time_rank,
                          "Portrait": get_profile_image_urls_for_user(i.user, request=request)["medium"],
                          "DateStr": strftime_localized(i.user.date_joined, "NUMBERIC_SHORT_DATE")}
                if status and real_time_rank <= 3:
                    detail["OrderStatus"] = status
                if i.user == request.user:
                    detail["Active"] = True
                    data["mission"] = i.get_leaderboard_detail()
                    request_user_included = True
            top_list.append(detail)
        if not request_user_included and top is not None and top < total_user and not request.user.is_staff:
            personal_rank = top
            for i in query_set[top:]:
                personal_rank += 1
                if i.user == request.user:
                    if period == "month":
                        point = i.current_month_score
                    elif period == "week":
                        point = i.current_week_score
                    else:
                        point = i.total_score

                    try:
                        name = i.user.profile.name or i.user.username
                    except:
                        name = i.user.username
                    detail = {"Points": point, "Name": name,
                              "Portrait": get_profile_image_urls_for_user(i.user, request=request)["medium"],
                              "Active": True, "Rank": personal_rank,
                              "DateStr": strftime_localized(i.user.date_joined, "NUMBERIC_SHORT_DATE")}
                    top_list.append(detail)
                    data["mission"] = i.get_leaderboard_detail()
                    break
        elif request and request.user.is_staff:
            staff_leaderboard = LeaderBoardView.objects.filter(user=request.user)
            if staff_leaderboard.exists():
                staff_leaderboard = staff_leaderboard.first()
                data['mission'] = staff_leaderboard.get_leaderboard_detail()
    last_updated = query_set.aggregate(Max("last_updated"))
    data.update({
        "list": top_list,
        "lastUpdate": strftime_localized(last_updated['last_updated__max'], "NUMBERIC_DATE_TIME"),
        "totalUser": total_user
    })

    return data


@login_required
@require_POST
def generate_leaderboard_report(request):
    if not configuration_helpers.get_value("ENABLE_LEADERBOARD", False):
        return JsonResponse(status=404)
    period = request.POST.get('period')
    file_format = request.POST.get('format')
    orgs = configuration_helpers.get_current_site_orgs()
    orgs = "+".join(orgs)
    try:
        generate_leaderboard_report_task.apply_async(
            kwargs={
                "period": period,
                "user_id": request.user.id,
                "username": request.user.username,
                "file_format": file_format,
                "orgs": orgs
            }
        )
    except Exception as e:
        return JsonResponseBadRequest({"message": _("Error while generating leaderboard report, "
                                                    "please try again later.")})

    return JsonResponse({"message": _("The report is being exported. Note that this operation can take "
                                      "several minutes. When the report will be ready, it will appear "
                                      "in the list of reports ready to download under the cloud icon "
                                      "in the menu bar and you will be able to download it.")})


@login_required
def generate_users_list(request):
    orgs = configuration_helpers.get_current_site_orgs()
    orgs = "+".join(orgs)

    profile_fields = configuration_helpers.get_value(
        'ANALYTICS_USER_PROPERTIES',
        settings.FEATURES.get('ANALYTICS_USER_PROPERTIES', {})
    )
    DEFAULT_ANALYTICS_USER_PROPERTIES = ["gender", "year_of_birth", "lt_area", "lt_sub_area", "lt_custom_country",
                                         "city", "location", "lt_address", "lt_address_2", "lt_phone_number", "lt_gdpr",
                                         "lt_company", "lt_employee_id", "lt_hire_date", "lt_level",
                                         "lt_job_description", "lt_job_code", "lt_department", "lt_supervisor",
                                         "lt_ilt_supervisor", "mailing_address", "lt_learning_group",
                                         "lt_exempt_status", "lt_comments"]
    user_properties_to_exclude = list(set(DEFAULT_ANALYTICS_USER_PROPERTIES) - set(profile_fields.keys()))

    internal_catalog_enabled = configuration_helpers.get_value(
        'COURSES_ARE_BROWSABLE',
        settings.FEATURES.get('COURSES_ARE_BROWSABLE', False)
    )

    learnlight_enabled = configuration_helpers.get_value(
        'ENABLE_LEARNLIGHT_CATALOG',
        settings.FEATURES.get('ENABLE_LEARNLIGHT_CATALOG', False)
    )

    linkedin_enabled = configuration_helpers.get_value(
        'ENABLE_LINKEDIN_CATALOG',
        settings.FEATURES.get('ENABLE_LINKEDIN_CATALOG', False)
    )

    udemy_enabled = configuration_helpers.get_value(
        'ENABLE_UDEMY_CATALOG',
        settings.FEATURES.get('ENABLE_UDEMY_CATALOG', False))

    exclude_fields = user_properties_to_exclude
    if request.user.profile.org not in (LT_DEVELOPER, LT_TESTER):
        exclude_fields.append('org')
    if not internal_catalog_enabled:
        exclude_fields.append('internal_catalog_access')
    if not is_edflex_enabled([]):
        exclude_fields.append('edflex_access')
    if not is_crehana_enabled([]):
        exclude_fields.append('crehana_access')
    if not is_anderspink_enabled([]):
        exclude_fields.append('anderspink_access')
    if not learnlight_enabled:
        exclude_fields.append('learnlight_access')
    if not linkedin_enabled:
        exclude_fields.append('linkedin_access')
    if not udemy_enabled:
        exclude_fields.append('udemy_access')
    if not is_founderz_enabled([]):
        exclude_fields.append('founderz_access')
    if not is_siemens_enabled([]):
        exclude_fields.append('siemens_access')

    try:
        generate_users_list_report_task.apply_async(
            kwargs={
                "user_id": request.user.id,
                "username": request.user.username,
                "file_format": 'csv',
                "orgs": orgs,
                "exclude_columns": tuple(exclude_fields)
            }
        )
    except Exception as e:
        return JsonResponseBadRequest({"message": _("Error while generating leaderboard report, "
                                                    "please try again later.")})

    return JsonResponse({"message": _("The report is being exported. Note that this operation can take "
                                      "several minutes. When the report will be ready, it will appear "
                                      "in the list of reports ready to download under the cloud icon "
                                      "in the menu bar and you will be able to download it.")})
