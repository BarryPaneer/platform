# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import defaultdict
import hashlib
import json
import logging
import multiprocessing
import re
import uuid
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator
from django.db import models, connection, connections
from django.db.models import Sum, Count, Q, Max
from django.http import Http404
from datetime import date, datetime
from django.utils import timezone
from pytz import UTC
from django.utils.translation import ugettext_noop
from django_countries.fields import CountryField
from model_utils.fields import AutoLastModifiedField
from model_utils.models import TimeStampedModel
from requests import ConnectionError
from completion.models import BlockCompletion
from course_blocks.api import get_course_blocks
from courseware.courses import get_course_by_id
from courseware.models import XModuleUserStateSummaryField, StudentModule
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from lms.djangoapps.grades.subsection_grade_factory import SubsectionGradeFactory
import lms.lib.comment_client as cc
from lms.lib.comment_client.utils import CommentClientMaintenanceError, CommentClientRequestError
from opaque_keys.edx.keys import CourseKey, UsageKey
from opaque_keys.edx.django.models import CourseKeyField, UsageKeyField
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.content.course_structures.api.v0.api import course_structure, CourseStructureNotAvailableError
from openedx.core.djangoapps.content.course_structures.tasks import update_course_structure
from openedx.core.djangoapps.models.course_details import CourseDetails
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration
from student.models import CourseEnrollment, UserProfile
from student.roles import LT_SERVICE
from track.backends.django import TrackingLog
from xmodule.modulestore.django import modulestore
from six import text_type
from functools import partial

ANALYTICS_ACCESS_GROUP = "Triboo Analytics Admin"
ANALYTICS_LIMITED_ACCESS_GROUP = "Restricted Triboo Analytics Admin"

ANALYTICS_WORKER_USER = "analytics_worker"

IDLE_TIME = 900 # 15 minutes

logger = logging.getLogger('triboo_analytics')


def create_analytics_worker():
    user = User(username=ANALYTICS_WORKER_USER,
                email="analytics_worker@learning-tribes.com",
                is_active=True,
                is_staff=True)
    user.set_password(uuid.uuid4().hex)
    user.save()

    profile = UserProfile(user=user)
    profile.org = LT_SERVICE
    profile.save()
    return user


def dt2key(date_time=None):
    if not date_time:
        date_time = timezone.now()
    return date_time.strftime('%Y-%m-%d')


def dtload(date_time_str):
    return datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=UTC)


def dtdump(date_time):
    return date_time.strftime('%Y-%m-%d %H:%M:%S.%f')


def get_day_limits(day=None, offset=0):
    day = (day or timezone.now()) + timezone.timedelta(days=offset)
    day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timezone.timedelta(days=1)
    return day_start, day_end


class CourseStatus(object):
    not_started = 0
    in_progress = 1
    finished = 2
    failed = 3
    verbose_names = ['Not Started', 'In Progress', 'Successful', 'Unsuccessful']


