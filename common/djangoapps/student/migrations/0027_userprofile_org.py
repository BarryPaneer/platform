# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2021-05-26 09:44
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('student', '0026_userprofile_service_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='org',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
    ]
