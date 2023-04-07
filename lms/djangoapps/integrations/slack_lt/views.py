from django.conf import settings
from slackclient import SlackClient
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers

import logging

log = logging.getLogger(__name__)


class InitialSlack(object):
    def __init__(self):
        self.slack_bot_token = None
        self.channel_name = None
        self.sender_title = None
        self.default_message = None
        self.slack_config = configuration_helpers.get_value('slack_config', getattr(settings, 'SLACK_CONFIG', None))
        if self.slack_config:
            self.slack_bot_token = self.slack_config['slack_bot_token']
            if 'channel_name' in self.slack_config:
                self.channel_name = self.slack_config['channel_name']
            if 'sender_title' in self.slack_config:
                self.sender_title = self.slack_config['sender_title']
            if 'default_message' in self.slack_config:
                self.default_message = self.slack_config['default_message']

    def initial_slack_client(self):
        if self.slack_bot_token:
            sc = SlackClient(self.slack_bot_token) 
            return sc
        return False

    def slack_send_message(self, content=None, channel_id=None, sender=None):
        if not content:
            content = self.default_message
        if not channel_id:
            channel_id = self.channel_name
        if not sender:
            sender = self.sender_title
        sc = self.initial_slack_client()
        if sc:
            sc_result = sc.api_call('chat.postMessage', channel=channel_id, text=content, as_user='false', username=sender)
            if sc_result['ok']:
                return True
            log.error(sc_result['error'])
            return False
        log.error("Failed to initiate slack client.")
        return False

    def slack_lookup_email(self, user_email):
        sc = self.initial_slack_client()
        if sc:
            sc_result = sc.api_call('users.lookupByEmail', email=user_email)
            if sc_result['ok']:
                return sc_result['user']['id']
            log.error(sc_result['error'])
            return False
        log.error("Failed to initiate slack client.")
        return False