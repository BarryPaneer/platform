# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-08-15 07:41
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('student', '0019_waiverrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='lt_ilt_supervisor',
            field=models.TextField(blank=True, null=True, verbose_name=b'ILT Supervisor'),
        ),
    ]
