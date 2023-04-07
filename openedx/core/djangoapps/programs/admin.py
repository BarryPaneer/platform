"""
django admin pages for program support models
"""
from config_models.admin import ConfigurationModelAdmin, cache
from django.contrib import admin

from openedx.core.djangoapps.programs.models import ProgramsApiConfig


class ProgramsApiConfigAdmin(ConfigurationModelAdmin):
    """
        Ref class: /edx/app/edxapp/venvs/edxapp/local/lib/python2.7/site-packages/config_models/admin.py
    """
    fields = [
        'enabled',
        'enable_student_dashboard',
        'marketing_path'
    ]
    readonly_fields = ['id']
    object_id = 'id'

    def has_delete_permission(self, request, obj=None):
        return True

    def get_readonly_fields(self, request, obj=None):
        return []

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        return super(ConfigurationModelAdmin, self).change_view(
            request,
            object_id,
            form_url,
            extra_context=extra_context
        )


admin.site.register(ProgramsApiConfig, ProgramsApiConfigAdmin)
