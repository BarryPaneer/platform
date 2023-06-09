"""
Django models for site configurations.
"""
import collections
from logging import getLogger

from django.contrib.sites.models import Site
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from jsonfield.fields import JSONField
from model_utils.models import TimeStampedModel

logger = getLogger(__name__)  # pylint: disable=invalid-name


class SiteConfiguration(models.Model):
    """
    Model for storing site configuration. These configuration override OpenEdx configurations and settings.
    e.g. You can override site name, logo image, favicon etc. using site configuration.

    Fields:
        site (OneToOneField): one to one field relating each configuration to a single site
        values (JSONField):  json field to store configurations for a site
    """
    site = models.OneToOneField(Site, related_name='configuration', on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False, verbose_name="Enabled")
    values = JSONField(
        null=False,
        default='{\n \
            "site_domain":"",\n \
            "course_org_filter":"",\n \
            "show_only_org_on_student_dashboard":true,\n \
            "COURSES_ARE_BROWSABLE":true,\n \
            "SHOW_ILT_CALENDAR":true,\n \
            "logo_image_url":"hawthorn-/images/logo.png",\n \
            "ENABLE_ANALYTICS":true,\n \
            "ENABLE_WAIVER_REQUEST":true,\n \
            "ENABLE_ILT_ANALYTICS":true,\n \
            "ENABLE_FAQ_LINK":true,\n \
            "ENABLE_EDFLEX_CATALOG":false,\n \
            "EDFLEX_URL":"",\n \
            "ENABLE_EDFLEX_REDIRECTION":false,\n \
            "EDFLEX_RENAME":"",\n \
            "ALLOW_PUBLIC_ACCOUNT_CREATION":false,\n \
            "ENABLE_DASHBOARD_BOOKMARKS":false,\n \
            "ENABLE_LAST_ACTIVITY":false,\n \
            "ENABLE_LEADERBOARD":true,\n \
            "ENABLE_ACCOUNT_DELETION":false,\n \
            "SKIP_EMAIL_VALIDATION":false,\n \
            "ANALYTICS_USER_PROPERTIES":{\n  \
                "lt_employee_id":"default",\n  \
                "email":"default",\n  \
                "gender":"option",\n  \
                "country":"default",\n  \
                "lt_area":"default",\n  \
                "lt_sub_area":"default",\n  \
                "city":"default",\n  \
                "location":"default",\n  \
                "lt_address":"option",\n  \
                "lt_address_2":"default",\n  \
                "lt_company":"option",\n  \
                "lt_hire_date":"option",\n  \
                "lt_level":"default",\n  \
                "lt_job_code":"default",\n  \
                "lt_department":"option",\n  \
                "lt_ilt_supervisor":"option"\n \
            },\n \
            "ILT_OPTIONAL_FIELDS":[\n  \
                "area_region",\n  \
                "address",\n  \
                "zip_code",\n  \
                "city",\n  \
                "location_id",\n  \
                "duration"\n \
            ],\n \
            "ILT_DATE_FORMAT":"DD-MM-YYYY HH:mm",\n \
            "ILT_DROPDOWN_LIST_FORMAT":"{area_region} - {city} - {zip_code} - {start_at} - Nb hrs. {duration} h"\n}',
        load_kwargs={'object_pairs_hook': collections.OrderedDict}
    )

    def __unicode__(self):
        return u"<SiteConfiguration: {site} >".format(site=self.site)

    def __repr__(self):
        return self.__unicode__()

    def get_value(self, name, default=None):
        """
        Return Configuration value for the key specified as name argument.

        Function logs a message if configuration is not enabled or if there is an error retrieving a key.

        Args:
            name (str): Name of the key for which to return configuration value.
            default: default value tp return if key is not found in the configuration

        Returns:
            Configuration value for the given key or returns `None` if configuration is not enabled.
        """
        if self.enabled:
            try:
                return self.values.get(name, default)  # pylint: disable=no-member
            except AttributeError as error:
                logger.exception('Invalid JSON data. \n [%s]', error)
        else:
            logger.info("Site Configuration is not enabled for site (%s).", self.site)

        return default

    @classmethod
    def get_value_for_org(cls, org, name, default=None):
        """
        This returns site configuration value which has an org_filter that matches
        what is passed in,

        Args:
            org (str): Course ord filter, this value will be used to filter out the correct site configuration.
            name (str): Name of the key for which to return configuration value.
            default: default value tp return if key is not found in the configuration

        Returns:
            Configuration value for the given key.
        """
        for configuration in cls.objects.filter(values__contains=org, enabled=True).all():
            course_org_filter = configuration.get_value('course_org_filter', [])
            # The value of 'course_org_filter' can be configured as a string representing
            # a single organization or a list of strings representing multiple organizations.
            if not isinstance(course_org_filter, list):
                course_org_filter = [course_org_filter]
            if org in course_org_filter:
                return configuration.get_value(name, default)
        return default

    @classmethod
    def get_all_orgs(cls):
        """
        This returns all of the orgs that are considered in site configurations, This can be used,
        for example, to do filtering.

        Returns:
            A list of all organizations present in site configuration.
        """
        org_filter_set = set()

        for configuration in cls.objects.filter(values__contains='course_org_filter', enabled=True).all():
            course_org_filter = configuration.get_value('course_org_filter', [])
            if not isinstance(course_org_filter, list):
                course_org_filter = [course_org_filter]
            org_filter_set.update(course_org_filter)
        return org_filter_set

    @classmethod
    def has_org(cls, org):
        """
        Check if the given organization is present in any of the site configuration.

        Returns:
            True if given organization is present in site configurations otherwise False.
        """
        return org in cls.get_all_orgs()


class SiteConfigurationHistory(TimeStampedModel):
    """
    This is an archive table for SiteConfiguration, so that we can maintain a history of
    changes. Note that the site field is not unique in this model, compared to SiteConfiguration.

    Fields:
        site (ForeignKey): foreign-key to django Site
        values (JSONField): json field to store configurations for a site
    """
    site = models.ForeignKey(Site, related_name='configuration_histories', on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False, verbose_name="Enabled")
    values = JSONField(
        null=False,
        blank=True,
        load_kwargs={'object_pairs_hook': collections.OrderedDict}
    )

    class Meta:
        get_latest_by = 'modified'
        ordering = ('-modified', '-created',)

    def __unicode__(self):
        return u"<SiteConfigurationHistory: {site}, Last Modified: {modified} >".format(
            modified=self.modified,
            site=self.site,
        )

    def __repr__(self):
        return self.__unicode__()


@receiver(post_save, sender=SiteConfiguration)
def update_site_configuration_history(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Add site configuration changes to site configuration history.

    Args:
        sender: sender of the signal i.e. SiteConfiguration model
        instance: SiteConfiguration instance associated with the current signal
        **kwargs: extra key word arguments
    """
    SiteConfigurationHistory.objects.create(
        site=instance.site,
        values=instance.values,
        enabled=instance.enabled,
    )
