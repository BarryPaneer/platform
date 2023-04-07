"""
Base Message types to be used to construct ace messages.
"""
from django.conf import settings
from edx_ace.message import MessageType
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers


class BaseMessageType(MessageType):
    def __init__(self, *args, **kwargs):
        super(BaseMessageType, self).__init__(*args, **kwargs)
        from_address = configuration_helpers.get_value('email_from_address', settings.DEFAULT_FROM_EMAIL)
        from_alias = configuration_helpers.get_value('email_from_alias', settings.DEFAULT_FROM_EMAIL_ALIAS)
        from_address = "{alias} <{email}>".format(alias=from_alias, email=from_address)
        if from_address:
            self.options.update({'from_address': from_address})  # pylint: disable=no-member
