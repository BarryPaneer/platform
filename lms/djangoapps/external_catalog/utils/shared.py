from django.conf import settings

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from student.triboo_groups import ANDERSPINK_DENIED_GROUP
from student.triboo_groups import CREHANA_DENIED_GROUP
from student.triboo_groups import EDFLEX_DENIED_GROUP
from student.triboo_groups import FOUNDERZ_DENIED_GROUP
from student.triboo_groups import SIEMENS_DENIED_GROUP


def is_external_catalog_enabled():
    return configuration_helpers.get_value(
        'ENABLE_EXTERNAL_CATALOG',
        settings.FEATURES.get('ENABLE_EXTERNAL_CATALOG', False)
    )


def get_founderz_configuration():
    return {
        'client_key': settings.AUTH_TOKENS.get('FOUNDERZ_API', {}).get('FOUNDERZ_CLIENT_KEY'),
        'client_secret': settings.AUTH_TOKENS.get('FOUNDERZ_API', {}).get('FOUNDERZ_CLIENT_SECRET'),
        'slug': settings.AUTH_TOKENS.get('FOUNDERZ_API', {}).get('FOUNDERZ_SLUG'),
        'partner_id': settings.AUTH_TOKENS.get('FOUNDERZ_API', {}).get('FOUNDERZ_PARTNER_ID')
    }


def is_founderz_enabled(user_groups):
    is_founderz_catalog_enabled = configuration_helpers.get_value(
        'ENABLE_FOUNDERZ_CATALOG',
        settings.FEATURES.get('ENABLE_FOUNDERZ_CATALOG', False)
    )
    if is_external_catalog_enabled() and is_founderz_catalog_enabled:
        return all(
            (all(get_founderz_configuration().values()), FOUNDERZ_DENIED_GROUP not in user_groups)
        )

    return False


def get_crehana_configuration():
    return {
        'client_key': settings.AUTH_TOKENS.get('CREHANA_API', {}).get('CREHANA_CLIENT_KEY'),
        'client_secret': settings.AUTH_TOKENS.get('CREHANA_API', {}).get('CREHANA_CLIENT_SECRET'),
        'client_slug': settings.AUTH_TOKENS.get('CREHANA_API', {}).get('CREHANA_CLIENT_SLUG'),
        'base_api_url': settings.AUTH_TOKENS.get('CREHANA_API', {}).get('CREHANA_BASE_API_URL')
    }


def is_crehana_enabled(user_groups):
    """Enable Crehana IF:
        - ENABLE_EXTERNAL_CATALOG is True
        - ENABLE_CREHANA_CATALOG is True
        - Group 'CREHANA_DENIED_GROUP' is not in user' groups.
    """
    is_crehana_catalog_enabled = configuration_helpers.get_value(
        'ENABLE_CREHANA_CATALOG',
        settings.FEATURES.get('ENABLE_CREHANA_CATALOG', False)
    )
    if is_external_catalog_enabled() and is_crehana_catalog_enabled:
        return all(
            (all(get_crehana_configuration().values()), CREHANA_DENIED_GROUP not in user_groups)
        )

    return False


def get_edflex_configuration():
    return {
        'client_id': settings.XBLOCK_SETTINGS.get('EdflexXBlock', {}).get('EDFLEX_CLIENT_ID'),
        'client_secret': settings.XBLOCK_SETTINGS.get('EdflexXBlock', {}).get('EDFLEX_CLIENT_SECRET'),
        'locale': settings.XBLOCK_SETTINGS.get('EdflexXBlock', {}).get('EDFLEX_LOCALE', ['en']),
        'base_api_url': settings.XBLOCK_SETTINGS.get('EdflexXBlock', {}).get('EDFLEX_BASE_API_URL')
    }


def is_edflex_enabled(user_groups):
    """Enable Edflex IF:
        - ENABLE_EXTERNAL_CATALOG is True
        - ENABLE_EDFLEX_CATALOG is True
        - Group 'EDFLEX_DENIED_GROUP' is not in user' groups.
    """
    is_edflex_catalog_enabled = configuration_helpers.get_value(
        'ENABLE_EDFLEX_CATALOG',
        settings.FEATURES.get('ENABLE_EDFLEX_CATALOG', False)
    )
    edflex_url = configuration_helpers.get_value('EDFLEX_URL', None)
    if is_external_catalog_enabled() and is_edflex_catalog_enabled and edflex_url:
        return all(
            (all(get_edflex_configuration().values()), EDFLEX_DENIED_GROUP not in user_groups)
        )

    return False


