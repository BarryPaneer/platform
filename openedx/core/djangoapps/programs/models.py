"""Models providing Programs support for the LMS and Studio."""

from config_models.models import ConfigurationModel, cache
from django.db import models
from django.utils.translation import ugettext_lazy as _


class ProgramsApiConfig(ConfigurationModel):
    """This model no longer fronts an API, but now sets a few config-related values for the idea of programs in general.

        A rename to ProgramsConfig would be more accurate, but costly in terms of developer time.

        Ref class: /edx/app/edxapp/venvs/edxapp/local/lib/python2.7/site-packages/config_models/models.py
    """
    class Meta(object):
        app_label = "programs"

    marketing_path = models.CharField(
        max_length=255,
        blank=True,
        help_text=_(
            'Path used to construct URLs to programs marketing pages (e.g., "/foo").'
        )
    )
    enable_student_dashboard = models.BooleanField(
        default=False,
        verbose_name=_("Enable Student Dashboard Displays")
    )

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        """
        Clear the cached value when saving a new configuration entry
        """
        super(ConfigurationModel, self).save(
            force_insert,
            force_update,
            using,
            update_fields
        )
        cache.delete(self.cache_key_name(*[getattr(self, key) for key in self.KEY_FIELDS]))
        if self.KEY_FIELDS:
            cache.delete(self.key_values_cache_key_name())

    @classmethod
    def is_student_dashboard_enabled(cls):
        """
        Indicate whether LMS dashboard functionality related to Programs should
        be enabled or not.
        """
        return cls.is_enabled() and cls.current().enable_student_dashboard
