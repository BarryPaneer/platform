# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import hashlib
import logging
import os
from functools import partial
import json
from celery import task
from celery_utils.persist_on_failure import LoggedPersistOnFailureTask
from completion.models import BlockCompletion
from course_blocks.api import get_course_blocks
from six import text_type
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import datetime
from django_tables2.export import TableExport
from eventtracking import tracker
from lms.djangoapps.grades.subsection_grade_factory import SubsectionGradeFactory
from lms.djangoapps.instructor.enrollment import send_mail_to_student, send_custom_waiver_email
from lms.djangoapps.instructor_task.models import ReportStore
from lms.djangoapps.instructor_task.tasks_base import BaseInstructorTask, TASK_LOG
from lms.djangoapps.instructor_task.tasks_helper.runner import run_main_task
from lms.djangoapps.instructor_task.tasks_helper.utils import REPORT_REQUESTED_EVENT_NAME
from opaque_keys.edx.keys import CourseKey, UsageKey
from student.models import CourseEnrollment
from util.file import course_filename_prefix_generator
from xmodule.modulestore.django import modulestore
from . import models
from . import tables
from django.http import HttpResponseNotFound
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers


logger = logging.getLogger('triboo_analytics')

@task(routing_key=settings.HIGH_PRIORITY_QUEUE)
def send_waiver_request_email(users, kwargs):
    for user in users:
        param_dict = {
            'message': kwargs['email_type'],
            'name': user['name'],
            'sections': kwargs['sections'],
            'course_name': kwargs['course_name'],
            'learner_name': kwargs['learner_name'],
            'username': kwargs['username'],
            'country': kwargs['country'],
            'location': kwargs['location'],
            'description': kwargs['description'],
            'accept_link': kwargs['accept_link'],
            'deny_link': kwargs['deny_link'],
            'platform_name': kwargs['platform_name'],
            'site_name': None
        }
        if kwargs['email_type'] == 'forced_waiver_request':
            param_dict.update({'site_theme': kwargs['site_theme']})
            send_custom_waiver_email(user['email'], param_dict)
        else:
            send_mail_to_student(user['email'], param_dict, language=user['language'])


def path_to(course_key, user_id, filename=''):
    if course_key:
        prefix = hashlib.sha1(text_type(course_key) + str(user_id)).hexdigest()
    else:
        prefix = hashlib.sha1(str(user_id)).hexdigest()
    return os.path.join(prefix, filename)


def links_for_leaderboard(storage, user):
    files = []
    report_dir = path_to("leaderboard_key", user.id)
    _, filenames = storage.listdir(report_dir)
    files.extend([(filename, os.path.join(report_dir, filename)) for filename in filenames])
    files.sort(key=lambda f: storage.modified_time(f[1]), reverse=True)
    return [(filename, storage.url(full_path)) for filename, full_path in files]


def links_for_users(storage, user):
    files = []
    report_dir = path_to("users_key", user.id)
    _, filenames = storage.listdir(report_dir)
    files.extend([(filename, os.path.join(report_dir, filename)) for filename in filenames])
    files.sort(key=lambda f: storage.modified_time(f[1]), reverse=True)
    return [(filename, storage.url(full_path)) for filename, full_path in files]


def links_for_all(storage, user):
    orgs = configuration_helpers.get_current_site_orgs()
    if not orgs:
        return HttpResponseNotFound()
    course_overviews = CourseOverview.objects.none()

    for org in orgs:
        org_course_overviews = CourseOverview.objects.filter(org=org, start__lte=timezone.now())
        course_overviews = course_overviews | org_course_overviews

    course_ids = [o.id for o in course_overviews]
    files = []
    for course_id in course_ids:
        report_dir = path_to(course_id, user.id)
        try:
            _, filenames = storage.listdir(report_dir)
            for filename in filenames:
                files.append((filename, os.path.join(report_dir, filename)))
        except OSError:
            pass

    report_dir = path_to(None, user.id)
    try:
        _, filenames = storage.listdir(report_dir)
        for filename in filenames:
            files.append((filename, os.path.join(report_dir, filename)))
    except OSError:
        pass

    files.sort(key=lambda f: storage.modified_time(f[1]), reverse=True)
    return [(filename, storage.url(full_path)) for filename, full_path in files]


