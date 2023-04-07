# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db.models import Q
from track.backends.django import EVENT_TYPE_BLACK_LIST, TrackingLog


query = Q()
for i in EVENT_TYPE_BLACK_LIST:
    query = query | Q(event_type__startswith=i)


def regular_delete():
    logs = TrackingLog.objects.filter(query)
    logs.delete()


def raw_delete():
    logs = TrackingLog.objects.filter(query)
    logs._raw_delete(logs.db)