def get_anderspink_configuration():
    return {
        'api_key': settings.AUTH_TOKENS.get('ANDERSPINK_API', {}).get('ANDERSPINK_CLIENT_KEY'),
        'base_url': settings.AUTH_TOKENS.get('ANDERSPINK_API', {}).get('ANDERSPINK_BASE_API_URL', 'https://anderspink.com/api/v3/'),
        'api_time': settings.AUTH_TOKENS.get('ANDERSPINK_API', {}).get('ANDERSPINK_CLIENT_TIME', '3-days'),
        'is_board_enabled': settings.AUTH_TOKENS.get('ANDERSPINK_API', {}).get('IS_BOARD_ENABLED', False)
    }


def is_anderspink_enabled(user_groups):
    """Enable AnderSpink IF:
        - ENABLE_EXTERNAL_CATALOG is True
        - ENABLE_ANDERSPINK_CATALOG is True
        - Group 'ANDERSPINK_DENIED_GROUP' is not in user' groups.
    """
    is_andersppink_catalog_enabled = configuration_helpers.get_value(
        'ENABLE_ANDERSPINK_CATALOG',
        settings.FEATURES.get('ENABLE_ANDERSPINK_CATALOG', False)
    )
    if is_external_catalog_enabled() and is_andersppink_catalog_enabled:
        return all(
            (all(get_anderspink_configuration().values()), ANDERSPINK_DENIED_GROUP not in user_groups)
        )

    return False


def is_siemens_enabled(user_groups):
    siemens_catalog_enabled = (
            configuration_helpers.get_value('ENABLE_SIEMENS_CATALOG',
                                            settings.FEATURES.get('ENABLE_SIEMENS_CATALOG', False))
            and configuration_helpers.get_value('SIEMENS_URL', None)
            and SIEMENS_DENIED_GROUP not in user_groups)
    return is_external_catalog_enabled() and siemens_catalog_enabled


def get_external_catalog_url_by_user(user):
    # `empty` means: hide `external catalog button`
    enable_external_catalog_button = configuration_helpers.get_value(
        'ENABLE_EXTERNAL_CATALOG', settings.FEATURES.get('ENABLE_EXTERNAL_CATALOG', False)
    )
    if not user.is_authenticated or not enable_external_catalog_button:
        return r''

    user_groups = {group.name for group in user.groups.all()}
    edflex_enabled = is_edflex_enabled(user_groups)
    crehana_enabled = is_crehana_enabled(user_groups)
    anderspink_enabled = is_anderspink_enabled(user_groups)

    external_catalogs_status = [edflex_enabled, crehana_enabled, anderspink_enabled]

    if any(external_catalogs_status):
        if len([s for s in external_catalogs_status if s]) > 1:
            return r'/all_external_catalog'
        if edflex_enabled:
            return r'/edflex_catalog'
        if anderspink_enabled:
            return r'/anderspink_catalog'
        return r'/crehana_catalog'

    return r''


def get_external_catalogs_by_user(user):
    external_catalogs = []

    enable_external_catalog_button = configuration_helpers.get_value(
        'ENABLE_EXTERNAL_CATALOG', settings.FEATURES.get('ENABLE_EXTERNAL_CATALOG', False)
    )
    if not enable_external_catalog_button:
        return external_catalogs

    if not user.is_authenticated:
        return external_catalogs

    user_groups = {group.name for group in user.groups.all()}
    edflex_enabled = is_edflex_enabled(user_groups)
    crehana_enabled = is_crehana_enabled(user_groups)
    anderspink_enabled = is_anderspink_enabled(user_groups)

    if crehana_enabled:
        external_catalogs.append({
            "name": "CREHANA",
            "to": "/crehana_catalog",
            "title": configuration_helpers.get_value('CREHANA_RENAME', 'Crehana'),
        })

    if edflex_enabled:
        external_catalogs.append({
            "name": "EDFLEX",
            "to": "/edflex_catalog",
            "title": configuration_helpers.get_value('EDFLEX_RENAME', 'EdFlex'),
        })

    if anderspink_enabled:
        external_catalogs.append({
            "name": "ANDERSPINK",
            "to": "/anderspink_catalog",
            "title": configuration_helpers.get_value('ANDERSPINK_RENAME', 'Anders Pink'),
        })

    return external_catalogs