def upload_file_to_store(user_id, course_key, filename, export_format, content, username=None):
    report_store = ReportStore.from_config('TRIBOO_ANALYTICS_REPORTS')
    if filename == "transcript":
        _filename = "{}_{}_{}.{}".format(filename,
                                         username,
                                         timezone.now().strftime("%Y-%m-%d-%H%M"),
                                         export_format)
    else:
        _filename = "{}_{}.{}".format(filename,
                                      timezone.now().strftime("%Y-%m-%d-%H%M"),
                                      export_format)
        if course_key:
            _filename = "{}_{}".format(course_filename_prefix_generator(course_key),
                                  _filename)
        if not course_key and filename.startswith('summary'):
            _filename = "{}_{}_{}.{}".format('course',
                                             filename,
                                             timezone.now().strftime("%Y-%m-%d-%H%M"),
                                             export_format)

    if filename.startswith("Leaderboard"):
        path = path_to("leaderboard_key", user_id, _filename)
    elif filename.startswith("users"):
        path = path_to("users_key", user_id, _filename)
    else:
        path = path_to(course_key, user_id, _filename)
    report_store.store_content(
        path,
        content
    )
    tracker.emit(REPORT_REQUESTED_EVENT_NAME, {"report_type": _filename})


def convert_period_format(kwargs):
    date_tuple = json.loads(kwargs['start__range'])
    from_date = pytz.utc.localize(datetime.strptime(date_tuple[0], "%Y-%m-%d %H:%M:%S %Z"))
    to_date = pytz.utc.localize(datetime.strptime(date_tuple[1], "%Y-%m-%d %H:%M:%S %Z"))
    kwargs['start__range'] = (from_date, to_date)
    return kwargs


def upload_export_table(_xmodule_instance_args, _entry_id, course_id, _task_input, action_name):
    from .views import (
        get_transcript_table,
        get_table_data,
        get_progress_table_data,
        get_time_spent_table_data,
        get_ilt_global_table_data,
        get_ilt_learner_table_data,
        get_customized_table,
    )

    if not TableExport.is_valid_format(_task_input['export_format']):
        raise UnsupportedExportFormatError()

    table = []

    if _task_input['report_name'] != "transcript":
        kwargs = _task_input['report_args']['filter_kwargs']
        exclude = _task_input['report_args']['exclude']

        if 'to_date' in kwargs.keys():
            kwargs['to_date'] = datetime.strptime(kwargs['to_date'], "%Y-%m-%d").date()
        if 'from_date' in kwargs.keys():
            kwargs['from_date'] = datetime.strptime(kwargs['from_date'], "%Y-%m-%d").date()

        if 'course_id' in kwargs.keys():
            kwargs['course_id'] = CourseKey.from_string(kwargs['course_id'])

    if _task_input['report_name'] in ["summary_report", "learner_report"]:
        report_cls = getattr(models, _task_input['report_args']['report_cls'])
        table_cls = getattr(tables, _task_input['report_args']['table_cls'])
        logger.info("ANALYTICS -- export course summary report or learner > call get_table_data")
        table = get_table_data(report_cls, table_cls, kwargs, exclude, by_period=True)

    elif _task_input['report_name'] == "progress_report":
        logger.info("ANALYTICS -- export course progress report > call get_table_data")
        table, _ = get_progress_table_data(kwargs['course_id'], kwargs, exclude)

    elif _task_input['report_name'] == "time_spent_report":
        logger.info("ANALYTICS -- export course time spent report > call get_table_data")
        kwargs['multiprocessing_mode'] = True
        table, _ = get_time_spent_table_data(kwargs['course_id'], kwargs, exclude)

    elif _task_input['report_name'] == "ilt_global_report":
        table = get_ilt_global_table_data(kwargs)

    elif _task_input['report_name'] == "ilt_learner_report":
        logger.info("ANALYTICS -- export ilt report > call get_table_data")
        table = get_ilt_learner_table_data(kwargs, exclude)

    elif _task_input['report_name'] == "transcript":
        if _task_input['report_args']['last_update'].endswith('UTC'):
            datetime_format = "%Y-%m-%d %H:%M:%S UTC"
        else:
            datetime_format = "%Y-%m-%d"
        table, _ = get_transcript_table(_task_input['report_args']['orgs'],
                                        _task_input['report_args']['user_id'],
                                        datetime.strptime(_task_input['report_args']['last_update'], datetime_format))

    elif _task_input['report_name'] == "summary_report_multiple":
        logger.info("ANALYTICS -- export course summary MULTIPLE report > call get_table_data")
        report_cls = getattr(models, _task_input['report_args']['report_cls'])
        table_cls = getattr(tables, _task_input['report_args']['table_cls'])
        courses_selected = _task_input['report_args'].get('courses_selected', None)
        course_keys = [CourseKey.from_string(_id) for _id in courses_selected.split(',')]
        kwargs['course_id__in'] = course_keys
        logger.info("ANALYTICS -- export course summary MULTIPLE report > call get_table_data")
        table, _ = get_customized_table(report_cls, kwargs, table_cls, exclude)

    logger.info("ANALYTICS -- about to export")
    exporter = TableExport(_task_input['export_format'], table)
    content = exporter.export()

    if _task_input['export_format'] == "json":
        content = json.dumps(json.loads(content), ensure_ascii=False, encoding='utf-8').encode('utf-8')

    if _task_input['report_name'] == "transcript":
        upload_file_to_store(_task_input['user_id'],
                             course_id,
                             _task_input['report_name'],
                             _task_input['export_format'],
                             content,
                             _task_input['report_args']['username'])
    else:
        if _task_input['report_name'] == 'summary_report_multiple':
            _task_input['report_name'] = 'summary_report'
        logger.info("ANALYTICS -- about to upload file %s" % _task_input['report_name'])
        upload_file_to_store(_task_input['user_id'],
                             course_id,
                             _task_input['report_name'],
                             _task_input['export_format'],
                             content)


