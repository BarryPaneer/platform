"""
Event tracker backend that saves events to a Django database.

"""

# TODO: this module is very specific to the event schema, and is only
# brought here for legacy support. It should be updated when the
# schema changes or eventually deprecated.

from __future__ import absolute_import

import logging
import re
from django.db import models
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from track.backends import BaseBackend
from opaque_keys.edx.django.models import CourseKeyField
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from django.contrib.auth.models import User


log = logging.getLogger('track.backends.django')


LOGFIELDS = [
    'user_id',
    'username',
    'ip',
    'event_source',
    'event_type',
    'event',
    'agent',
    'page',
    'time',
    'host',
]

EVENT_TYPE_BLACK_LIST = [
    '/analytics/list_table_downloads/',
    '/media/',
    '/xblock/resources/',
    'edx.',
    'xblock.',
    'showanswer',
    'problem_check'
]


class TrackingLog(models.Model):
    """Defines the fields that are stored in the tracking log database."""

    dtcreated = models.DateTimeField('creation date', auto_now_add=True)
    user_id = models.PositiveIntegerField(default=None, null=True)
    username = models.CharField(max_length=150, blank=True)
    ip = models.CharField(max_length=32, blank=True)
    event_source = models.CharField(max_length=32)
    event_type = models.CharField(max_length=512, blank=True)
    event = models.TextField(blank=True)
    agent = models.CharField(max_length=256, blank=True)
    page = models.CharField(max_length=512, blank=True, null=True)
    time = models.DateTimeField('event time', db_index=True)
    host = models.CharField(max_length=64, blank=True)
    time_spent = models.FloatField(default=None, null=True, blank=True)
    section = models.CharField(max_length=100, default=None, null=True, blank=True)

    course_id_pattern = re.compile('^/courses/.+')
    device_pattern = re.compile('Android|iPhone|iPad')

    class Meta(object):
        app_label = 'track'
        db_table = 'track_trackinglog'
        index_together = ['user_id', 'section', 'time']

    def __unicode__(self):
        fmt = (
            u"[{self.time}] {self.username}@{self.ip}: "
            u"{self.event_source}| {self.event_type} | "
            u"{self.page} | {self.event}"
        )
        return fmt.format(self=self)

    @property
    def course_id(self):
        prog = self.course_id_pattern.match(self.event_type)
        if prog:
            try:
                course_id = CourseKey.from_string(self.event_type.split('/')[2])
                return course_id
            except InvalidKeyError:
                pass
        return CourseKeyField.Empty


    @property
    def device(self):
        if self.device_pattern.search(self.agent):
            return 'mobile'
        return 'desktop'


class DjangoBackend(BaseBackend):
    """Event tracker backend that saves to a Django database"""
    def __init__(self, name='default', **options):
        """
        Configure database used by the backend.

        :Parameters:

          - `name` is the name of the database as specified in the project
            settings.

        """
        super(DjangoBackend, self).__init__(**options)
        self.name = name

    def send(self, event):
        field_values = {x: event.get(x, '') for x in LOGFIELDS}
        if field_values['user_id']:
            if field_values['event_type']:
                for blacklisted_event_type in EVENT_TYPE_BLACK_LIST:
                    if field_values['event_type'].startswith(blacklisted_event_type):
                        return
            tldat = TrackingLog(**field_values)
            try:
                tldat.save(using=self.name)
            except Exception as e:  # pylint: disable=broad-except
                log.exception(e)


class CourseUnenrollment(models.Model):
    created = models.DateTimeField('unenrollment date', auto_now_add=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(CourseOverview, on_delete=models.CASCADE, db_index=True)

    class Meta(object):
        app_label = 'track'

    def __unicode__(self):
        return (
            "[CourseUnenrollment] {} - {} : {}"
        ).format(self.user, self.course_id, self.created)