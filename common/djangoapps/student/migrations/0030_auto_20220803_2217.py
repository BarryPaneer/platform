# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2022-08-04 02:17
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import openedx.core.djangolib.model_mixins


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('student', '0029_courseenrollment_enrolled_datetime'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProgramEnrollmentAllowed',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.CharField(db_index=True, max_length=255)),
                ('program_id', models.UUIDField(db_index=True)),
                ('auto_enroll', models.BooleanField(default=0)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True, null=True)),
                ('user', models.ForeignKey(blank=True, help_text=b"First user which enrolled in the specified course through the specified e-mail. Once set, it won't change.", null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            bases=(openedx.core.djangolib.model_mixins.DeletableByUserValue, models.Model),
        ),
        migrations.AlterUniqueTogether(
            name='programenrollmentallowed',
            unique_together=set([('email', 'program_id')]),
        ),
    ]