@task(
    base=BaseInstructorTask,
    routing_key=settings.HIGH_PRIORITY_QUEUE
)  # pylint: disable=not-callable
def generate_export_table(entry_id, xmodule_instance_args):
    action_name = 'triboo_analytics_exported'
    TASK_LOG.info(
        u"Task: %s, Triboo Analytics Task ID: %s, Task type: %s, Preparing for task execution",
        xmodule_instance_args.get('task_id'), entry_id, action_name
    )

    task_fn = partial(upload_export_table, xmodule_instance_args)
    return run_main_task(entry_id, task_fn, action_name)


@task(
    base=LoggedPersistOnFailureTask,
    routing_key=settings.HIGH_PRIORITY_QUEUE
)
def generate_leaderboard_report_task(period, user_id, username, file_format, orgs):
    from .views import _leaderboard_data
    data = _leaderboard_data(request=None, period=period, orgs=orgs)
    data_table = tables.LeaderboardTable(data['list'])
    exporter = TableExport(file_format, data_table)
    content = exporter.export()
    if period in ['month', 'week']:
        file_name = "Leaderboard_{} Ranking".format(period.capitalize())
    else:
        file_name = "Leaderboard_All"
    upload_file_to_store(user_id,
                         "",
                         file_name,
                         file_format,
                         content,
                         username)


@task(
    base=LoggedPersistOnFailureTask,
    routing_key=settings.HIGH_PRIORITY_QUEUE
)
def generate_users_list_report_task(user_id, username, file_format, orgs, exclude_columns):
    from .views import users_list_export_table
    data_table = users_list_export_table(orgs)
    exporter = TableExport(file_format, data_table, exclude_columns=exclude_columns)
    content = exporter.export()
    upload_file_to_store(user_id,
                         "",
                         "users_list",
                         file_format,
                         content,
                         username)


@receiver(post_save, sender=BlockCompletion)
def handle_leader_board_activity(sender, instance, **kwargs):

    update_leader_board_activity.apply_async(
        kwargs={
            "block_id": unicode(instance.block_key),
            "user_id": instance.user_id,
            "completion": instance.completion
        }
    )


