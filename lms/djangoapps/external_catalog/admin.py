from django.contrib import admin

from .models import EdflexCategory, EdflexResource

admin.site.register([EdflexCategory, EdflexResource])
