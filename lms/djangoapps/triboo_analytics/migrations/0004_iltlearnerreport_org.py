# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-09-11 07:06
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('triboo_analytics', '0003_auto_20190904_0251'),
    ]

    operations = [
        migrations.AddField(
            model_name='iltlearnerreport',
            name='org',
            field=models.CharField(db_index=True, default=None, max_length=255, null=True),
        ),
    ]