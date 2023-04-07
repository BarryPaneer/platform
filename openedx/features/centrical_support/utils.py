from django.conf import settings

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from student.triboo_groups import CENTRICAL_DENIED_GROUP


def get_triboo_centrical_index_url():
    """Return URL of Triboo CENTRICAL Index Page
    """
    return configuration_helpers.get_value(
        'TRIBOO_CENTRICAL_URL',
        settings.FEATURES.get('TRIBOO_CENTRICAL_URL', None)
    )


def is_triboo_centrical_enabled(user_groups):
    """Enable Centrical Platform IF:
        - `ENABLE_TRIBOO_CENTRICAL` is True
        - `TRIBOO_CENTRICAL_URL` is defined
        - Group `CENTRICAL_DENIED_GROUP` is not in user' groups.
    """
    is_centrical_platform_enabled = configuration_helpers.get_value(
        'ENABLE_TRIBOO_CENTRICAL',
        settings.FEATURES.get('ENABLE_TRIBOO_CENTRICAL', False)
    )
    centrical_index_url = get_triboo_centrical_index_url()

    return is_centrical_platform_enabled and centrical_index_url and CENTRICAL_DENIED_GROUP not in user_groups
