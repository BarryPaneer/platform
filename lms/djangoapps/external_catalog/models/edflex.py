"""
External catalog used for "find courses" page.
"""

from django.db import models


class EdflexCategory(models.Model):
    category_id = models.CharField(max_length=255)
    language = models.CharField(default='en', max_length=255)
    name = models.CharField(max_length=255)
    created = models.DateTimeField(auto_now_add=True, db_index=True, null=True)
    modified = models.DateTimeField(auto_now=True, db_index=True, null=True)

    def __unicode__(self):
        return u'{} - {} ({})'.format(self.category_id, self.name, self.language)


class EdflexResource(models.Model):
    resource_id = models.CharField(max_length=255, unique=True)
    title = models.TextField()
    type = models.CharField(max_length=255, db_index=True)
    language = models.CharField(max_length=255, db_index=True, null=True)
    url = models.URLField(max_length=1024, null=True, blank=True)
    duration = models.CharField(max_length=255, null=True, blank=True)
    publication_date = models.DateTimeField(default=None, null=True, blank=True)
    image_url = models.URLField(max_length=1024)
    rating = models.FloatField(default=None, null=True, blank=True)
    categories = models.ManyToManyField(EdflexCategory, related_name='resources')
    created = models.DateTimeField(auto_now_add=True, db_index=True, null=True)
    modified = models.DateTimeField(auto_now=True, db_index=True, null=True)

    class Meta:
        ordering = ['-publication_date', 'title']

    def __unicode__(self):
        return u'{} - {}'.format(self.resource_id, self.title)


class EdflexSelection(models.Model):
    selection_id = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    publication_date = models.DateTimeField(default=None, null=True, blank=True)
    items = models.TextField()
    created = models.DateTimeField(auto_now_add=True, db_index=True, null=True)
    modified = models.DateTimeField(auto_now=True, db_index=True, null=True)
