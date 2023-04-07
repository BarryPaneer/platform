""" Overrides for Docker-based devstack. """

from .devstack import *  # pylint: disable=wildcard-import, unused-wildcard-import

# Docker does not support the syslog socket at /dev/log. Rely on the console.
LOGGING['handlers']['local'] = LOGGING['handlers']['tracking'] = {
    'class': 'logging.NullHandler',
}

COURSE_CATALOG_API_URL='http://edx.devstack.discovery:18381/api/v1/'

LOGGING['loggers']['tracking']['handlers'] = ['console']

LMS_BASE = 'edx.devstack.lms:18000'
CMS_BASE = 'edx.devstack.studio:18010'
LMS_ROOT_URL = 'http://{}'.format(LMS_BASE)

FEATURES.update({
    'ENABLE_COURSE_DISCOVERY': True,
    'ALLOW_PUBLIC_ACCOUNT_CREATION': False,
    'ENABLE_COURSEWARE_INDEX': True,
    'ENABLE_LIBRARY_INDEX': False,
    'ENABLE_DISCUSSION_SERVICE': True,
    'ENABLE_EXTENDED_COURSE_DETAILS': True
})

CREDENTIALS_SERVICE_USERNAME = 'credentials_worker'

OAUTH_OIDC_ISSUER = '{}/oauth2'.format(LMS_ROOT_URL)

JWT_AUTH.update({
    'JWT_SECRET_KEY': 'lms-secret',
    'JWT_ISSUER': OAUTH_OIDC_ISSUER,
    'JWT_AUDIENCE': 'lms-key',
})
