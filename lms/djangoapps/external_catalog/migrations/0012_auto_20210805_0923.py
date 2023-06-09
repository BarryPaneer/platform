# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2021-08-05 13:23
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('external_catalog', '0011_auto_20210712_1001'),
    ]

    operations = [
        migrations.CreateModel(
            name='AndersPinkBoard',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('board_id', models.IntegerField(blank=True, null=True)),
                ('name', models.TextField()),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='anderspinkarticle',
            name='board_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='external_catalog.AndersPinkBoard'),
        ),
    ]
