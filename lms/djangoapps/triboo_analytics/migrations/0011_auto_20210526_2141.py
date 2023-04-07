# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-05-27 01:41
from __future__ import unicode_literals

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import opaque_keys.edx.django.models
import triboo_analytics.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('triboo_analytics', '0010_auto_20210117_2124'),
    ]

    operations = [
        migrations.CreateModel(
            name='Badge',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('course_id', opaque_keys.edx.django.models.CourseKeyField(db_index=True, max_length=255)),
                ('badge_hash', models.CharField(db_index=True, max_length=100)),
                ('order', models.PositiveSmallIntegerField(default=0)),
                ('grading_rule', models.CharField(max_length=255)),
                ('section_name', models.CharField(max_length=255)),
                ('threshold', models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MaxValueValidator(100)])),
            ],
        ),
        migrations.CreateModel(
            name='LearnerBadgeJsonReport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('score', models.FloatField(blank=True, default=0, null=True)),
                ('success', models.BooleanField(default=False)),
                ('success_date', models.DateTimeField(blank=True, default=None, null=True)),
                ('records', models.TextField(default='{}')),
                ('is_active', models.BooleanField(default=True)),
                ('badge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='triboo_analytics.Badge')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            bases=(triboo_analytics.models.JsonReportMixin, models.Model),
        ),
        migrations.CreateModel(
            name='LearnerBadgeSuccess',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('success_date', models.DateTimeField(blank=True, default=None, null=True)),
                ('badge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='triboo_analytics.Badge')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='LearnerCourseJsonReport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('course_id', opaque_keys.edx.django.models.CourseKeyField(db_index=True, max_length=255)),
                ('org', models.CharField(db_index=True, max_length=255)),
                ('status', models.PositiveSmallIntegerField(default=0, help_text='not started: 0; in progress: 1; finished: 2; failed: 3; ')),
                ('progress', models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MaxValueValidator(100)])),
                ('badges', models.CharField(default='0 / 0', max_length=20)),
                ('current_score', models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MaxValueValidator(100)])),
                ('posts', models.PositiveIntegerField(default=0)),
                ('total_time_spent', models.PositiveIntegerField(default=0)),
                ('enrollment_date', models.DateTimeField(blank=True, default=None, null=True)),
                ('completion_date', models.DateTimeField(blank=True, default=None, null=True)),
                ('records', models.TextField(default='{}')),
                ('is_active', models.BooleanField(default=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            bases=(triboo_analytics.models.JsonReportMixin, models.Model),
        ),
        migrations.CreateModel(
            name='LearnerSectionJsonReport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('course_id', opaque_keys.edx.django.models.CourseKeyField(db_index=True, max_length=255)),
                ('section_key', models.CharField(max_length=100)),
                ('section_name', models.CharField(max_length=512)),
                ('total_time_spent', models.PositiveIntegerField(default=0)),
                ('records', models.TextField(default='{}')),
                ('is_active', models.BooleanField(default=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            bases=(triboo_analytics.models.JsonReportMixin, models.Model),
        ),
        migrations.AddField(
            model_name='coursedailyreport',
            name='unique_visitors',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterUniqueTogether(
            name='badge',
            unique_together=set([('course_id', 'badge_hash')]),
        ),
        migrations.AlterIndexTogether(
            name='badge',
            index_together=set([('course_id', 'badge_hash')]),
        ),
        migrations.AlterUniqueTogether(
            name='learnersectionjsonreport',
            unique_together=set([('user', 'course_id', 'section_key')]),
        ),
        migrations.AlterIndexTogether(
            name='learnersectionjsonreport',
            index_together=set([('user', 'course_id', 'section_key'), ('course_id', 'user')]),
        ),
        migrations.AlterUniqueTogether(
            name='learnercoursejsonreport',
            unique_together=set([('user', 'course_id')]),
        ),
        migrations.AlterIndexTogether(
            name='learnercoursejsonreport',
            index_together=set([('org', 'status'), ('user', 'course_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='learnerbadgesuccess',
            unique_together=set([('user', 'badge')]),
        ),
        migrations.AlterIndexTogether(
            name='learnerbadgesuccess',
            index_together=set([('user', 'badge')]),
        ),
        migrations.AlterUniqueTogether(
            name='learnerbadgejsonreport',
            unique_together=set([('user', 'badge')]),
        ),
        migrations.AlterIndexTogether(
            name='learnerbadgejsonreport',
            index_together=set([('user', 'badge')]),
        ),
    ]
