"""Anders pink catalog data models
"""
from django.db import models


class AndersPinkBriefing(models.Model):
    briefing_id = models.IntegerField(null=True, blank=True)
    name = models.TextField(null=False)
    
    class Meta:
        ordering = ['name']

    def __unicode__(self):
        return u'{} - {}'.format(self.briefing_id, self.name)


class AndersPinkBoard(models.Model):
    board_id = models.IntegerField(null=True, blank=True)
    name = models.TextField(null=False)

    class Meta:
        ordering = ['name']

    def __unicode__(self):
        return u'{} - {}'.format(self.board_id, self.name)
    

class AndersPinkArticle(models.Model):
    title_id = models.IntegerField(null=True, blank=True)
    briefing_id = models.ForeignKey(AndersPinkBriefing, blank=True, null=True)
    board_id = models.ForeignKey(AndersPinkBoard, blank=True, null=True)
    title = models.TextField(null=True)
    image = models.CharField(max_length=1024, null=True)
    date_published = models.DateTimeField(auto_now_add=True, db_index=True, null=True)
    url = models.CharField(max_length=2048, null=True)
    author = models.TextField(null=True)
    reading_time = models.IntegerField(default=0, null=True)
    language = models.CharField(max_length=128, null=True)

    class Meta:
        ordering = ['title']

    def __unicode__(self):
        return u'{} - {}'.format(self.title_id, self.title)