@task(
    bind=True,
    base=LoggedPersistOnFailureTask,
    time_limit=300,
    max_retries=3,
    default_retry_delay=10,
    routing_key=settings.RECALCULATE_LEADERBOARD_ROUTING_KEY
)
def update_leader_board_activity(self, **kwargs):
    try:
        logger.info("#### {} #####".format(kwargs.get('block_id')))
        block_key = UsageKey.from_string(kwargs.get('block_id'))
        user = User.objects.get(id=kwargs.get('user_id'))
        block = modulestore().get_item(block_key)
        leader_board = None
        completion = kwargs.get('completion')
        if completion == 1:
            offset = 1
        else:
            offset = -1
        if block_key.block_type in ['survey', 'poll', 'word_cloud']:
            leader_board, _ = models.LeaderBoard.objects.get_or_create(user=user)
            leader_board.non_graded_completed = leader_board.non_graded_completed + offset
            logger.info("updated non_graded activity of leaderboard score by ({offset}) for user: {user_id}, "
                        "block_id: {block_id}".format(
                            user_id=user.id,
                            block_id=block_key,
                            offset=offset
                        ))
            leader_board.save()
        elif block_key.block_type == 'problem':
            leader_board, _ = models.LeaderBoard.objects.get_or_create(user=user)
            if not block.graded:
                leader_board.non_graded_completed = leader_board.non_graded_completed + offset
                logger.info(
                    "updated non_graded activity of leaderboard score by ({offset}) for user: {user_id}, "
                    "block_id: {block_id}".format(
                        user_id=user.id,
                        block_id=block_key,
                        offset=offset
                    ))
            else:
                if block.weight == 0:
                    leader_board.non_graded_completed = leader_board.non_graded_completed + offset
                    logger.info(
                        "updated non_graded activity of leaderboard score by ({offset}) for user: {user_id}, "
                        "block_id: {block_id}".format(
                            user_id=user.id,
                            block_id=block_key,
                            offset=offset
                        ))
                else:
                    course_structure = get_course_blocks(user, block_key)
                    subsection_grade_factory = SubsectionGradeFactory(user, course_structure=course_structure)
                    subsection_grade = subsection_grade_factory.update(
                        course_structure[block_key], persist_grade=False
                    )
                    if subsection_grade.all_total.possible == 0:
                        leader_board.non_graded_completed = leader_board.non_graded_completed + offset
                        logger.info(
                            "updated non_graded activity of leaderboard score by ({offset}) for user: {user_id}, "
                            "block_id: {block_id}".format(
                                user_id=user.id,
                                block_id=block_key,
                                offset=offset
                            ))
                    else:
                        leader_board.graded_completed = leader_board.graded_completed + offset
                        logger.info(
                            "updated graded activity of leaderboard score by ({offset}) for user: {user_id}, "
                            "block_id: {block_id}".format(
                                user_id=user.id,
                                block_id=block_key,
                                offset=offset
                            )
                        )

            leader_board.save()

        vertical_block = modulestore().get_item(block.parent)
        if block.parent.block_type == "library_content":
            vertical_block = modulestore().get_item(vertical_block.parent)

        unit_completion_event = models.LeaderboardActivityLog.objects.filter(
            user_id=user.id,
            event_type="unit_completion",
            block_key=vertical_block.location
        )
        if not unit_completion_event.exists():
            # if the block completion is reset to 0 and parent block was not completed before
            # then just do nothing, just return, else we need to reset the unit completion
            if completion == 0:
                return
            course_block_completions = BlockCompletion.get_course_completions(user, block_key.course_key)
            children = vertical_block.children
            for child in children[:]:
                if child.block_type == 'library_content':
                    lib_content_block = get_course_blocks(user, child)
                    extra_children = [i for i in lib_content_block if i.block_type != 'library_content']
                    children.extend(extra_children)
            if children:
                completed = True
            else:
                completed = False
            for child in children:
                if child.block_type in ['discussion', 'library_content'] or child == block_key:
                    continue
                completion = course_block_completions.get(child, None)
                if not completion:
                    logger.info("#### {} ##### not completed".format(child))
                    completed = False
                    break
            if completed:
                cache_key = "{user_id}_{key}".format(user_id=user.id, key=unicode(block.parent))
                if cache.get(cache_key) is None:
                    cache.add(cache_key, "completed", 300)
                    if leader_board is None:
                        leader_board, _ = models.LeaderBoard.objects.get_or_create(user=user)
                    leader_board.unit_completed = leader_board.unit_completed + 1
                    leader_board.save()
                    logger.info("updated unit completed of leaderboard score for user: {user_id}, "
                                "block_id: {block_id}".format(
                                    user_id=user.id,
                                    block_id=vertical_block.location
                                ))
                    models.LeaderboardActivityLog.objects.create(
                        user_id=user.id,
                        event_type="unit_completion",
                        event_time=timezone.now(),
                        block_key=vertical_block.location,
                        course_key=block_key.course_key
                    )
                else:
                    logger.info("user: {user_id}, cache key is found; unit is already completed, {key}".format(
                        user_id=user.id,
                        key=vertical_block.location
                    ))
        else:
            if completion == 0:
                unit_completion_event.delete()
                leader_board.unit_completed = leader_board.unit_completed - 1
                leader_board.save()
                logger.info("remove unit completion for user: {user_id}, "
                            "block_id: {block_id}".format(
                                user_id=user.id,
                                block_id=vertical_block.location
                            ))
            else:
                logger.info("user: {user_id}, unit is already completed, {key}".format(
                    user_id=user.id,
                    key=vertical_block.location
                ))
    except Exception as e:
        self.retry(kwargs=kwargs, exc=e)
