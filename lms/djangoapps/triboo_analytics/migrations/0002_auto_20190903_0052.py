# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-09-03 04:52
from __future__ import unicode_literals

import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import opaque_keys.edx.django.models
import triboo_analytics.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('triboo_analytics', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='IltLearnerReport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', triboo_analytics.models.AutoCreatedField(default=datetime.date.today, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Accepted', 'Accepted'), ('Confirmed', 'Confirmed'), ('Refused', 'Refused')], max_length=9)),
                ('attendee', models.BooleanField(default=False)),
                ('outward_trips', models.PositiveSmallIntegerField(default=0)),
                ('return_trips', models.PositiveSmallIntegerField(default=0)),
                ('accommodation', models.BooleanField(default=False)),
                ('comment', models.TextField(blank=True, default=None, null=True)),
                ('hotel', models.TextField(blank=True, default=None, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='IltModule',
            fields=[
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('id', opaque_keys.edx.django.models.UsageKeyField(db_index=True, max_length=255, primary_key=True, serialize=False)),
                ('course_id', opaque_keys.edx.django.models.CourseKeyField(max_length=255)),
                ('course_display_name', models.TextField()),
                ('course_tags', models.TextField(blank=True, null=True)),
                ('chapter_display_name', models.TextField(blank=True, null=True)),
                ('section_display_name', models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='IltSession',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('session_nb', models.PositiveSmallIntegerField(null=True)),
                ('start', models.DateTimeField(blank=True, default=None, null=True)),
                ('end', models.DateTimeField(blank=True, default=None, null=True)),
                ('duration', models.PositiveSmallIntegerField(default=0)),
                ('seats', models.PositiveSmallIntegerField(default=0)),
                ('ack_attendance_sheet', models.BooleanField(default=False)),
                ('location_id', models.TextField(blank=True, default=None, null=True)),
                ('location', models.TextField(blank=True, default=None, null=True)),
                ('address', models.TextField(blank=True, default=None, null=True)),
                ('zip_code', models.TextField(blank=True, default=None, null=True)),
                ('city', models.TextField(blank=True, default=None, null=True)),
                ('area', models.TextField(blank=True, default=None, null=True)),
                ('org', models.CharField(db_index=True, default=None, max_length=255, null=True)),
                ('enrollees', models.PositiveSmallIntegerField(default=0)),
                ('attendees', models.PositiveSmallIntegerField(default=0)),
                ('ilt_module', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='triboo_analytics.IltModule')),
            ],
        ),
        migrations.AddField(
            model_name='iltlearnerreport',
            name='ilt_module',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='triboo_analytics.IltModule'),
        ),
        migrations.AddField(
            model_name='iltlearnerreport',
            name='ilt_session',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='triboo_analytics.IltSession'),
        ),
        migrations.AddField(
            model_name='iltlearnerreport',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='iltsession',
            unique_together=set([('ilt_module', 'session_nb')]),
        ),
        migrations.AlterIndexTogether(
            name='iltsession',
            index_together=set([('ilt_module', 'session_nb')]),
        ),
        migrations.AlterUniqueTogether(
            name='iltlearnerreport',
            unique_together=set([('ilt_module', 'user')]),
        ),
        migrations.AlterIndexTogether(
            name='iltlearnerreport',
            index_together=set([('ilt_module', 'user')]),
        ),
    ]