def format_time_spent(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return "%02d:%02d:%02d" % (h, m, s)


def format_badges(badges_earned, badges_possible):
    return "{} / {}".format(badges_earned, badges_possible)


def get_badges(report_badges):
    badges = report_badges.split(" / ")
    if len(badges) == 2:
        return int(badges[0]), int(badges[1])
    return 0, 0


def get_combined_org(org_combination):
    combined_org = ""
    for org in org_combination:
        combined_org += "+%s" % org
    return combined_org[1:]


class TrackingLogHelper(object):
    def __init__(self, course_keys):
        self.block_sections_by_course = {}
        self.sections_by_course = {}
        for course_key in course_keys:
            sections, block_sections = self.get_sections(course_key)
            course_id_str = "%s" % course_key
            self.sections_by_course[course_id_str] = sections
            self.block_sections_by_course[course_id_str] = block_sections

    @classmethod
    def get_chapter_url(cls, block_id):
        chapter_url_start = block_id.find("@chapter+block@")
        if chapter_url_start > 0:
            return block_id[chapter_url_start+15:]
        return None

    @classmethod
    def get_section_url(cls, block_id):
        section_url_start = block_id.find("@sequential+block@")
        if section_url_start > 0:
            return block_id[section_url_start+18:]
        return None

    @classmethod
    def get_sections(cls, course_key):
        """
        returns 2 dicts:
        1) a dict giving the combined display name for the combined url of each section
        the combined display name of a section is formatted as "chapter.display_name / section.display_name"
        2) a dict giving the combined url of the parent section for each block id of the course
        the combined url of a section is formatted as "chapter_url/section_url" where:
        - chapter_url is the part of the chapter block id after '@chapter+block@'
        - section_url is the part of the section block id after '@sequential+block@'
        """
        _sections = {}

        section_urls = {}
        parentage = {}
        outline = course_structure(course_key)

        for block_id, block in outline['blocks'].iteritems():
            if block['type'] == "chapter":
                chapter_url = cls.get_chapter_url(block_id)
                for section_id in block['children']:
                    section_url = cls.get_section_url(section_id)
                    combined_section_url = "%s/%s" % (chapter_url, section_url)
                    section_urls[section_id] = combined_section_url
                    _sections[section_id] = {
                        'combined_url': combined_section_url,
                        'chapter_display_name': block['display_name']
                    }
            else:
                if block['type'] != "course" and len(block['children']) > 0:
                    parent_id = block_id
                    parent_type = block['type']
                    for child_id in block['children']:
                        parentage[child_id] = {
                            'parent_id': parent_id,
                            'parent_type': parent_type
                        }

        done = False
        while not done:
            done = True
            for child_id, child in parentage.iteritems():
                if child['parent_type'] != "sequential":
                    done = False
                    parent_id = child['parent_id']
                    child['parent_id'] = parentage[parent_id]['parent_id']
                    child['parent_type'] = parentage[parent_id]['parent_type']

        block_sections = {child_id: section_urls[child['parent_id']] for child_id, child in parentage.iteritems()}

        sections = {}
        for block_id, block in outline['blocks'].iteritems():
            if block_id in _sections.keys():
                combined_url = _sections[block_id]['combined_url']
                combined_display_name = "%s / %s" % (_sections[block_id]['chapter_display_name'],
                                                     block['display_name'])
                sections[combined_url] = combined_display_name

        return sections, block_sections

    @classmethod
    def get_day_tracking_logs(cls, day_start, day_end):
        """
        retrieve the TrackingLog objects with time between [like day_start, day_end[
        and sort these logs by user_id and order them by time
        """
        tracking_logs = TrackingLog.objects.filter(
                            time__gte=day_start, time__lt=day_end).exclude(
                            user_id=None).only('event_type', 'time', 'user_id', 'agent', 'time_spent')
        user_logs = defaultdict(list)
        for l in tracking_logs:
            user_logs[l.user_id].append(l)
        for user_id, logs in user_logs.iteritems():
            user_logs[user_id] = sorted(logs, key=lambda v:v.time)
            first_log_time = user_logs[user_id][0].time
            try:
                user = User.objects.get(id=user_id)
                if not user.last_login or (user.last_login and user.last_login.date() < first_log_time.date()):
                    logger.info("user %d last_login %s should => %s" % (user_id, user.last_login, first_log_time))
                    user.last_login = first_log_time
                    user.save()
            except User.DoesNotExist:
                pass

        return user_logs

    def update_logs(self, day=None):
        day_start, day_end = get_day_limits(day=day)
        user_logs = self.get_day_tracking_logs(day_start, day_end)

        for user_id, logs in user_logs.iteritems():
            if len(logs) >= 2:
                log_pairs = zip(logs[:-1], logs[1:])
                for log1, log2 in log_pairs:
                    total_seconds = (log2.time - log1.time).total_seconds()
                    time_spent = total_seconds if total_seconds < IDLE_TIME else IDLE_TIME
                    self.update_log(log1, time_spent)
                self.update_log(logs[-1], IDLE_TIME)
            elif len(logs) == 1:
                self.update_log(logs[0], IDLE_TIME)

    def update_log(self, tracking_log, time_spent):
        tracking_log.time_spent = time_spent
        section = self.get_parent_section_combined_url(tracking_log.event_type)
        if section:
            tracking_log.section = section
        tracking_log.save()

    def get_parent_section_combined_url(self, event_type):
        section = None
        pieces = event_type.split('/')
        nb_pieces = len(pieces)
        if nb_pieces > 4 and pieces[1] == "courses":
            course_id = pieces[2]
            if course_id in self.block_sections_by_course.keys():
                if pieces[3] == "courseware" and nb_pieces > 5:
                    section = "%s/%s" % (pieces[4], pieces[5])
                elif pieces[3] == "xblock":
                    block_id = "%s" % pieces[4]
                    if block_id in self.block_sections_by_course[course_id].keys():
                        section = self.block_sections_by_course[course_id][block_id]
        return section


def get_day():
    return timezone.now().date()


class AutoCreatedField(models.DateField):
    """
    A DateField that automatically populates itself at
    object creation.

    By default, sets editable=False, default=timezone.now.

    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('editable', False)
        kwargs.setdefault('default', get_day)
        super(AutoCreatedField, self).__init__(*args, **kwargs)


class TimeModel(models.Model):
    """
    An abstract base class model that provides self-updating
    ``created`` and ``modified`` fields.

    """
    created = AutoCreatedField('created')
    modified = AutoLastModifiedField('modified')

    class Meta:
        abstract = True


class ReportMixin(object):
    @classmethod
    def filter_by_day(cls, date_time=None, **kwargs):
        day = date_time.date() if date_time else timezone.now().date()
        return cls.objects.filter(created=day, **kwargs)

    @classmethod
    def get_by_day(cls, date_time=None, **kwargs):
        day = date_time.date() if date_time else timezone.now().date()
        try:
            return cls.objects.get(created=day, **kwargs)
        except cls.DoesNotExist:
            return None


class JsonReportMixin(object):
    @classmethod
    def get_record_str(cls, records_str, key):
        regex = r"\"%s\":\s(\{[^\}]+\})" % key
        m = re.search(regex, records_str)
        if m:
            return m.group(1)
        return None

    @classmethod
    def get_record(cls, records_str, key):
        record_str = cls.get_record_str(records_str, key)
        if record_str:
            return json.loads(record_str)
        return None

    @classmethod
    def recordify(cls, key, record_str):
        return "\"%s\": %s" % (key, record_str)

    @classmethod
    def append_record(cls, records_str, new_key, new_record_str):
        new_record_str = cls.recordify(new_key, new_record_str)
        return "%s, %s}" % (records_str[:-1], new_record_str)


class UnicodeMixin(object):
    def __unicode__(self):
        result = {}
        for k, v in self.__dict__.iteritems():
            if isinstance(v, User):
                result[k] = unicode(v)
            elif k not in ['_state', 'modified']:
                result[k] = v.strftime('%Y-%m-%d %H:%S %Z') if isinstance(v, timezone.datetime) else v
        return unicode(result)


class UniqueVisitorsMixin(object):
    @classmethod
    def _get_unique_visitors_csv_data(cls, unique_visitors):
        unique_visitors_csv_data = {"per_day": "", "per_week": "", "per_month": ""}

        unique_visitors = unique_visitors.values('created', 'unique_visitors').order_by('created')
        if unique_visitors:
            current_week = unique_visitors[0]['created'].strftime('%Y-%W')
            per_week = {current_week: []}
            current_month = unique_visitors[0]['created'].strftime('%Y-%m')
            per_month = {current_month: []}

            for uv in unique_visitors:
                unique_visitors_csv_data['per_day'] += "%s,%d\\n" % (uv['created'].strftime('%Y-%m-%d'), uv['unique_visitors'])
                uv_week = uv['created'].strftime('%Y-%W')
                if uv_week != current_week:
                    current_week = uv_week
                    per_week[current_week] = [uv['unique_visitors']]
                else:
                    per_week[current_week].append(uv['unique_visitors'])

                uv_month = uv['created'].strftime('%Y-%m')
                if uv_month != current_month:
                    current_month = uv_month
                    per_month[current_month] = [uv['unique_visitors']]
                else:
                    per_month[current_month].append(uv['unique_visitors'])

            weeks = per_week.keys()
            weeks.sort()
            for week in weeks:
                visitors = per_week[week]
                avg = int(round(sum(visitors) / float(len(visitors))))
                unique_visitors_csv_data['per_week'] += "%s,%d\\n" % (week, avg)

            months = per_month.keys()
            months.sort()
            for month in months:
                visitors = per_month[month]
                avg = int(round(sum(visitors) / float(len(visitors))))
                unique_visitors_csv_data['per_month'] += "%s,%d\\n" % (month, avg)

        return unique_visitors_csv_data


class ReportLog(UnicodeMixin, TimeStampedModel):
    class Meta(object):
        app_label = "triboo_analytics"
        get_latest_by = "created"

    learner_visit = models.DateTimeField(default=None, null=True)
    learner_course = models.DateTimeField(default=None, null=True)
    learner = models.DateTimeField(default=None, null=True)
    course = models.DateTimeField(default=None, null=True)
    microsite = models.DateTimeField(default=None, null=True)
    country = models.DateTimeField(default=None, null=True)

    @classmethod
    def get_latest(cls, from_date=None, to_date=None):
        filter_kwargs = {
            'learner_visit__isnull': False,
            'learner_course__isnull': False,
            'learner__isnull': False,
            'course__isnull': False,
            'microsite__isnull': False,
            'country__isnull': False
        }
        try:
            if from_date:
                if to_date:
                    filter_kwargs['created__gte'] = from_date
                    filter_kwargs['created__lte'] = to_date
                else:
                    filter_kwargs['created__gte'] = from_date
            elif to_date:
                filter_kwargs['created__lte'] = to_date
            return cls.objects.filter(**filter_kwargs).latest()
        except cls.DoesNotExist:
            return None

    @classmethod
    def update_or_create(cls, **kwargs):
        today_start, today_end = get_day_limits()
        cls.objects.update_or_create(created__gte=today_start,
                                     created__lt=today_end,
                                     defaults=kwargs)


class LearnerVisitsDailyReport(UnicodeMixin, ReportMixin, TimeModel):
    class Meta(object):
        app_label = "triboo_analytics"
        get_latest_by = "created"
        unique_together = ('created', 'user', 'course_id', 'device')
        index_together = ['created', 'user', 'course_id', 'device']

    user = models.ForeignKey(User, null=False)
    course_id = CourseKeyField(max_length=255, null=True)
    org = models.CharField(max_length=255, db_index=True, null=True, default=None)
    device = models.CharField(max_length=255, null=False)
    time_spent = models.PositiveIntegerField(default=0)

    @classmethod
    def generate_day_reports(cls, day=None):
        previous_day_start, previous_day_end = get_day_limits(day=day, offset=-1)
        previous_day_tracking_logs = TrackingLogHelper.get_day_tracking_logs(previous_day_start, previous_day_end)
        for user_id, user_logs in previous_day_tracking_logs.iteritems():
            if User.objects.filter(id=user_id).exists():
                cls.update_or_create(user_id, user_logs, day)

    @classmethod
    def generate_today_reports(cls):
        cls.generate_day_reports()
        ReportLog.update_or_create(learner_visit=timezone.now())

    @classmethod
    def update_or_create(cls, user_id, user_tracking_logs, day=None):
        # group visit by course_id, device, cumulate time_spent
        reports = defaultdict(lambda: 0)
        for l in user_tracking_logs:
            if l.time_spent:
                reports[(l.course_id, l.device)] += l.time_spent

        report_day = day.date() if day else timezone.now().date()
        for (course_id, device), time_spent in reports.iteritems():
            org = course_id.org if course_id != CourseKeyField.Empty else None

            cls.objects.update_or_create(user_id=user_id,
                                         course_id=course_id,
                                         org=org,
                                         device=device,
                                         created=report_day,
                                         defaults={'time_spent': int(time_spent)})

    @classmethod
    def get_active_user_ids(cls, from_date, to_date, course_id=None):
        # logger.info("ANALYTICS -- searching for visitors in [%s, %s[" % (from_date, to_date))
        if course_id:
            reports = cls.objects.filter(created__gte=from_date,
                                         created__lt=to_date,
                                         user__is_active=True,
                                         course_id=course_id)
        else:
            reports = cls.objects.filter(created__gte=from_date, created__lt=to_date, user__is_active=True)
        return reports.values_list('user', flat=True).distinct()


class LearnerCourseDailyReportMockup(object):
    def __init__(self, learner_course_json_report, record):
        self.user = learner_course_json_report.user
        self.course_id = learner_course_json_report.course_id
        self.org = learner_course_json_report.org
        if record:
            self.status = record['status']
            self.progress = record['progress']
            self.badges = record['badges']
            self.current_score = record['current_score']
            self.posts = record['posts']
            self.total_time_spent = record['total_time_spent']
            self.enrollment_date = dtload(record['enrollment_date'])
            self.completion_date = dtload(record['completion_date']) if record['completion_date'] else None
        else:
            self.status = None
            self.progress = None
            self.badges = ""
            self.current_score = None
            self.posts = None
            self.total_time_spent = None
            self.enrollment_date = learner_course_json_report.enrollment_date
            self.completion_date = None


class LearnerCourseJsonReport(JsonReportMixin, TimeStampedModel):
    class Meta(object):
        app_label = "triboo_analytics"
        unique_together = ('user', 'course_id')
        index_together = (['user', 'course_id'], ['org', 'status'])

    user = models.ForeignKey(User, null=False)
    course_id = CourseKeyField(max_length=255, db_index=True, null=False)
    org = models.CharField(max_length=255, db_index=True, null=False)
    status = models.PositiveSmallIntegerField(help_text="not started: 0; in progress: 1; finished: 2; failed: 3; ",
                                              default=0)
    progress = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    badges = models.CharField(max_length=20, default="0 / 0")
    current_score = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    posts = models.PositiveIntegerField(default=0)
    total_time_spent = models.PositiveIntegerField(default=0)
    enrollment_date = models.DateTimeField(default=None, null=True, blank=True)
    completion_date = models.DateTimeField(default=None, null=True, blank=True)
    records = models.TextField(default="{}", null=False, blank=False)
    is_active = models.BooleanField(default=True)

    @classmethod
    def dump_record(cls, record):
        return json.dumps({"status": record['status'],
                           "progress": record['progress'],
                           "badges": record['badges'],
                           "current_score": record['current_score'],
                           "posts": record['posts'],
                           "total_time_spent": record['total_time_spent'],
                           "enrollment_date": dtdump(record['enrollment_date']) if record['enrollment_date'] else None,
                           "completion_date": dtdump(record['completion_date']) if record['completion_date'] else None})

    @classmethod
    def generate_today_reports(cls, last_analytics_success, overviews, sections_by_course, multi_process=False):
        analytics_worker = User.objects.get(username=ANALYTICS_WORKER_USER)

        nb_processes = 2 * multiprocessing.cpu_count() if multi_process else 1

        nb_courses = len(overviews)
        i = 0
        for overview in overviews:
            i += 1
            course_id = overview.id
            course_last_update = overview.modified.date()
            course_id_str = "%s" % course_id
            course = modulestore().get_course(course_id)
            if not course:
                logger.error("course_id=%s returned Http404" % course_id)
                continue
            Badge.refresh(course_id, course, analytics_worker)

            sections = sections_by_course[course_id_str]

            enrollments = CourseEnrollment.objects.filter(is_active=True,
                                                          course_id=course_id,
                                                          user__is_active=True)
            nb_enrollments = len(enrollments)

            logger.info("learner course report for course_id=%s (%d / %d): %d enrollments" % (
                course_id, i, nb_courses, nb_enrollments))

            if (not multi_process
                and (nb_enrollments > 10000)
                and (not last_analytics_success or (course_last_update >= last_analytics_success.date()))):
                multi_process = True
                logger.info("force multiprocessing")

            if multi_process:
                enrollment_ids = [e_id for e_id in enrollments.values_list('id', flat=True)]

                enrollments_by_process = []
                for j in range(0, nb_processes):
                    enrollments_by_process.append([])

                j = 0
                for enrollment_id in enrollment_ids:
                    enrollments_by_process[j].append(enrollment_id)
                    j += 1
                    if j == nb_processes:
                        j = 0

                connections.close_all()
                processes = []
                for process_enrollments in enrollments_by_process:
                    process = multiprocessing.Process(target=cls.process_generate_today_reports,
                                                      args=(last_analytics_success, course_last_update, process_enrollments, course, sections,))
                    process.start()
                    processes.append(process)
                [process.join() for process in processes]

            else:
                enrollments = enrollments.prefetch_related('user')
                for enrollment in enrollments:
                    cls.generate_enrollment_report(last_analytics_success, course_last_update, enrollment, course, sections)


    @classmethod
    def process_generate_today_reports(cls, last_analytics_success, course_last_update, enrollment_ids, course, sections):
        for enrollment_id in enrollment_ids:
            enrollment = CourseEnrollment.objects.get(id=enrollment_id)
            cls.generate_enrollment_report(last_analytics_success, course_last_update, enrollment, course, sections)

    @classmethod
    def generate_enrollment_report(cls, last_analytics_success, course_last_update, enrollment, course, sections):
        key_last_analytics_success = dt2key(last_analytics_success) if last_analytics_success else None
        updated = cls.update_or_create(key_last_analytics_success, course_last_update, enrollment, course)
        LearnerSectionJsonReport.update_or_create(key_last_analytics_success, enrollment, sections, updated)

    @classmethod
    def update_or_create(cls, key_last_analytics_success, course_last_update, enrollment, course):
        course_key = enrollment.course_id
        user = enrollment.user

        if user.is_active:
            report_needs_update = True
            report = None
            try:
                report = cls.objects.get(course_id=course_key, user_id=user.id)
            except cls.DoesNotExist:
                pass
            if key_last_analytics_success and report:
                report_last_modified = report.modified.date()
                last_analytics_success_record = cls.get_record_str(report.records, key_last_analytics_success)
                if (last_analytics_success_record
                    and (not enrollment.gradebook_edit or enrollment.gradebook_edit.date() < report_last_modified)
                    and (not user.last_login or user.last_login.date() < report_last_modified)
                    and course_last_update < report_last_modified
                    and enrollment.completed == report.completion_date):
                    # logger.info("ANALYTICS -- LC report user_id=%d / gradebook=%s / login=%s / "\
                    #     "course update=%s / completion=%s => NO UPDATE NEEDED" % (
                    #     user.id,
                    #     (not enrollment.gradebook_edit or enrollment.gradebook_edit.date() < report_last_modified),
                    #     (not user.last_login or user.last_login.date() < report_last_modified),
                    #     (course_last_update < report_last_modified),
                    #     (enrollment.completed == report.completion_date)))
                    report_needs_update = False
                    report.records = cls.append_record(report.records, dt2key(), last_analytics_success_record)
                    report.is_active = True
                    report.save()

            badge_report_needs_update = True
            trophies_by_chapter = None
            if report_needs_update:
                # logger.info("ANALYTICS -- LC report user_id=%d NEEDS UPDATE" % user.id)
                with modulestore().bulk_operations(course_key):
                    total_time_spent = (LearnerVisitsDailyReport.objects.filter(
                        user=user, course_id=course_key, created__gte=enrollment.created).aggregate(
                        Sum('time_spent')).get('time_spent__sum') or 0)

                    grade_factory = CourseGradeFactory()
                    progress = grade_factory.get_progress(user, course)
                    if progress:
                        progress['progress'] *= 100.0
                        if enrollment.completed:
                            status = CourseStatus.failed

                            if progress['nb_trophies_possible'] == 0 or progress['is_course_passed']:
                                status = CourseStatus.finished

                        else:
                            # by gradebook edit a user could have a progress > 0 while total_time_spent = 0
                            if total_time_spent > 0 or progress['progress'] > 0:
                                status = CourseStatus.in_progress
                            else:
                                status = CourseStatus.not_started

                        posts = 0
                        try:
                            cc_user = cc.User(id=user.id, course_id=course_key).to_dict()
                            posts = cc_user.get('comments_count', 0) + cc_user.get('threads_count', 0)
                        except (cc.CommentClient500Error, cc.CommentClientRequestError, ConnectionError):
                            pass

                        new_record = {"status": status,
                                      "progress": progress['progress'],
                                      "badges": format_badges(progress['nb_trophies_earned'],
                                                              progress['nb_trophies_possible']),
                                      "current_score": progress['current_score'],
                                      "posts": posts,
                                      "total_time_spent": total_time_spent,
                                      "enrollment_date": enrollment.created,
                                      "completion_date": enrollment.completed}

                        trophies_by_chapter = progress['trophies_by_chapter']

                    else:
                        # logger.warning('ANALYTICS -- course=%s user_id=%d does not have progress info => empty report.' % (
                        #     course_key, user.id))
                        new_record = {"status": CourseStatus.not_started,
                                      "progress": 0,
                                      "badges": 0,
                                      "current_score": 0,
                                      "posts": 0,
                                      "total_time_spent": total_time_spent,
                                      "enrollment_date": enrollment.created,
                                      "completion_date": None}
                        badge_report_needs_update = False

                    new_record_str = cls.dump_record(new_record)
                    if report:
                        # logger.info("ANALYTICS -- LC report user_id=%d SIMPLY ADD RECORD" % user.id)
                        report.status = new_record['status']
                        report.progress = new_record['progress']
                        report.badges = new_record['badges']
                        report.current_score = new_record['current_score']
                        report.posts = new_record['posts']
                        report.total_time_spent = new_record['total_time_spent']
                        report.enrollment_date = new_record['enrollment_date']
                        report.completion_date = new_record['completion_date']
                        report.records = cls.append_record(report.records, dt2key(), new_record_str)
                        report.is_active = True
                        report.save()

                    else:
                        # logger.info("ANALYTICS -- LC report user_id=%d CREATE NEW REPORT" % user.id)
                        cls.objects.update_or_create(user=user,
                                                     course_id=course_key,
                                                     defaults={'org': course_key.org,
                                                               'status': new_record['status'],
                                                               'progress': new_record['progress'],
                                                               'badges': new_record['badges'],
                                                               'current_score': new_record['current_score'],
                                                               'posts': new_record['posts'],
                                                               'total_time_spent': new_record['total_time_spent'],
                                                               'enrollment_date': new_record['enrollment_date'],
                                                               'completion_date': new_record['completion_date'],
                                                               'records': "{%s}" % cls.recordify(dt2key(), new_record_str)})

            if badge_report_needs_update:
                LearnerBadgeJsonReport.update_or_create(key_last_analytics_success,
                                                        course_key,
                                                        course,
                                                        user,
                                                        trophies_by_chapter,
                                                        report_needs_update)
            return report_needs_update
        return False

    @classmethod
    def filter_by_period(cls, to_date=None, from_date=None, **kwargs):
        logger.info("ANALYTICS -- LearnerCourseJsonReport filter_by_period from=%s to=%s kwargs=%s" % (
            from_date, to_date, kwargs))
        if from_date:
            _to_date = to_date
            if not _to_date:
                _to_date = timezone.now().date()
            user_ids = LearnerVisitsDailyReport.get_active_user_ids(from_date, _to_date)
            kwargs['user_id__in'] = user_ids
            logger.info("ANALYTICS -- LearnerCourseJsonReport filter_by_period from=%s to=%s nb user_ids=%d" % (
                from_date, to_date, len(user_ids)))
        return cls.filter_by_day(to_date, **kwargs)

    @classmethod
    def filter_by_day(cls, to_date=None, **kwargs):
        if to_date:
            reports = cls.objects.filter(is_active=True, **kwargs).select_related('user__profile')
            day_key = dt2key(to_date)
            results = []
            for r in reports:
                record = cls.get_record(r.records, day_key)
                results.append(LearnerCourseDailyReportMockup(r, record))
            return results
        else:
            reports = cls.objects.filter(is_active=True, **kwargs).defer('records').select_related('user__profile')
        return reports

    @classmethod
    def get_by_day(cls, to_date=None, **kwargs):
        try:
            r = cls.objects.get(is_active=True, **kwargs)
            if to_date:
                day_key = dt2key(to_date)
                record = cls.get_record(r.records, day_key)
                return LearnerCourseDailyReportMockup(r, record)
            return r
        except cls.DoesNotExist:
            return None


class LearnerCourseDailyReport(UnicodeMixin, ReportMixin, TimeModel):
    class Meta(object):
        app_label = "triboo_analytics"
        get_latest_by = "created"
        unique_together = ('created', 'user', 'course_id')
        index_together = (['created', 'user', 'course_id'],
                          ['created', 'course_id'])

    user = models.ForeignKey(User, null=False)
    course_id = CourseKeyField(max_length=255, db_index=True, null=False)
    org = models.CharField(max_length=255, db_index=True, null=False)
    status = models.PositiveSmallIntegerField(help_text="not started: 0; in progress: 1; finished: 2; failed: 3; ",
                                              default=0)
    progress = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    badges = models.CharField(max_length=20, default="0 / 0")
    current_score = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    posts = models.PositiveIntegerField(default=0)
    total_time_spent = models.PositiveIntegerField(default=0)
    enrollment_date = models.DateTimeField(default=None, null=True, blank=True)
    completion_date = models.DateTimeField(default=None, null=True, blank=True)

    @classmethod
    def generate_today_reports(cls, last_analytics_success, overviews, sections_by_course, multi_process=False):
        nb_processes = 2 * multiprocessing.cpu_count() if multi_process else 1

        nb_courses = len(overviews)
        i = 0
        for overview in overviews:
            i += 1
            course_id = overview.id
            course_last_update = overview.modified.date()
            course_id_str = "%s" % course_id
            sections = sections_by_course[course_id_str]
            enrollments = CourseEnrollment.objects.filter(is_active=True,
                                                          course_id=course_id,
                                                          user__is_active=True)
            nb_enrollments = len(enrollments)

            logger.info("learner course report for course_id=%s (%d / %d): %d enrollments" % (
                course_id, i, nb_courses, nb_enrollments))

            if (not multi_process
                    and (nb_enrollments > 10000)
                    and (not last_analytics_success or (course_last_update >= last_analytics_success))):
                multi_process = True
                logger.info("force multiprocessing")

            if multi_process:
                enrollment_ids = [e_id for e_id in enrollments.values_list('id', flat=True)]

                enrollments_by_process = []
                for j in range(0, nb_processes):
                    enrollments_by_process.append([])

                j = 0
                for enrollment_id in enrollment_ids:
                    enrollments_by_process[j].append(enrollment_id)
                    j += 1
                    if j == nb_processes:
                        j = 0

                connections.close_all()
                processes = []
                for process_enrollments in enrollments_by_process:
                    process = multiprocessing.Process(target=cls.process_generate_today_reports,
                                                      args=(last_analytics_success, course_last_update, process_enrollments, sections,))
                    process.start()
                    processes.append(process)
                [process.join() for process in processes]

            else:
                enrollments = enrollments.prefetch_related('user')
                for enrollment in enrollments:
                    cls.generate_enrollment_report(last_analytics_success, course_last_update, enrollment, sections)

        ReportLog.update_or_create(learner_course=timezone.now())

    @classmethod
    def process_generate_today_reports(cls, last_analytics_success, course_last_update, enrollment_ids, sections):
        # logger.info("process %d enrollments" % len(enrollment_ids))
        for enrollment_id in enrollment_ids:
            enrollment = CourseEnrollment.objects.get(id=enrollment_id)
            cls.generate_enrollment_report(last_analytics_success, course_last_update, enrollment, sections)

    @classmethod
    def generate_enrollment_report(cls, last_analytics_success, course_last_update, enrollment, sections):
        updated = cls.update_or_create(last_analytics_success, course_last_update, enrollment)
        if updated:
            LearnerSectionReport.update_or_create(enrollment, sections)

    @classmethod
    def update_or_create(cls, last_analytics_success, course_last_update, enrollment):
        course_key = enrollment.course_id
        user = enrollment.user
        day = timezone.now().date()

        report_needs_update = True
        if user.is_active:
            if last_analytics_success:
                try:
                    last_report = cls.objects.get(course_id=course_key, user_id=user.id, created=last_analytics_success)
                    if ((not enrollment.gradebook_edit or enrollment.gradebook_edit.date() < last_report.created)
                            and (not user.last_login or user.last_login.date() < last_report.created)
                            and course_last_update < last_report.created
                            and enrollment.completed == last_report.completion_date):
                        report_needs_update = False
                        cls.objects.update_or_create(created=day,
                                                     user=user,
                                                     course_id=course_key,
                                                     defaults={'org': course_key.org,
                                                               'total_time_spent': last_report.total_time_spent,
                                                               'status': last_report.status,
                                                               'progress': last_report.progress,
                                                               'badges': last_report.badges,
                                                               'current_score': last_report.current_score,
                                                               'posts': last_report.posts,
                                                               'enrollment_date': enrollment.created,
                                                               'completion_date': enrollment.completed})
                except cls.DoesNotExist:
                    pass

            if report_needs_update:
                with modulestore().bulk_operations(course_key):
                    try:
                        course = get_course_by_id(course_key)
                    except Http404:
                        logger.error("course_id=%s returned Http404" % course_key)
                        return

                    total_time_spent = (LearnerVisitsDailyReport.objects.filter(
                        user=user, course_id=course_key, created__gte=enrollment.created).aggregate(
                        Sum('time_spent')).get('time_spent__sum') or 0)

                    grade_factory = CourseGradeFactory()
                    # grade_factory.update_course_completion_percentage(course_key, user)
                    progress = grade_factory.get_progress(user, course)
                    if not progress:
                        logger.warning('course=%s user_id=%d does not have progress info => empty report.' % (
                            course_key, user.id))
                        cls.objects.update_or_create(
                            created=day,
                            user=user,
                            course_id=course_key,
                            defaults={'org': course_key.org,
                                      'status': CourseStatus.not_started,
                                      'progress': 0,
                                      'badges': 0,
                                      'current_score': 0,
                                      'posts': 0,
                                      'total_time_spent': 0,
                                      'enrollment_date': enrollment.created,
                                      'completion_date': None})
                        return

                    progress['progress'] *= 100.0
                    if enrollment.completed:
                        status = CourseStatus.failed

                        if progress['nb_trophies_possible'] == 0 or progress['is_course_passed']:
                            status = CourseStatus.finished

                    else:
                        # by gradebook edit a user could have a progress > 0 while total_time_spent = 0
                        if total_time_spent > 0 or progress['progress'] > 0:
                            status = CourseStatus.in_progress
                        else:
                            status = CourseStatus.not_started

                    posts = 0
                    try:
                        cc_user = cc.User(id=user.id, course_id=course_key).to_dict()
                        posts = cc_user.get('comments_count', 0) + cc_user.get('threads_count', 0)
                    except (cc.CommentClient500Error, cc.CommentClientRequestError, ConnectionError):
                        pass

                    cls.objects.update_or_create(
                        created=day,
                        user=user,
                        course_id=course_key,
                        defaults={'org': course_key.org,
                                  'total_time_spent': total_time_spent,
                                  'status': status,
                                  'progress': progress['progress'],
                                  'badges': format_badges(progress['nb_trophies_earned'],
                                                          progress['nb_trophies_possible']),
                                  'current_score': progress['current_score'],
                                  'posts': posts,
                                  'enrollment_date': enrollment.created,
                                  'completion_date': enrollment.completed})
            return report_needs_update
        return False


def time_spent_worker(dataset, sections, queryset, chunk_size, course_id, from_date_key, to_date_key, offset):
    subset = queryset[offset: offset+chunk_size]
    connections.close_all()
    logger.info("offset: {} beginning".format(offset))
    LearnerSectionJsonReport.rearrange_dataset(dataset, sections, subset, course_id, from_date_key, to_date_key)
    logger.info("offset: {} finished".format(offset))


def dataset_multiprocessing(queryset, course_id, from_date_key=None, to_date_key=None, chunk_size=1000):
    logger.info("Start dataset multiprocessing rearrangement #####")
    start = timezone.now()
    manager = multiprocessing.Manager()
    dataset = manager.dict()
    sections = manager.dict()
    nb_of_processes = min(multiprocessing.cpu_count(), 10)
    pool = multiprocessing.Pool(nb_of_processes)
    nb_records = queryset.count()

    connections.close_all()
    func = partial(time_spent_worker, dataset, sections, queryset, chunk_size, course_id, from_date_key, to_date_key)
    pool.map(func, range(0, nb_records, chunk_size))
    pool.close()
    pool.join()
    duration = (timezone.now() - start).total_seconds()
    logger.info("Dataset rearrangement finished in {} minutes {} seconds ####".format(
        int(duration / 60), int(duration % 60)))
    return dataset, sections


class LearnerSectionJsonReport(JsonReportMixin, TimeStampedModel):
    class Meta(object):
        app_label = "triboo_analytics"
        unique_together = ('user', 'course_id', 'section_key')
        index_together = (['user', 'course_id', 'section_key'], ['course_id', 'user'])

    user = models.ForeignKey(User, null=False)
    course_id = CourseKeyField(max_length=255, db_index=True, null=False)
    section_key = models.CharField(max_length=100, null=False)
    section_name = models.CharField(max_length=512, null=False)
    total_time_spent = models.PositiveIntegerField(default=0)
    records = models.TextField(default="{}", null=False, blank=False)
    is_active = models.BooleanField(default=True)

    @classmethod
    def update_or_create(cls, key_last_analytics_success, enrollment, sections, needs_update):
        for section_combined_url, section_combined_display_name in sections.iteritems():
            report = None
            try:
                report = cls.objects.get(user=enrollment.user,
                                         course_id=enrollment.course_id,
                                         section_key=section_combined_url)
            except cls.DoesNotExist:
                pass

            last_analytics_success_record = None
            if key_last_analytics_success and report:
                last_analytics_success_record = cls.get_record_str(report.records, key_last_analytics_success)
            if report and last_analytics_success_record and not needs_update:
                # logger.info("ANALYTICS -- Section report user_id=%d / section=%s NO UPDATE NEEDED" % (
                #         enrollment.user.id, section_combined_url))
                report.records = cls.append_record(report.records, dt2key(), last_analytics_success_record)
                report.is_active = True
                report.save()
            else:
                total_time_spent = (TrackingLog.objects.filter(user_id=enrollment.user.id,
                                                           section=section_combined_url,
                                                           time__gte=enrollment.created).aggregate(
                                                               Sum('time_spent')).get('time_spent__sum') or 0)
                total_time_spent = int(round(total_time_spent))
                new_record = {"total_time_spent": total_time_spent}
                new_record_str = json.dumps(new_record)
                if report:
                    # logger.info("ANALYTICS -- Section report user_id=%d / section=%s SIMPLY ADD RECORD" % (
                    #         enrollment.user.id, section_combined_url))
                    report.section_name = section_combined_display_name
                    report.total_time_spent = new_record['total_time_spent']
                    report.records = cls.append_record(report.records, dt2key(), new_record_str)
                    report.is_active = True
                    report.save()
                else:
                    # logger.info("ANALYTICS -- Section report user_id=%d / section=%s CREATE NEW REPORT" % (
                    #         enrollment.user.id, section_combined_url))
                    cls.objects.update_or_create(user=enrollment.user,
                                                 course_id=enrollment.course_id,
                                                 section_key=section_combined_url,
                                                 defaults={'section_name': section_combined_display_name.encode('utf-8'),
                                                           'total_time_spent': new_record['total_time_spent'],
                                                           'records': "{%s}" % cls.recordify(dt2key(), new_record_str)})

    @classmethod
    def rearrange_dataset(cls, dataset, sections, enrollments, course_id, from_date_key=None, to_date_key=None):
        if from_date_key:
            for enrollment in enrollments:
                user = enrollment.user
                user_id = enrollment.user_id
                reports = LearnerSectionJsonReport.objects.filter(course_id=course_id, user=user).only(
                    "section_key", "section_name", "total_time_spent", "records")
                dataset[user_id] = {'user': user}
                for res in reports.iterator():
                    old_time_spent = 0
                    from_record = LearnerSectionJsonReport.get_record(res.records, from_date_key)
                    if from_record:
                        old_time_spent = from_record['total_time_spent']
                    new_time_spent = res.total_time_spent
                    if to_date_key:
                        to_record = LearnerSectionJsonReport.get_record(res.records, to_date_key)
                        if to_record:
                            new_time_spent = to_record['total_time_spent']
                        else:
                            new_time_spent = 0
                    if new_time_spent >= old_time_spent:
                        total_time_spent = new_time_spent - old_time_spent
                    else:
                        logger.error("invalid values for user_id %d / section %s: from %s = %d, to %s = %d" % (
                            user_id, res.section_key, from_date_key, old_time_spent,
                            to_date_key, new_time_spent))
                        continue
                    # we have to append data to the dict by this way, to make it compatible with multiprocessing
                    # manager.dict
                    temp_dict = dataset[user_id]
                    temp_dict[res.section_key] = total_time_spent
                    dataset[user_id] = temp_dict
                    sections[res.section_key] = res.section_name
        else:
            for enrollment in enrollments:
                user = enrollment.user
                user_id = enrollment.user_id
                reports = LearnerSectionJsonReport.objects.filter(course_id=course_id, user=user).only(
                    "section_key", "section_name", "total_time_spent")
                dataset[user_id] = {'user': user}
                for res in reports.iterator():
                    temp_dict = dataset[user_id]
                    temp_dict[res.section_key] = res.total_time_spent
                    dataset[user_id] = temp_dict
                    sections[res.section_key] = res.section_name

    @classmethod
    def filter_by_period(cls, course_id, to_date=None, from_date=None, multiprocessing_mode=False, **kwargs):
        logger.info("ANALYTICS -- LearnerSectionJsonReport filter_by_period course_id=%s from=%s to=%s kwargs=%s" % (
            course_id, from_date, to_date, kwargs))
        enrollments = CourseEnrollment.objects.filter(
            course_id=course_id, is_active=True, user__is_active=True, **kwargs
        ).only('user').select_related('user__profile')

        logger.info("Start LearnerSectionJsonReport data rearrangement")
        if from_date:
            _to_date = to_date
            if not _to_date:
                _to_date = timezone.now().date()
            user_ids = LearnerVisitsDailyReport.get_active_user_ids(from_date, _to_date)
            logger.info("ANALYTICS -- LearnerSectionJsonReport filter_by_period from=%s to=%s nb user_ids=%d" % (
                from_date, _to_date, len(user_ids)))
            enrollments = enrollments.filter(user_id__in=user_ids)
        from_date_key = dt2key(from_date) if from_date else None
        to_date_key = dt2key(to_date) if to_date else None

        if multiprocessing_mode:
            nb_of_processes = min(multiprocessing.cpu_count(), 10)
            chunk_size = enrollments.count() / nb_of_processes or enrollments.count()
            dataset, sections = dataset_multiprocessing(enrollments, course_id,
                                                        from_date_key=from_date_key,
                                                        to_date_key=to_date_key,
                                                        chunk_size=chunk_size)
            dataset = dict(dataset)
            sections = dict(sections)
        else:
            dataset = {}
            sections = {}
            cls.rearrange_dataset(dataset, sections, enrollments, course_id, from_date_key, to_date_key)
        nb_results = len(dataset) * len(sections)

        logger.info("ANALYTICS -- LearnerSectionJsonReport nb results = %d" % nb_results)
        logger.info("ANALYTICS -- LearnerSectionJsonReport dataset is ready")

        return dataset.values(), sections


class LearnerSectionReport(TimeModel):
    class Meta(object):
        app_label = "triboo_analytics"
        unique_together = ('user', 'course_id', 'section_key')

    user = models.ForeignKey(User, null=False)
    course_id = CourseKeyField(max_length=255, db_index=True, null=False)
    section_key = models.CharField(max_length=100, null=False)
    section_name = models.CharField(max_length=512, null=False)
    time_spent = models.PositiveIntegerField(default=0)

    @classmethod
    def update_or_create(cls, enrollment, sections):
        for section_combined_url, section_combined_display_name in sections.iteritems():
            time_spent = (TrackingLog.objects.filter(
                user_id=enrollment.user.id,
                section=section_combined_url,
                time__gte=enrollment.created).aggregate(
                Sum('time_spent')).get('time_spent__sum') or 0)
            time_spent = int(round(time_spent))
            cls.objects.update_or_create(user=enrollment.user,
                                         course_id=enrollment.course_id,
                                         section_key=section_combined_url,
                                         defaults={'section_name': section_combined_display_name,
                                                   'time_spent': time_spent})


class Badge(models.Model):
    class Meta(object):
        app_label = "triboo_analytics"
        unique_together = ['course_id', 'badge_hash']
        index_together = ['course_id', 'badge_hash']

    course_id = CourseKeyField(max_length=255, db_index=True, null=False)
    badge_hash = models.CharField(max_length=100, db_index=True, null=False)
    order = models.PositiveSmallIntegerField(default=0)
    grading_rule = models.CharField(max_length=255, null=False, blank=False)
    section_name = models.CharField(max_length=255, null=False, blank=False)
    threshold = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])

    @classmethod
    def get_badge_hash(cls, grading_rule, chapter_url, section_url):
        m = hashlib.md5()
        badge = ("%s-%s-%s" % (grading_rule.encode('utf-8').decode('utf-8'), chapter_url, section_url)).encode('utf-8')
        m.update(badge)
        return m.hexdigest()

    @classmethod
    def refresh(cls, course_key, course, analytics_worker):
        hashes = []

        progress = CourseGradeFactory().get_progress(analytics_worker, course)
        i = 0
        for chapter in progress['trophies_by_chapter']:
            for trophy in chapter['trophies']:
                i += 1
                badge_hash = cls.get_badge_hash(trophy['section_format'],
                                                chapter['url'],
                                                trophy['section_url'])
                hashes.append(badge_hash)
                cls.objects.update_or_create(course_id=course_key,
                                             badge_hash=badge_hash,
                                             defaults={'order': i,
                                                       'grading_rule': trophy['section_format'],
                                                       'section_name': trophy['section_name'],
                                                       'threshold': (trophy['threshold'] * 100)})

        course_badges = cls.objects.filter(course_id=course_key).exclude(badge_hash__in=hashes).delete()


class LearnerBadgeDailyReportMockup(object):
    def __init__(self, learner_badge_json_report, key_day):
        self.user = learner_badge_json_report.user
        self.badge = learner_badge_json_report.badge
        if key_day:
            records = json.loads(learner_badge_json_report.records)
            if key_day in records.keys():
                self.score = records[key_day]['score']
                self.success = records[key_day]['success']
                self.success_date = dtload(records[key_day]['success_date']) if \
                    records[key_day]['success_date'] else None
            else:
                self.score = None
                self.success = None
                self.success_date = None
        else:
            self.score = learner_badge_json_report.score
            self.success = learner_badge_json_report.success
            self.success_date = learner_badge_json_report.success_date


class LearnerBadgeJsonReport(JsonReportMixin, TimeStampedModel):
    class Meta(object):
        app_label = "triboo_analytics"
        unique_together = ['user', 'badge']
        index_together = ['user', 'badge']

    user = models.ForeignKey(User, null=False, on_delete=models.CASCADE)
    badge = models.ForeignKey(Badge, null=False, on_delete=models.CASCADE)
    score = models.FloatField(default=0, null=True, blank=True)
    success = models.BooleanField(default=False)
    success_date = models.DateTimeField(default=None, null=True, blank=True)
    records = models.TextField(default="{}", null=False, blank=False)
    is_active = models.BooleanField(default=True)

    @classmethod
    def dump_record(cls, record):
        return json.dumps({"score": record['score'],
                           "success": record['success'],
                           "success_date": dtdump(record['success_date']) if record['success_date'] else None})

    @classmethod
    def update_or_create(cls, key_last_analytics_success, course_key, course, user, trophies_by_chapter, needs_update):
        if not trophies_by_chapter:
            progress = CourseGradeFactory().get_progress(user, course)
            trophies_by_chapter = progress['trophies_by_chapter']

        _successes = LearnerBadgeSuccess.objects.filter(badge__course_id=course_key, user=user)
        successes = {s.badge.badge_hash: s.success_date for s in _successes}
        i = 0
        for chapter in trophies_by_chapter:
            for trophy in chapter['trophies']:
                i += 1
                badge_hash = Badge.get_badge_hash(trophy['section_format'],
                                                  chapter['url'],
                                                  trophy['section_url'])
                try:
                    badge = Badge.objects.get(course_id=course_key, badge_hash=badge_hash)
                    # logger.info("ANALYTICS -- found Badge course=%s - progress trophy %s (%s %s)" % (
                    #     course_key, badge_hash, chapter['chapter_name'], trophy['section_name']))

                except Badge.DoesNotExist:
                    badge, _ = Badge.objects.update_or_create(course_id=course_key,
                                                              badge_hash=badge_hash,
                                                              defaults={'order': i,
                                                                        'grading_rule': trophy['section_format'],
                                                                        'section_name': trophy['section_name'],
                                                                        'threshold': (trophy['threshold'] * 100)})
                    # logger.info("ANALYTICS -- create Badge course=%s - progress trophy %s (%s %s)" % (
                    #     course_key, badge_hash, chapter['chapter_name'], trophy['section_name']))

                report = None
                records = {}
                try:
                    report = cls.objects.get(user=user, badge=badge)
                except cls.DoesNotExist:
                    pass

                last_analytics_success_record = None
                if key_last_analytics_success and report:
                    last_analytics_success_record = cls.get_record_str(report.records, key_last_analytics_success)

                if report and last_analytics_success_record and not needs_update:
                    # logger.info("ANALYTICS -- Badge report user_id=%d / badge=%s NO UPDATE NEEDED" % (
                    #     user.id, badge))
                    report.records = cls.append_record(report.records, dt2key(), last_analytics_success_record)
                    report.is_active = True
                    report.save()

                else:
                    score = trophy['result'] * 100
                    success = True if score >= badge.threshold else False
                    success_date = successes[badge_hash] if badge_hash in successes.keys() else None
                    new_record = {"score": score,
                                  "success": success,
                                  "success_date": success_date}
                    new_record_str = cls.dump_record(new_record)
                    if report:
                        # logger.info("ANALYTICS -- Badge report user_id=%d / badge=%s SIMPLY ADD RECORD" % (
                        #     user.id, badge))
                        report.score = new_record['score']
                        report.success = new_record['success']
                        report.success_date = new_record['success_date']
                        report.records = cls.append_record(report.records, dt2key(), new_record_str)
                        report.is_active = True
                        report.save()
                    else:
                        # logger.info("ANALYTICS -- Badge report user_id=%d / badge=%s CREATE NEW REPORT" % (
                        #     user.id, badge))
                        cls.objects.update_or_create(user=user,
                                                     badge=badge,
                                                     defaults={'score': score,
                                                               'success': success,
                                                               'success_date': success_date,
                                                               'records': "{%s}" % cls.recordify(dt2key(),
                                                                                                 new_record_str)})

    @classmethod
    def filter_by_day(cls, date_time=None, **kwargs):
        day_key = dt2key(date_time) if date_time else None
        reports = cls.objects.filter(is_active=True, **kwargs).select_related('user__profile')
        if not day_key:
            reports = reports.defer('records')
        results = []
        for r in reports:
            results.append(LearnerBadgeDailyReportMockup(r, day_key))
        return results

    @classmethod
    def get_by_day(cls, date_time=None, **kwargs):
        key_day = dt2key(date_time) if date_time else None
        try:
            if key_day:
                r = cls.objects.select_related('user__profile').get(is_active=True, **kwargs)
            else:
                r = cls.objects.defer('records').select_related('user__profile').get(is_active=True, **kwargs)
            return LearnerBadgeDailyReportMockup(r, key_day)
        except cls.DoesNotExist:
            return None

    @classmethod
    def filter_by_period(cls, to_date=None, from_date=None, **kwargs):
        logger.info("ANALYTICS -- LearnerBadgeJsonReport filter_by_period from=%s to=%s kwargs=%s" % (
            from_date, to_date, kwargs))
        if from_date:
            _to_date = to_date
            if not _to_date:
                _to_date = timezone.now().date()
            user_ids = LearnerVisitsDailyReport.get_active_user_ids(from_date, _to_date)
            kwargs['user_id__in'] = user_ids

            logger.info("ANALYTICS -- LearnerBadgeJsonReport filter_by_period from=%s to=%s nb user_ids=%d" % (
                from_date, to_date, len(user_ids)))

        results = cls.filter_by_day(to_date, **kwargs)
        dataset = {}
        for res in results:
            key = res.user.id
            if key not in dataset.keys():
                dataset[key] = {'user': res.user}
            dataset[key]["%s_success" % res.badge.badge_hash] = res.success
            dataset[key]["%s_score" % res.badge.badge_hash] = res.score
            dataset[key]["%s_successdate" % res.badge.badge_hash] = res.success_date

        logger.info("ANALYTICS -- => nb results=%d" % len(dataset.values()))
        return dataset.values()


class LearnerBadgeSuccess(models.Model):
    class Meta(object):
        app_label = "triboo_analytics"
        unique_together = ['user', 'badge']
        index_together = ['user', 'badge']

    user = models.ForeignKey(User, null=False, on_delete=models.CASCADE)
    badge = models.ForeignKey(Badge, null=False, on_delete=models.CASCADE)
    success_date = models.DateTimeField(default=None, null=True, blank=True)


class LearnerDailyReportMockup(object):
    def __init__(self, learner_daily_report, total_time_spent):
        self.org = learner_daily_report.org
        self.user = learner_daily_report.user
        self.enrollments = learner_daily_report.enrollments
        self.average_final_score = learner_daily_report.average_final_score
        self.badges = learner_daily_report.badges
        self.posts = learner_daily_report.posts
        self.finished = learner_daily_report.finished
        self.failed = learner_daily_report.failed
        self.not_started = learner_daily_report.not_started
        self.in_progress = learner_daily_report.in_progress
        self.total_time_spent = total_time_spent


class LearnerDailyReport(UnicodeMixin, ReportMixin, TimeModel):
    class Meta(object):
        app_label = "triboo_analytics"
        get_latest_by = "created"
        unique_together = ('created', 'user', 'org')
        index_together = ['created', 'user', 'org']

    user = models.ForeignKey(User, null=False)
    org = models.CharField(max_length=255, db_index=True, null=False)
    enrollments = models.PositiveIntegerField(default=0)
    average_final_score = models.PositiveSmallIntegerField(default=0)
    badges = models.CharField(max_length=20, default="0 / 0")
    posts = models.PositiveIntegerField(default=0)
    finished = models.PositiveSmallIntegerField(default=0, verbose_name=CourseStatus.verbose_names[CourseStatus.finished])
    failed = models.PositiveSmallIntegerField(default=0, verbose_name=CourseStatus.verbose_names[CourseStatus.failed])
    not_started = models.PositiveSmallIntegerField(default=0, verbose_name=CourseStatus.verbose_names[CourseStatus.not_started])
    in_progress = models.PositiveSmallIntegerField(default=0, verbose_name=CourseStatus.verbose_names[CourseStatus.in_progress])
    total_time_spent = models.PositiveIntegerField(default=0)

    @classmethod
    def generate_today_reports(cls, org_combinations, user_ids_by_org):
        for org in user_ids_by_org.keys():
            for user_id in user_ids_by_org[org]['total']:
                logger.info("learner report for user_id=%d org=%s" % (user_id, org))
                reports = LearnerCourseJsonReport.filter_by_day(user_id=user_id, org=org)
                cls.update_or_create(user_id, org, reports)

        for combination in org_combinations:
            cls.update_or_create_combined_orgs(combination, user_ids_by_org)

        ReportLog.update_or_create(learner=timezone.now())

    @classmethod
    def update_or_create(cls, user_id, org, learner_course_reports):
        posts = 0
        badges_earned = 0
        badges_possible = 0
        finished = 0
        failed = 0
        in_progress = 0
        not_started = 0
        total_score = 0
        nb_completed_courses = 0
        for report in learner_course_reports:
            posts += report.posts
            earned, possible = get_badges(report.badges)
            badges_earned += earned
            badges_possible += possible
            if report.status == CourseStatus.finished:
                finished += 1
            elif report.status == CourseStatus.failed:
                failed += 1
            elif report.status == CourseStatus.in_progress:
                in_progress += 1
            elif report.status == CourseStatus.not_started:
                not_started += 1
            if report.status in [CourseStatus.finished, CourseStatus.failed]:
                total_score += report.current_score
                nb_completed_courses += 1

        average_final_score = 0
        if nb_completed_courses > 0:
            average_final_score = total_score / nb_completed_courses

        total_time_spent = (LearnerVisitsDailyReport.objects.filter(user_id=user_id).aggregate(
            Sum('time_spent')).get('time_spent__sum') or 0)

        cls.objects.update_or_create(
            created=timezone.now().date(),
            user_id=user_id,
            org=org,
            defaults={'enrollments': len(learner_course_reports),
                      'average_final_score': average_final_score,
                      'badges': format_badges(badges_earned, badges_possible),
                      'posts': posts,
                      'finished': finished,
                      'failed': failed,
                      'not_started': not_started,
                      'in_progress': in_progress,
                      'total_time_spent': total_time_spent})

    @classmethod
    def update_or_create_combined_orgs(cls, org_combination, user_ids_by_org):
        user_ids = set()
        query = Q()
        for org in org_combination:
            query = query | Q(org=org)
            if org in user_ids_by_org.keys():
                user_ids = user_ids.union(user_ids_by_org[org]['total'])

        combined_org = get_combined_org(org_combination)
        for user_id in user_ids:
            logger.info("learner report for user_id=%d org=%s" % (user_id, combined_org))
            reports = LearnerCourseJsonReport.objects.filter(query, is_active=True, user_id=user_id)
            cls.update_or_create(user_id, combined_org, reports)

    @classmethod
    def filter_by_period(cls, org, to_date, from_date=None, **kwargs):
        logger.info("ANALYTICS -- LearnerDailyReport filter_by_period org=%s from=%s to=%s kwargs=%s" % (
            org, from_date, to_date, kwargs.keys()))
        if from_date:
            user_ids = LearnerVisitsDailyReport.get_active_user_ids(from_date, to_date)

            old_results = cls.objects.filter(org=org, created=from_date, user_id__in=user_ids, **kwargs)
            old_time_spent_by_user = {r.user_id: r.total_time_spent for r in old_results}

            new_results = cls.objects.filter(org=org, created=to_date, user_id__in=user_ids, **kwargs)

            logger.info("ANALYTICS -- LearnerDailyReport filter_by_period org=%s from=%s to=%s nb user_ids=%d" % (
                org, from_date, to_date, len(user_ids)))
            logger.info("ANALYTICS -- nb old_results=%d / nb new_results=%d" % (len(old_results), len(new_results)))
            results = []
            for r in new_results:
                old_time_spent = 0
                try:
                    old_time_spent = old_time_spent_by_user[r.user_id]
                except KeyError:
                    pass
                results.append(LearnerDailyReportMockup(r, (r.total_time_spent - old_time_spent)))
            logger.info("ANALYTICS -- => nb results=%d" % len(results))
            return results

        logger.info("ANALYTICS --  no period start => return only results for day=%s" % to_date)
        return cls.objects.filter(org=org, created=to_date, **kwargs)


class CourseDailyReport(UnicodeMixin, ReportMixin, UniqueVisitorsMixin, TimeModel):
    class Meta(object):
        app_label = "triboo_analytics"
        get_latest_by = "created"
        unique_together = ('created', 'course_id')
        index_together = ['created', 'course_id']

    course_id = CourseKeyField(max_length=255, db_index=True, null=False)
    enrollments = models.PositiveIntegerField(default=0)
    unique_visitors = models.PositiveIntegerField(default=0)
    average_final_score = models.PositiveSmallIntegerField(default=0)
    posts = models.PositiveIntegerField(default=0)
    finished = models.PositiveIntegerField(default=0, verbose_name=CourseStatus.verbose_names[CourseStatus.finished])
    failed = models.PositiveIntegerField(default=0, verbose_name=CourseStatus.verbose_names[CourseStatus.failed])
    in_progress = models.PositiveIntegerField(default=0, verbose_name=CourseStatus.verbose_names[CourseStatus.in_progress])
    not_started = models.PositiveIntegerField(default=0, verbose_name=CourseStatus.verbose_names[CourseStatus.not_started])
    average_complete_time = models.PositiveIntegerField(default=0)

    @classmethod
    def generate_today_reports(cls, course_ids):
        for course_id in course_ids:
            logger.info("course report for course_id=%s" % course_id)
            reports = LearnerCourseJsonReport.filter_by_day(course_id=course_id)
            cls.update_or_create(course_id, reports)

        ReportLog.update_or_create(course=timezone.now())

    @classmethod
    def update_or_create(cls, course_id, learner_course_reports):
        posts = 0
        finished = 0
        failed = 0
        in_progress = 0
        not_started = 0
        nb_completed_courses = 0
        total_score = 0
        total_time = 0
        for report in learner_course_reports:
            posts += report.posts
            if report.status == CourseStatus.finished:
                finished += 1
            elif report.status == CourseStatus.failed:
                failed += 1
            elif report.status == CourseStatus.in_progress:
                in_progress += 1
            elif report.status == CourseStatus.not_started:
                not_started += 1
            if report.status in [CourseStatus.finished, CourseStatus.failed]:
                total_score += report.current_score
                total_time += report.total_time_spent
                nb_completed_courses += 1

        average_final_score = 0
        average_complete_time = 0
        if nb_completed_courses > 0:
            average_final_score = total_score / nb_completed_courses
            average_complete_time = total_time / nb_completed_courses

        today_unique_visitors = (LearnerVisitsDailyReport.filter_by_day(course_id=course_id).aggregate(
            Count('user_id', distinct=True)).get('user_id__count') or 0)

        cls.objects.update_or_create(
            created=timezone.now().date(),
            course_id=course_id,
            defaults={'enrollments': len(learner_course_reports),
                      'unique_visitors': today_unique_visitors,
                      'average_final_score': average_final_score,
                      'posts': posts,
                      'finished': finished,
                      'failed': failed,
                      'in_progress': in_progress,
                      'not_started': not_started,
                      'average_complete_time': average_complete_time})

    @classmethod
    def update_or_create_unique_visitors(cls, day, course_id):
        unique_visitors = (LearnerVisitsDailyReport.filter_by_day(date_time=day, course_id=course_id).aggregate(
            Count('user_id', distinct=True)).get('user_id__count') or 0)
        cls.objects.update_or_create(
            created=day.date(),
            course_id=course_id,
            defaults={'unique_visitors': unique_visitors})

    @classmethod
    def get_average_complete_time_csv_data(cls, reports):
        _reports = reports.values('created', 'average_complete_time').order_by('created')
        average_complete_time_csv_data = ""
        for r in _reports:
            average_complete_time_csv_data += "%s,%d\\n" % (r['created'].strftime('%Y-%m-%d'), r['average_complete_time'])

        return average_complete_time_csv_data

    @classmethod
    def get_csv_data(cls, course_id, from_date=None, to_date=None):
        course_overview = CourseOverview.objects.get(id=course_id)

        if from_date:
            if course_overview.start > from_date:
                from_date = course_overview.start
            if to_date:
                reports = cls.objects.filter(course_id=course_id,
                                             created__gte=from_date,
                                             created__lte=to_date)
            else:
                reports = cls.objects.filter(course_id=course_id,
                                             created__gte=from_date)
        else:
            if to_date:
                reports = cls.objects.filter(course_id=course_id,
                                             created__gte=course_overview.start,
                                             created__lte=to_date)
            else:
                reports = cls.objects.filter(course_id=course_id,
                                             created__gte=course_overview.start)

        csv_unique_visitors = cls._get_unique_visitors_csv_data(reports)
        csv_average_complete_time = cls.get_average_complete_time_csv_data(reports)
        return csv_unique_visitors, csv_average_complete_time


class MicrositeDailyReport(UnicodeMixin, ReportMixin, UniqueVisitorsMixin, TimeModel):
    class Meta:
        app_label = "triboo_analytics"
        get_latest_by = "created"
        unique_together = ('created', 'org')
        index_together = ['created', 'org']

    org = models.CharField(max_length=255, null=False)
    users = models.PositiveIntegerField(default=0)
    courses = models.PositiveIntegerField(default=0)
    finished = models.PositiveIntegerField(default=0)
    unique_visitors = models.PositiveIntegerField(default=0)
    average_time_spent = models.PositiveIntegerField(default=0)
    total_time_spent_on_mobile = models.BigIntegerField(default=0)
    total_time_spent_on_desktop = models.BigIntegerField(default=0)

    @classmethod
    def generate_today_reports(cls, course_ids, org_combinations, user_ids_by_org):
        finished_by_org = {}
        with connection.cursor() as cursor:
            cursor.execute("select org, count(*) as finished from triboo_analytics_learnercoursejsonreport "\
                           "where is_active=1 and status=%s group by org" % CourseStatus.finished)
            for row in cursor.fetchall():
                finished_by_org[row[0]] = row[1]

        course_ids_by_org = defaultdict(list)
        for course_id in course_ids:
            course_ids_by_org[course_id.org].append(course_id)

        for org, ids in course_ids_by_org.iteritems():
            logger.info("microsite report for org=%s" % org)
            nb_users = len(user_ids_by_org[org]['total']) if org in user_ids_by_org.keys() else 0
            finished = finished_by_org.get(org, 0)
            cls.update_or_create(org, ids, nb_users, finished)

        for combination in org_combinations:
            cls.update_or_create_combined_orgs(combination, user_ids_by_org)

        ReportLog.update_or_create(microsite=timezone.now())

    @classmethod
    def update_or_create(cls, org, course_ids, nb_users, finished):
        total_time_spent_on_mobile = (LearnerVisitsDailyReport.objects.filter(
            org=org, course_id__in=course_ids, device="mobile").aggregate(
            Sum('time_spent')).get('time_spent__sum') or 0)
        total_time_spent_on_desktop = (LearnerVisitsDailyReport.objects.filter(
            org=org, course_id__in=course_ids, device="desktop").aggregate(
            Sum('time_spent')).get('time_spent__sum') or 0)

        today_unique_visitors = (LearnerVisitsDailyReport.filter_by_day(org=org).aggregate(
            Count('user_id', distinct=True)).get('user_id__count') or 0)

        all_unique_visitors = (LearnerVisitsDailyReport.objects.filter(org=org).aggregate(
            Count('user_id', distinct=True)).get('user_id__count') or 0)
        average_time_spent = 0
        if all_unique_visitors > 0:
            average_time_spent = (total_time_spent_on_mobile + total_time_spent_on_desktop) / all_unique_visitors

        cls.objects.update_or_create(
            created=timezone.now().date(),
            org=org,
            defaults={'users': nb_users,
                      'courses': len(course_ids),
                      'finished': finished,
                      'unique_visitors': today_unique_visitors,
                      'average_time_spent': average_time_spent,
                      'total_time_spent_on_mobile': total_time_spent_on_mobile,
                      'total_time_spent_on_desktop': total_time_spent_on_desktop})

    @classmethod
    def update_or_create_combined_orgs(cls, org_combination, user_ids_by_org):
        combined_org = get_combined_org(org_combination)

        learner_course_reports = []
        courses = 0
        finished = 0
        total_time_spent_on_mobile = 0
        total_time_spent_on_desktop = 0
        users = set()

        for org in org_combination:
            microsite_report = cls.get_by_day(org=org)
            if not microsite_report:
                logger.error("combined microsite report for %s could not be generated: no report found for %s" % (
                    org_combination, org))
                return
            courses += microsite_report.courses
            finished += microsite_report.finished
            total_time_spent_on_mobile += microsite_report.total_time_spent_on_mobile
            total_time_spent_on_desktop += microsite_report.total_time_spent_on_desktop

            org_users = set()
            if org in user_ids_by_org.keys():
                org_users = user_ids_by_org[org]['total']
            users = users.union(org_users)

        today_unique_visitors = (LearnerVisitsDailyReport.filter_by_day(org__in=org_combination).aggregate(
            Count('user_id', distinct=True)).get('user_id__count') or 0)

        all_unique_visitors = (LearnerVisitsDailyReport.objects.filter(org__in=org_combination).aggregate(
            Count('user_id', distinct=True)).get('user_id__count') or 0)
        average_time_spent = 0
        if all_unique_visitors > 0:
            average_time_spent = (total_time_spent_on_mobile + total_time_spent_on_desktop) / all_unique_visitors

        logger.info("microsite report for org=%s" % combined_org)
        cls.objects.update_or_create(
            created=timezone.now().date(),
            org=combined_org,
            defaults={'users': len(users),
                      'courses': courses,
                      'finished': finished,
                      'unique_visitors': today_unique_visitors,
                      'average_time_spent': average_time_spent,
                      'total_time_spent_on_mobile': total_time_spent_on_mobile,
                      'total_time_spent_on_desktop': total_time_spent_on_desktop})

    @classmethod
    def update_or_create_unique_visitors(cls, day, org):
        unique_visitors = (LearnerVisitsDailyReport.filter_by_day(date_time=day, org=org).aggregate(
            Count('user_id', distinct=True)).get('user_id__count') or 0)
        cls.objects.update_or_create(
            created=day.date(),
            org=org,
            defaults={'unique_visitors': unique_visitors})

    @classmethod
    def update_or_create_combined_orgs_unique_visitors(cls, day, org_combination):
        combined_org = get_combined_org(org_combination)
        learner_visits = LearnerVisitsDailyReport.objects.none()
        for org in org_combination:
            org_learner_visits = LearnerVisitsDailyReport.filter_by_day(date_time=day, org=org)
            learner_visits = learner_visits | org_learner_visits
        unique_visitors = (learner_visits.aggregate(Count('user_id', distinct=True)).get('user_id__count') or 0)
        cls.objects.update_or_create(
            created=day.date(),
            org=combined_org,
            defaults={'unique_visitors': unique_visitors})

    @classmethod
    def get_users_csv_data(cls, reports):
        _reports = reports.values('created', 'users').order_by('created')
        users_csv_data = ""
        for r in _reports:
            users_csv_data += "%s,%d\\n" % (r['created'].strftime('%Y-%m-%d'), r['users'])

        return users_csv_data

    @classmethod
    def get_average_time_spent_csv_data(cls, reports):
        _reports = reports.values('created', 'average_time_spent').order_by('created')
        average_time_spent_csv_data = ""
        for r in _reports:
            average_time_spent_csv_data += "%s,%d\\n" % (r['created'].strftime('%Y-%m-%d'), r['average_time_spent'])

        return average_time_spent_csv_data

    @classmethod
    def get_csv_data(cls, org, from_date=None, to_date=None):
        if from_date:
            if to_date:
                reports = cls.objects.filter(org=org, created__gte=from_date, created__lte=to_date)
            else:
                reports = cls.objects.filter(org=org, created__gte=from_date)
        else:
            if to_date:
                reports = cls.objects.filter(org=org, created__lte=to_date)
            else:
                reports = cls.objects.filter(org=org)
        csv_unique_visitors = cls._get_unique_visitors_csv_data(reports)
        csv_users = cls.get_users_csv_data(reports)
        csv_average_time_spent = cls.get_average_time_spent_csv_data(reports)
        return csv_unique_visitors, csv_users, csv_average_time_spent


class CountryDailyReport(UnicodeMixin, ReportMixin, TimeModel):
    class Meta:
        app_label = "triboo_analytics"
        get_latest_by = "created"
        unique_together = ('created', 'org', 'country')
        index_together = ['created', 'org']

    org = models.CharField(max_length=255, null=False)
    country = CountryField(null=True)
    nb_users = models.PositiveIntegerField(default=0)

    @classmethod
    def generate_today_reports(cls, org_combinations, user_ids_by_org):
        for org in user_ids_by_org.keys():
            logger.info("country reports for org=%s" % org)
            cls.update_or_create(org, user_ids_by_org[org]['countries'])

        for combination in org_combinations:
            cls.update_or_create_combined_orgs(combination, user_ids_by_org)

        ReportLog.update_or_create(country=timezone.now())

    @classmethod
    def update_or_create(cls, org, users_by_country):
        for country, user_ids in users_by_country.iteritems():
            cls.objects.update_or_create(
                created=timezone.now().date(),
                org=org,
                country=country,
                defaults={'nb_users': len(user_ids)})

    @classmethod
    def update_or_create_combined_orgs(cls, org_combination, user_ids_by_org):
        combined_org = get_combined_org(org_combination)

        users_by_country = {}
        for org in org_combination:
            if org in user_ids_by_org.keys():
                for country, user_ids in user_ids_by_org[org]['countries'].iteritems():
                    if country not in users_by_country.keys():
                        users_by_country[country] = set()
                    users_by_country[country] = users_by_country[country].union(user_ids)

        logger.info("country reports for org=%s" % combined_org)
        cls.update_or_create(combined_org, users_by_country)


class IltModule(TimeStampedModel):
    class Meta(object):
        app_label = "triboo_analytics"

    id = UsageKeyField(db_index=True, primary_key=True, max_length=255)
    course_id = CourseKeyField(max_length=255, null=False)
    course_display_name = models.TextField(null=False)
    course_country = models.TextField(null=True, blank=True)
    course_tags = models.TextField(null=True, blank=True)
    chapter_display_name = models.TextField(null=True, blank=True)
    section_display_name = models.TextField(null=True, blank=True)


class IltSession(TimeStampedModel):
    class Meta(object):
        app_label = "triboo_analytics"
        unique_together = ('ilt_module', 'session_nb')
        index_together = ['ilt_module', 'session_nb']

    ilt_module = models.ForeignKey(IltModule, null=False)
    session_nb = models.PositiveSmallIntegerField(null=True)
    org = models.CharField(max_length=255, db_index=True, null=True, default=None)
    start = models.DateTimeField(default=None, null=True, blank=True)
    end = models.DateTimeField(default=None, null=True, blank=True)
    duration = models.PositiveSmallIntegerField(default=0)
    seats = models.PositiveSmallIntegerField(default=0)
    ack_attendance_sheet = models.BooleanField(default=False)
    location_id = models.TextField(null=True, blank=True, default=None)
    location = models.TextField(null=True, blank=True, default=None)
    address = models.TextField(null=True, blank=True, default=None)
    zip_code = models.TextField(null=True, blank=True, default=None)
    city = models.TextField(null=True, blank=True, default=None)
    area = models.TextField(null=True, blank=True, default=None)
    enrollees = models.PositiveSmallIntegerField(default=0)
    attendees = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def session_id(self):
        module_id = "%s" % self.ilt_module.id
        start = module_id.find("@ilt+block@")
        if start > 0:
            module_id = module_id[start + 11:]
        return "%s_%d" % (module_id, self.session_nb)

    @classmethod
    def get_ilt_blocks(cls, overviews):
        ilt_blocks = {}
        for overview in overviews:
            course_ilt_blocks = []
            try:
                course_details = CourseDetails.fetch(overview.id)
                outline = course_structure(overview.id)
                outline = outline['blocks']
                for block_id, block in outline.iteritems():
                    if block['type'] == "ilt":
                        course_ilt_blocks.append(block_id)
                        ilt_blocks[block_id] = {
                            'course_id': overview.id,
                            'course_display_name': overview.display_name,
                            'course_country': ", ".join(course_details.course_country),
                            'course_tags': ", ".join(course_details.vendor)
                        }
                    for child in block['children']:
                        outline[child]['parent'] = block_id

                for ilt_block_id in course_ilt_blocks:
                    parent_id = outline[ilt_block_id]['parent']
                    vertical = outline[parent_id]
                    sequential = outline[vertical['parent']]
                    ilt_blocks[ilt_block_id]['section_display_name'] = sequential['display_name']
                    chapter = outline[sequential['parent']]
                    ilt_blocks[ilt_block_id]['chapter_display_name'] = chapter['display_name']

            except (CourseStructureNotAvailableError, AttributeError), e:
                pass

        return ilt_blocks

    @classmethod
    def prepare_today_reports(cls):
        cls.objects.all().update(is_active=False)
        IltLearnerReport.objects.all().update(is_active=False)

    @classmethod
    def clean_obsolete_reports(cls):
        cls.objects.filter(is_active=False).delete()
        IltLearnerReport.objects.filter(is_active=False).delete()

    @classmethod
    def generate_today_reports(cls, overviews):
        ilt_blocks = cls.get_ilt_blocks(overviews)
        for ilt_block_id, ilt_block_info in ilt_blocks.iteritems():
            logger.info("ILT Module %s" % ilt_block_id)
            ilt_module_id = UsageKey.from_string(ilt_block_id)
            ilt_module, _ = IltModule.objects.update_or_create(
                id=ilt_module_id,
                defaults={'course_id': ilt_block_info['course_id'],
                          'course_display_name': ilt_block_info['course_display_name'],
                          'course_country': ilt_block_info['course_country'],
                          'course_tags': ilt_block_info['course_tags'],
                          'chapter_display_name': ilt_block_info['chapter_display_name'],
                          'section_display_name': ilt_block_info['section_display_name']})

            sessions = XModuleUserStateSummaryField.objects.filter(usage_id=ilt_module_id,
                                                                   field_name="sessions").only('value')
            if len(sessions) == 1:
                sessions = json.loads(sessions[0].value)
                if "counter" in sessions.keys():
                    del (sessions['counter'])

            else:
                sessions = {}
                logger.info("ILT Module %s has no sessions => pass" % ilt_block_id)
                pass

            registrations = XModuleUserStateSummaryField.objects.filter(usage_id=ilt_module_id,
                                                                        field_name="enrolled_users").only('value')
            registrations = json.loads(registrations[0].value) if len(registrations) == 1 else {}

            scores = StudentModule.objects.filter(module_state_key=ilt_module_id).only('student_id', 'grade')

            users = {}
            for score in scores:
                users[score.student.id] = {
                    'user': score.student,
                    'session_nb': None,
                    'registration': None,
                    'attendee': (score.grade > 0) if score.grade else False
                }
            for session_nb, session_registrations in registrations.iteritems():
                for user_id, registration in session_registrations.iteritems():
                    user_id = int(user_id)
                    if user_id in users.keys():
                        users[user_id]['session_nb'] = session_nb
                        users[user_id]['registration'] = registration
                    else:
                        try:
                            user = User.objects.get(id=user_id)
                            users[user_id] = {
                                'user': user,
                                'session_nb': session_nb,
                                'registration': registration,
                                'attendee': False
                            }
                        except User.DoesNotExist:
                            pass

            try:
                cls.update_or_create(ilt_module, ilt_module_id.org, sessions, users)
                IltLearnerReport.generate_today_reports(ilt_module, users)
            except Exception as err:  # pylint: disable=broad-except
                logger.error('Error with %s: %r', ilt_block_id, err)
                pass

    @classmethod
    def update_or_create(cls, ilt_module, org, sessions, users):
        for session_nb, session in sessions.iteritems():
            enrollees = 0
            attendees = 0
            for user_id, user_session in users.iteritems():
                if user_session['session_nb'] == session_nb:
                    if user_session['registration']['status'] in ["accepted", "confirmed"]:
                        enrollees += 1
                    if user_session['attendee']:
                        attendees += 1
            cls.objects.update_or_create(ilt_module=ilt_module,
                                         session_nb=session_nb,
                                         defaults={
                                             'start': datetime.strptime(session['start_at'], '%Y-%m-%dT%H:%M').replace(
                                                 tzinfo=UTC),
                                             'end': datetime.strptime(session['end_at'], '%Y-%m-%dT%H:%M').replace(
                                                 tzinfo=UTC),
                                             'duration': session.get('duration', 0),
                                             'seats': session['total_seats'],
                                             'ack_attendance_sheet': session.get('ack_attendance_sheet', False),
                                             'location_id': session.get('location_id', ""),
                                             'location': session['location'],
                                             'address': session.get('address', ""),
                                             'zip_code': session.get('zip_code', ""),
                                             'city': session.get('city', ""),
                                             'area': session.get('area_region', ""),
                                             'org': org,
                                             'enrollees': enrollees,
                                             'attendees': attendees,
                                             'is_active': True})


class IltLearnerReport(TimeModel):
    class Meta(object):
        app_label = "triboo_analytics"
        unique_together = ('ilt_module', 'user')
        index_together = ['ilt_module', 'user']

    ilt_module = models.ForeignKey(IltModule, db_index=True, null=False)
    user = models.ForeignKey(User, db_index=True, null=False)
    org = models.CharField(max_length=255, db_index=True, null=True, default=None)
    ilt_session = models.ForeignKey(IltSession, null=True)
    STATUS_CHOICES = (
        ('pending', ugettext_noop("Pending")),
        ('accepted', ugettext_noop("Accepted")),
        ('confirmed', ugettext_noop("Confirmed")),
        ('refused', ugettext_noop("Refused"))
    )
    status = models.CharField(null=False, max_length=9, choices=STATUS_CHOICES)
    attendee = models.BooleanField(default=False)
    outward_trips = models.PositiveSmallIntegerField(default=0)
    return_trips = models.PositiveSmallIntegerField(default=0)
    accommodation = models.BooleanField(default=False)
    comment = models.TextField(null=True, blank=True, default=None)
    hotel = models.TextField(null=True, blank=True, default=None)
    is_active = models.BooleanField(default=True)

    @classmethod
    def generate_today_reports(cls, ilt_module, users):
        for _, user_session in users.iteritems():
            cls.update_or_create(ilt_module, user_session)

    @classmethod
    def update_or_create(cls, ilt_module, user_session):
        ilt_session = None
        if user_session['session_nb']:
            ilt_session = IltSession.objects.get(ilt_module=ilt_module, session_nb=user_session['session_nb'])

        status = "Confirmed"
        outward_trips = 1
        return_trips = 1
        accommodation = False
        comment = None
        hotel = None

        if user_session['registration']:
            status = user_session['registration']['status']
            outward_trips = int(user_session['registration']['number_of_one_way']) if user_session['registration'][
                'number_of_one_way'] else 0
            return_trips = int(user_session['registration']['number_of_return']) if user_session['registration'][
                'number_of_return'] else 0
            if user_session['registration']['accommodation'] == "yes":
                accommodation = True
            comment = user_session['registration']['comment']
            hotel = user_session['registration'].get('hotel', None)

        cls.objects.update_or_create(ilt_module=ilt_module,
                                     user=user_session['user'],
                                     defaults={'org': ilt_module.id.org,
                                               'ilt_session': ilt_session,
                                               'status': status,
                                               'attendee': user_session['attendee'],
                                               'outward_trips': outward_trips,
                                               'return_trips': return_trips,
                                               'accommodation': accommodation,
                                               'comment': comment,
                                               'hotel': hotel,
                                               'is_active': True})


def get_org_combinations():
    org_combinations = []
    for configuration in SiteConfiguration.objects.filter(enabled=True).all():
        course_org_filter = configuration.get_value('course_org_filter', None)
        if course_org_filter and isinstance(course_org_filter, list) and len(course_org_filter) > 1:
            sorted_course_org_filter = sorted(course_org_filter)
            if sorted_course_org_filter not in org_combinations:
                org_combinations.append(sorted_course_org_filter)
    return org_combinations


def generate_today_reports(multi_process=False):
    try:
        User.objects.get(username=ANALYTICS_WORKER_USER)
    except User.DoesNotExist:
        create_analytics_worker()

    yesterday = timezone.now() + timezone.timedelta(days=-1)
    overviews = CourseOverview.objects.filter(start__lte=yesterday).only('id')
    course_ids = [o.id for o in overviews]

    logger.info("start updating course structures")
    for course_id in course_ids:
        update_course_structure.apply(args=[text_type(course_id)])

    logger.info("start updating tracking logs")
    tracking_log_helper = TrackingLogHelper(course_ids)
    tracking_log_helper.update_logs(day=yesterday)

    logger.info("start Learner Visits reports")
    LearnerVisitsDailyReport.generate_today_reports()

    logger.info("start deactivate reports for inactive users/enrollments")
    LearnerCourseJsonReport.objects.filter(is_active=True, user__is_active=False).update(is_active=False)
    LearnerSectionJsonReport.objects.filter(is_active=True, user__is_active=False).update(is_active=False)
    LearnerBadgeJsonReport.objects.filter(is_active=True, user__is_active=False).update(is_active=False)

    inactive_enrollments = CourseEnrollment.objects.filter(is_active=False, user__is_active=True).values('user',
                                                                                                         'course_id')
    for e in inactive_enrollments:
        LearnerCourseJsonReport.objects.filter(user=e['user'], course_id=e['course_id']).update(is_active=False)
        LearnerSectionJsonReport.objects.filter(user=e['user'], course_id=e['course_id']).update(is_active=False)
        LearnerBadgeJsonReport.objects.filter(user=e['user'], badge__course_id=e['course_id']).update(is_active=False)

    last_analytics_success = None
    last_reportlog = ReportLog.get_latest()
    if last_reportlog:
        last_analytics_success = last_reportlog.created

    logger.info("start Learner Course reports")
    LearnerCourseJsonReport.generate_today_reports(last_analytics_success,
                                                   overviews,
                                                   tracking_log_helper.sections_by_course,
                                                   multi_process=multi_process)

    logger.info("start double checking generated Learner Course reports")
    course_last_updates = {o.id: o.modified.date() for o in overviews}
    check_generated_learner_course_reports(last_analytics_success,
                                           overviews,
                                           course_last_updates,
                                           tracking_log_helper.sections_by_course)

    ReportLog.update_or_create(learner_course=timezone.now())

    logger.info("fetch user_ids by org")
    # user_ids_by_org = { org : { total : set(user_ids...), countries : { XX : set(user_ids...) } } }
    user_ids_by_org = {}
    with connection.cursor() as cursor:
        cursor.execute("select distinct user_id, org from triboo_analytics_learnercoursejsonreport where is_active=1")
        for row in cursor.fetchall():
            user_id = row[0]
            org = row[1]
            if org not in user_ids_by_org.keys():
                user_ids_by_org[org] = {'total': set(), 'countries': {}}
            user_ids_by_org[org]['total'].add(user_id)
            try:
                country = UserProfile.objects.get(user_id=user_id).country
                if country not in user_ids_by_org[org]['countries'].keys():
                    user_ids_by_org[org]['countries'][country] = set()
                user_ids_by_org[org]['countries'][country].add(user_id)
            except UserProfile.DoesNotExist:
                pass

    org_combinations = get_org_combinations()

    logger.info("start Learner reports")
    LearnerDailyReport.generate_today_reports(org_combinations, user_ids_by_org)

    logger.info("start Course reports")
    CourseDailyReport.generate_today_reports(course_ids)

    logger.info("start Microsite reports")
    MicrositeDailyReport.generate_today_reports(course_ids, org_combinations, user_ids_by_org)

    logger.info("start Country reports")
    CountryDailyReport.generate_today_reports(org_combinations, user_ids_by_org)

    logger.info("start Leaderboard daily update")
    LeaderBoard.update_stayed_online()

    logger.info("start ILT reports")
    IltSession.prepare_today_reports()
    all_overviews = CourseOverview.objects.all()
    IltSession.generate_today_reports(all_overviews)
    IltSession.clean_obsolete_reports()


def check_generated_learner_course_reports(last_analytics_success, overviews, course_last_updates, sections_by_course):
    all_good = False
    today = timezone.now().date()
    course_ids_to_check = [o.id for o in overviews]
    while not all_good:
        course_ids_nok = []
        logger.info("new check round with %d courses" % len(course_ids_to_check))
        for course_id in course_ids_to_check:
            course_id_needs_fix = False
            logger.info("checking %s" % course_id)
            course = modulestore().get_course(course_id)
            sections = sections_by_course["%s" % course_id]
            enrollments = CourseEnrollment.objects.filter(is_active=True, course_id=course_id, user__is_active=True)
            for enrollment in enrollments:
                is_missing = True
                try:
                    learner_course_report = LearnerCourseJsonReport.objects.get(course_id=course_id,
                                                                                user_id=enrollment.user_id)
                    if learner_course_report.modified.date() == today and learner_course_report.is_active:
                        is_missing = False
                except LearnerCourseJsonReport.DoesNotExist:
                    pass
                if is_missing:
                    course_id_needs_fix = True
                    # logger.info("missing report for user_id=%d => trying to generate it" % enrollment.user_id)
                    LearnerCourseJsonReport.generate_enrollment_report(last_analytics_success,
                                                                       course_last_updates[course_id],
                                                                       enrollment,
                                                                       course,
                                                                       sections)
            if course_id_needs_fix:
                course_ids_nok.append(course_id)
        if len(course_ids_nok) == 0:
            all_good = True
        else:
            course_ids_to_check = course_ids_nok


class LeaderboardActivityLog(TimeStampedModel):
    """
    We use this model to track leaderboard activities instead of TrackingLog.
    Event type could be 'unit_completion', 'online_check'.
    """
    user_id = models.PositiveIntegerField(db_index=True)
    event_type = models.CharField(max_length=512)
    event_time = models.DateTimeField(db_index=True)
    block_key = UsageKeyField(max_length=255, blank=True, null=True)
    course_key = CourseKeyField(max_length=255, blank=True, null=True, db_index=True)

    class Meta(object):
        app_label = "triboo_analytics"
        index_together = [
            ('user_id', 'event_type'),
            ('user_id', 'event_type', 'block_key')
        ]


class LeaderBoard(TimeStampedModel):
    user = models.OneToOneField(User, db_index=True, on_delete=models.CASCADE)
    first_login = models.BooleanField(default=False)
    first_course_opened = models.BooleanField(default=False)
    stayed_online = models.PositiveIntegerField(default=0)   # number of days the user has more 30 mins online
    non_graded_completed = models.PositiveIntegerField(default=0)
    graded_completed = models.PositiveIntegerField(default=0)
    unit_completed = models.PositiveIntegerField(default=0)
    course_completed = models.PositiveIntegerField(default=0)
    learning_path_completed = models.PositiveIntegerField(default=0)  # lms/templates/triboo_analytics/leaderboard.html:L57
    # last_time_rank = models.PositiveIntegerField(default=0)
    last_week_score = models.PositiveIntegerField(default=0)
    last_week_rank = models.PositiveIntegerField(default=0)
    last_month_score = models.PositiveIntegerField(default=0)
    last_month_rank = models.PositiveIntegerField(default=0)

    COURSE_STRUCTURE = {}

    class Meta(object):
        app_label = "triboo_analytics"

    def __str__(self):
        return "LeaderBoard detail of user: {user_id}, first_login: {first_login}, first_course_opened: " \
               "{first_course_opened}, stayed_online: {stayed_online}, non_graded_completed: {non_graded_completed}" \
               "graded_completed: {graded_completed}, unit_completed: {unit_completed}, course_completed: " \
               "{course_completed}, learning_path_completed: {learning_path_completed}, " \
               "last_week_score: {last_week_score}, last_week_rank: {last_week_rank}," \
               "last_month_score: {last_month_score}, last_month_rank: {last_month_rank}".format(
                user_id=self.user_id,
                first_login=self.first_login,
                first_course_opened=self.first_course_opened,
                stayed_online=self.stayed_online,
                non_graded_completed=self.non_graded_completed,
                graded_completed=self.graded_completed,
                unit_completed=self.unit_completed,
                course_completed=self.course_completed,
                learning_path_completed=self.learning_path_completed,
                last_week_score=self.last_week_score,
                last_week_rank=self.last_week_rank,
                last_month_score=self.last_month_score,
                last_month_rank=self.last_month_rank
                )

    @classmethod
    def init_user(cls, user, worker):
        non_graded_completed = 0
        graded_completed = 0
        unit_completed = 0
        if user.last_login is not None:
            first_login = True
        else:
            first_login = False

        if StudentModule.objects.filter(student=user).exists():
            first_course_opened = True
        else:
            first_course_opened = False

        enrollments = CourseEnrollment.objects.filter(is_active=True, user=user).values_list(
            'course_id', 'completed'
        )

        from util.programs import ProgramCoursesKeysStatistics
        programs_stat = ProgramCoursesKeysStatistics()
        learning_path_completed = programs_stat.count_completed_programs_by_user(
            user,
            {str(e[0]) for e in enrollments if e[1]}
        )

        course_completed = len(enrollments.filter(completed__isnull=False))
        for course_key, _ in enrollments:
            try:
                cc_user = cc.User(id=user.id, course_id=course_key).to_dict()
                nb_posts = cc_user.get('comments_count', 0) + cc_user.get('threads_count', 0)
                non_graded_completed += nb_posts
            except (CommentClientMaintenanceError, CommentClientRequestError):
                pass
            course_usage_key = modulestore().make_course_usage_key(course_key)
            subsection_structure = None
            subsection_grade_factory = None
            if course_key in cls.COURSE_STRUCTURE:
                vertical_blocks = cls.COURSE_STRUCTURE[course_key][0]
                problem_blocks_data = cls.COURSE_STRUCTURE[course_key][1]
            else:
                # load course blocks with a staff user
                try:
                    vertical_blocks = modulestore().get_items(course_key, qualifiers={'category': 'vertical'})
                except Exception:
                    continue
                problem_blocks_data = {}
                cls.COURSE_STRUCTURE[course_key] = (vertical_blocks, problem_blocks_data)

            course_block_completions = BlockCompletion.get_course_completions(user, course_key)
            if len(course_block_completions) == 0:
                continue

            for block in vertical_blocks:
                block_id = block.location
                children = block.children
                if children:
                    completed = True
                else:
                    completed = False
                    continue
                for child in children[:]:
                    if child.block_type == 'library_content':
                        lib_content_blocks = get_course_blocks(user, child)
                        extra_children = [i for i in lib_content_blocks if i.block_type != 'library_content']
                        children = children + extra_children
                for child in children:
                    if child.block_type in ['discussion', 'library_content']:
                        continue
                    completion = course_block_completions.get(child, None)
                    if completion:
                        if child.block_type in ['survey', 'poll', 'word_cloud']:
                            non_graded_completed += 1
                        elif child.block_type == 'problem':
                            if child in problem_blocks_data:
                                graded = problem_blocks_data[child]
                                if graded:
                                    graded_completed += 1
                                else:
                                    non_graded_completed += 1
                            else:
                                if subsection_structure is None:
                                    subsection_structure = get_course_blocks(user, course_usage_key)
                                    subsection_grade_factory = SubsectionGradeFactory(
                                        user, course_structure=subsection_structure
                                    )
                                child_data = subsection_structure[child].fields
                                if not child_data['graded']:
                                    non_graded_completed += 1
                                    problem_blocks_data[child] = False
                                else:
                                    if child_data['weight'] == 0:
                                        non_graded_completed += 1
                                        problem_blocks_data[child] = False
                                    else:
                                        problem_grade = subsection_grade_factory.update(
                                            subsection_structure[child], persist_grade=False
                                        )
                                        if problem_grade.all_total.possible == 0:
                                            non_graded_completed += 1
                                            problem_blocks_data[child] = False
                                        else:
                                            graded_completed += 1
                                            problem_blocks_data[child] = True
                        else:
                            pass
                    else:
                        completed = False
                if completed:
                    unit_completed += 1
                    unit_completion_event = LeaderboardActivityLog.objects.filter(
                        user_id=user.id,
                        event_type="unit_completion",
                        block_key=block_id
                    )
                    if unit_completion_event.exists():
                        pass
                    else:
                        LeaderboardActivityLog.objects.create(
                            user_id=user.id,
                            event_type="unit_completion",
                            block_key=block_id,
                            course_key=course_key,
                            event_time=timezone.now()
                        )
        reports = LearnerVisitsDailyReport.objects.filter(user=user, org__isnull=False)
        daily_visit_reports = reports.values("created").annotate(total=Sum("time_spent"))
        stayed_online = daily_visit_reports.filter(total__gte=1800).count()
        if reports:
            query = reports.aggregate(Max("modified"))
            last_online_check = query["modified__max"]
        else:
            last_online_check = ReportLog.objects.latest().learner_visit

        LeaderboardActivityLog.objects.update_or_create(
            user_id=user.id,
            event_type="online_check",
            defaults={
                "user_id": user.id,
                "event_type": "online_check",
                "event_time": last_online_check
            }
        )

        obj, created = cls.objects.update_or_create(
            user=user,
            defaults={
                'first_login': first_login,
                'first_course_opened': first_course_opened,
                'stayed_online': stayed_online,
                'unit_completed': unit_completed,
                'non_graded_completed': non_graded_completed,
                'graded_completed': graded_completed,
                'course_completed': course_completed,
                'learning_path_completed': learning_path_completed
            })
        if created:
            logger.info("Created LeaderBoard for user: {}".format(user.id))
        else:
            logger.info("Updated LeaderBoard for user: {}".format(user.id))

    @classmethod
    def init_all(cls):
        try:
            analytics_worker = User.objects.get(username=ANALYTICS_WORKER_USER)
        except User.DoesNotExist:
            analytics_worker = create_analytics_worker()
        users = User.objects.filter(is_active=True)
        total = len(users)
        counter = 0
        for user in users:
            counter += 1
            try:
                cls.init_user(user, analytics_worker)
                if counter % 500 == 0 or counter == total:
                    logger.info("{x} / {y} finished".format(x=counter, y=total))
            except Exception as e:
                logger.error("Error initiating leaderboard for User: {user_id}, reason: {reason}".format(
                    user_id=user.id, reason=e
                ))

    @classmethod
    def update_stayed_online(cls):
        users = User.objects.filter(is_active=True)
        for user in users:
            tracking_log = LeaderboardActivityLog.objects.filter(
                user_id=user.id,
                event_type="online_check"
            )
            if tracking_log:
                last_check = tracking_log.last().event_time
                new_reports = LearnerVisitsDailyReport.objects.filter(
                    user=user, modified__gt=last_check, org__isnull=False
                )
            else:
                new_reports = LearnerVisitsDailyReport.objects.filter(user=user, org__isnull=False)

            annotation_reports = new_reports.values("created").annotate(total=Sum("time_spent"))
            stayed_online = annotation_reports.filter(total__gte=1800).count()

            if new_reports:
                query = new_reports.aggregate(Max("modified"))
                last_online_check = query["modified__max"]
            else:
                last_online_check = ReportLog.objects.latest().learner_visit

            LeaderboardActivityLog.objects.update_or_create(
                user_id=user.id,
                event_type="online_check",
                defaults={
                    "user_id": user.id,
                    "event_type": "online_check",
                    "event_time": last_online_check
                }
            )

            leader_board, _ = LeaderBoard.objects.get_or_create(user=user)
            leader_board.stayed_online = leader_board.stayed_online + stayed_online
            leader_board.save()
            logger.info("online_check updated for user: {user_id}, last_check: {last}".format(
                user_id=user.id,
                last=last_online_check
            ))


class LeaderBoardView(models.Model):
    id = models.BigIntegerField(primary_key=True)
    user = models.OneToOneField(User, db_index=True, on_delete=models.DO_NOTHING)
    total_score = models.PositiveIntegerField()
    current_week_score = models.PositiveIntegerField()
    current_month_score = models.PositiveIntegerField()
    last_week_rank = models.PositiveIntegerField()
    last_month_rank = models.PositiveIntegerField()
    last_updated = models.DateTimeField()

    class Meta(object):
        app_label = "triboo_analytics"
        db_table = "triboo_analytics_leaderboardview"
        managed = False

    def __str__(self):
        return "LeaderBoardView of user: {user_id}, total_score: {total_score}, current_week_score: " \
               "{current_week_score}, current_month_score: {current_month_score}, last_week_rank: {last_week_rank}," \
               "last_month_rank: {last_month_rank}".format(
                user_id=self.user_id,
                total_score=self.total_score,
                current_week_score=self.current_week_score,
                current_month_score=self.current_month_score,
                last_week_rank=self.last_week_rank,
                last_month_rank=self.last_month_rank
                )

    def get_leaderboard_detail(self):
        obj = LeaderBoard.objects.get(id=self.id)
        data = {
            'first_login': obj.first_login,
            'everyday_least_30': obj.stayed_online,
            'answering_non_graded': obj.non_graded_completed,
            'answering_graded': obj.graded_completed,
            'unit_completed': obj.unit_completed,
            'accessing_first_course': obj.first_course_opened,
            'course_completed': obj.course_completed,
            'learning_path_completed': obj.learning_path_completed
        }
        return data

    @classmethod
    def calculate_last_week_rank(cls):
        query_set = cls.objects.all()
        weekly_rank = 0
        for i in query_set.order_by("-current_week_score"):
            weekly_rank += 1
            logger.info("update last week rank of user: {user_id}, from {old_rank} ==> {new_rank}".format(
                user_id=i.user_id,
                old_rank=i.last_week_rank,
                new_rank=weekly_rank
            ))
            LeaderBoard.objects.filter(id=i.id).update(last_week_rank=weekly_rank, last_week_score=i.total_score)

    @classmethod
    def calculate_last_month_rank(cls):
        query_set = cls.objects.all()
        monthly_rank = 0
        for i in query_set.order_by("-current_month_score"):
            monthly_rank += 1
            logger.info("update last month rank of user: {user_id}, from {old_rank} ==> {new_rank}".format(
                user_id=i.user_id,
                old_rank=i.last_month_rank,
                new_rank=monthly_rank
            ))
            LeaderBoard.objects.filter(id=i.id).update(last_month_rank=monthly_rank, last_month_score=i.total_score)
