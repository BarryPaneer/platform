"""
Test the heartbeat
"""
import json

from django.urls import reverse
from django.db.utils import DatabaseError
from django.test.client import Client
from django.conf import settings
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from mock import patch

from xmodule.exceptions import HeartbeatFailure


class HeartbeatTestCase(ModuleStoreTestCase):
    """
    Test the heartbeat
    """

    def setUp(self):
        self.client = Client()
        self.heartbeat_url = reverse('heartbeat')
        settings.HEARTBEAT_CHECKS = [
            'openedx.core.djangoapps.heartbeat.default_checks.check_modulestore',
            'openedx.core.djangoapps.heartbeat.default_checks.check_database'
        ]
        return super(HeartbeatTestCase, self).setUp()

    def test_success(self):
        response = self.client.get(self.heartbeat_url + '?extended')
        print response

        self.assertEqual(response.status_code, 200)

    def test_sql_fail(self):
        with patch('openedx.core.djangoapps.heartbeat.default_checks.connection') as mock_connection:
            mock_connection.cursor.return_value.execute.side_effect = DatabaseError
            response = self.client.get(self.heartbeat_url)
            self.assertEqual(response.status_code, 503)
            response_dict = json.loads(response.content)
            self.assertIn('sql', response_dict)

    def test_modulestore_fail(self):
        with patch('openedx.core.djangoapps.heartbeat.default_checks.modulestore') as mock_modulestore:
            mock_modulestore.return_value.heartbeat.side_effect = HeartbeatFailure('msg', 'service')
            response = self.client.get(self.heartbeat_url)
            self.assertEqual(response.status_code, 503)
