# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2021-09-08 06:57
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('triboo_analytics', '0011_auto_20210526_2141'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaderboard',
            name='learning_path_completed',
            field=models.PositiveIntegerField(default=0),
        ),
    ]