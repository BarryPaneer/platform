# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2021-08-31 10:44
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('programs', '0012_auto_20170419_0018'),
    ]

    operations = [
        migrations.AddField(
            model_name='programsapiconfig',
            name='enable_student_dashboard',
            field=models.BooleanField(default=False, verbose_name='Enable Student Dashboard Displays'),
        ),
    ]