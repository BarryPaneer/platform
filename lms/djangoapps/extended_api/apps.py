# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig

from openedx.core.djangoapps.plugins.constants import ProjectType, PluginURLs


class EdxExtendedApiConfig(AppConfig):
    name = 'extended_api'
    verbose_name = "Edx extended API"

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: 'extended_api',
                PluginURLs.APP_NAME: 'extended_api',
                PluginURLs.REGEX: '',
                PluginURLs.RELATIVE_PATH: 'urls',
            }
        }
    }
