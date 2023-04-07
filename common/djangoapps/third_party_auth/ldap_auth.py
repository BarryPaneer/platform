""" Util providing customized LDAPBackend. """

import logging

from django.conf import settings
from django_auth_ldap.backend import LDAPBackend
from django_auth_ldap.config import LDAPSearch
import ldap

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers


log = logging.getLogger(__name__)


class LDAPAuthBackend(LDAPBackend):
    def configure(self):
        settings.AUTH_LDAP_SERVER_URI = configuration_helpers.get_value('AUTH_LDAP_SERVER_URI')
        settings.AUTH_LDAP_BIND_DN = configuration_helpers.get_value('AUTH_LDAP_BIND_DN')
        settings.AUTH_LDAP_BIND_PASSWORD = configuration_helpers.get_value('AUTH_LDAP_BIND_PASSWORD')
        if (configuration_helpers.get_value('AUTH_LDAP_USER_SEARCH_BASE_DN')
            and configuration_helpers.get_value('AUTH_LDAP_USER_SEARCH_FILTER_STR')):
            settings.AUTH_LDAP_USER_SEARCH = LDAPSearch(
                configuration_helpers.get_value('AUTH_LDAP_USER_SEARCH_BASE_DN'),
                ldap.SCOPE_SUBTREE,
                configuration_helpers.get_value('AUTH_LDAP_USER_SEARCH_FILTER_STR'))
        settings.AUTH_LDAP_USER_ATTR_MAP = configuration_helpers.get_value('AUTH_LDAP_USER_ATTR_MAP', settings.AUTH_LDAP_USER_ATTR_MAP)
        settings.AUTH_LDAP_GLOBAL_OPTIONS = {
            ldap.OPT_X_TLS_CACERTFILE: configuration_helpers.get_value('AUTH_LDAP_CACERT'),
#            ldap.OPT_DEBUG_LEVEL: 255
        }

    def authenticate(self, request=None, username=None, password=None, **kwargs):
        if configuration_helpers.get_value('AUTH_LDAP_SERVER_URI'):
            self.configure()
#            log.warning('settings: AUTH_LDAP_SERVER_URI=%s | AUTH_LDAP_BIND_DN=%s | AUTH_LDAP_BIND_PASSWORD=%s | AUTH_LDAP_USER_SEARCH=%s | AUTH_LDAP_USER_ATTR_MAP=%s | AUTH_LDAP_GLOBAL_OPTIONS=%s | username=%s | password=%s',
#                settings.AUTH_LDAP_SERVER_URI, settings.AUTH_LDAP_BIND_DN, settings.AUTH_LDAP_BIND_PASSWORD, settings.AUTH_LDAP_USER_SEARCH, settings.AUTH_LDAP_USER_ATTR_MAP, settings.AUTH_LDAP_GLOBAL_OPTIONS, username, password)
            try:
                return super(LDAPAuthBackend, self).authenticate(request=request, username=username, password=password, **kwargs)
            except Exception as e:
                log.warning('LDAP authenticated failed: %s', e.message)
                return
