"""
Utility methods related to course
"""
import logging
import urllib

from babel import Locale, UnknownLocaleError
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from opaque_keys.edx.keys import AssetKey
from opaque_keys.edx.locator import InvalidKeyError

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from xmodule.contentstore.content import StaticContent
from xmodule.contentstore.django import contentstore


log = logging.getLogger(__name__)

COURSE_SHARING_UTM_PARAMETERS = {
    'facebook': {
        'utm_medium': 'social',
        'utm_campaign': 'social-sharing-db',
        'utm_source': 'facebook',
    },
    'twitter': {
        'utm_medium': 'social',
        'utm_campaign': 'social-sharing-db',
        'utm_source': 'twitter',
    },
}


def get_encoded_course_sharing_utm_params():
    """
    Returns encoded Course Sharing UTM Parameters.
    """
    return {
        utm_source: urllib.urlencode(utm_params)
        for utm_source, utm_params in COURSE_SHARING_UTM_PARAMETERS.iteritems()
    }


def get_link_for_about_page(course):
    """
    Arguments:
        course: This can be either a course overview object or a course descriptor.

    Returns the course sharing url, this can be one of course's social sharing url, marketing url, or
    lms course about url.
    """
    is_social_sharing_enabled = configuration_helpers.get_value(
        'SOCIAL_SHARING_SETTINGS',
        getattr(settings, 'SOCIAL_SHARING_SETTINGS', {})
    ).get('CUSTOM_COURSE_URLS')
    if is_social_sharing_enabled and course.social_sharing_url:
        course_about_url = course.social_sharing_url
    elif settings.FEATURES.get('ENABLE_MKTG_SITE') and getattr(course, 'marketing_url', None):
        course_about_url = course.marketing_url
    else:
        course_about_url = u'{about_base_url}/courses/{course_key}/about'.format(
            about_base_url=configuration_helpers.get_value('LMS_ROOT_URL', settings.LMS_ROOT_URL),
            course_key=unicode(course.id),
        )

    return course_about_url


def remove_course_reports(course_key):
    """
    Delete all reports related to the course.
    """
    from triboo_analytics.models import (
        Badge,
        CourseDailyReport,
        LearnerCourseJsonReport,
        LearnerSectionJsonReport,
    )
    Badge.objects.filter(course_id=course_key).delete()
    CourseDailyReport.objects.filter(course_id=course_key).delete()
    LearnerCourseJsonReport.objects.filter(course_id=course_key).delete()
    LearnerSectionJsonReport.objects.filter(course_id=course_key).delete()


def get_badge_url(course_key, grader):
    """
    Get real asset for the provided grade image url.
    """

    try:
        badge_url = grader.get('badge_url', '')
        if badge_url:
            asset_key = AssetKey.from_string(badge_url[1:]) # trim first slash char to get asset key
            content = contentstore().find(asset_key, throw_on_not_found=False)
            if content is not None:
                return badge_url

        if grader['short_label'] is not None:
            # keep compatibility with old badge image url get(use the same name with grade's
            # short label.
            for img_type in ('.png', '.PNG', '.jpg', '.JPG', '.jpeg', '.JPEG'):
                asset_key = course_key.make_asset_key('asset', grader['short_label'].encode('utf-8').decode('utf-8') + img_type)
                content = contentstore().find(asset_key, throw_on_not_found=False)
                if content is not None:
                    return StaticContent.serialize_asset_key_with_slash(asset_key)
    except InvalidKeyError:
        # roll back to get image url with the default one.
        pass

    return staticfiles_storage.url("images/badge.png")


def language_locale(language, display_language):
    language = language.replace('_', '-')
    try:
        return Locale.parse(language, sep='-').get_language_name((display_language or '').split('-')[0] or 'en').capitalize()
    except UnknownLocaleError:
        return next((language_set for language_set in settings.ALL_LANGUAGES if language_set[0] == language), [])[1]
