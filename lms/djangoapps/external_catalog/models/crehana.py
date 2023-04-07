"""
    Crehana catalog data models
"""
from django.db import models


class CrehanaLanguage(models.Model):
    language_id = models.IntegerField(primary_key=True, null=False)
    language = models.CharField(max_length=64, db_index=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now_add=True, db_index=True, null=True)


class CrehanaResource(models.Model):
    resource_id = models.IntegerField(primary_key=True, null=False)
    title = models.TextField(null=False)
    duration = models.IntegerField(default=0, null=True)
    languages = models.CharField(max_length=128, null=True)
    description = models.TextField(null=True, blank=True)
    image = models.CharField(max_length=1024, null=True)
    url = models.CharField(max_length=2048, null=True)
    rating = models.FloatField(default=None, null=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True, null=True)

    class Meta:
        ordering = ['title']

    def __unicode__(self):
        return u'{} - {}'.format(self.resource_id, self.title)
