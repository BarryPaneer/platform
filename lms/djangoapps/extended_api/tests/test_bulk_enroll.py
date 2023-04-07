"""
Tests for the Bulk Enrollment views.
"""
import json

from courseware.tests.helpers import LoginEnrollmentTestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core import mail
from django.urls import reverse
from extended_api.serializers import BulkEnrollmentSerializer
from microsite_configuration import microsite
from rest_framework.test import APITestCase, force_authenticate
from student.models import (
    ManualEnrollmentAudit,
    ENROLLED_TO_UNENROLLED,
    UNENROLLED_TO_ENROLLED,
)
from student.models import UserProfile, CourseEnrollment
from student.tests.factories import UserFactory
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import XMODULE_FACTORY_LOCK

from lms.djangoapps.course_api.tests.mixins import CourseApiFactoryMixin
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration

User = get_user_model()
test_config_multi_org = {  # pylint: disable=invalid-name
    "course_org_filter": ["FooOrg", "BarOrg", "FooBarOrg"]
}


def create_mock_site_config():
    site, __ = Site.objects.get_or_create(domain="example.com", name="example.com")
    site_configuration, created = SiteConfiguration.objects.get_or_create(
        site=site,
        defaults={"enabled": True, "values": test_config_multi_org},
    )
    if not created:
        site_configuration.values = test_config_multi_org
        site_configuration.save()


class BulkEnrollmentTest(CourseApiFactoryMixin, ModuleStoreTestCase, LoginEnrollmentTestCase, APITestCase):
    """
    Test the bulk enrollment endpoint
    """
    shard = 4

    USERNAME = "Bob"
    EMAIL = "bob@example.com"
    PASSWORD = "edx"

    def setUp(self):
        """ Create a course and user, then log in. """

        create_mock_site_config()

        XMODULE_FACTORY_LOCK.enable()

        if not CourseOverview.objects.all() and modulestore().get_courses():
            CourseOverview.load_from_module_store(modulestore().get_courses()[0].id)
        else:
            self.create_course()

        self.staff = User.objects.create(
            username=self.USERNAME,
            email=self.EMAIL,
            password=self.PASSWORD,
            is_staff=True,
            is_superuser=True,

        )
        UserProfile.objects.create(
            user=self.staff,
            org="FooOrg"
        )
        self.client.force_authenticate(user=self.staff)
        self.url = reverse('extended_api:bulk_enroll')

        self.course = CourseOverview.objects.first()
        self.course_key = unicode(self.course.id)
        self.course.org = "FooOrg"
        self.course.save()
        self.enrolled_student = UserFactory(username='EnrolledStudent', first_name='Enrolled', last_name='Student')
        CourseEnrollment.enroll(
            self.enrolled_student,
            self.course.id
        )
        self.notenrolled_student = UserFactory(username='NotEnrolledStudent', first_name='NotEnrolled',
                                               last_name='Student')

        # Email URL values
        self.site_name = microsite.get_value(
            'SITE_NAME',
            settings.SITE_NAME
        )
        self.about_path = '/courses/{}/about'.format(self.course.id)
        self.course_path = '/courses/{}/'.format(self.course.id)

    def request_bulk_enroll(self, data=None, use_json=False, **extra):
        """ Make an authenticated request to the bulk enrollment API. """
        content_type = None
        if use_json:
            content_type = 'application/json'
            data = json.dumps(data)
        request = self.request_factory.post(self.url, data=data, content_type=content_type, **extra)
        force_authenticate(request, user=self.staff)
        response = self.view(request)
        response.render()
        return response

    def test_course_list_serializer(self):
        """
        Test that the course serializer will work when passed a string or list.

        Internally, DRF passes the data into the value conversion method as a list instead of
        a string, so StringListField needs to work with both.
        """
        for key in [self.course_key, [self.course_key]]:
            serializer = BulkEnrollmentSerializer(data={
                'identifiers': 'percivaloctavius',
                'action': 'enroll',
                'email_students': False,
                'courses': key,
            })
            self.assertTrue(serializer.is_valid())

    def test_non_staff(self):
        """ Test that non global staff users are forbidden from API use. """
        self.staff.is_staff = False
        self.staff.save()
        # response = self.request_bulk_enroll()
        response = self.client.post(self.url, format='json')
        self.assertEqual(response.status_code, 403)

    def test_missing_params(self):
        """ Test the response when missing all query parameters. """
        response = self.client.post(self.url, format='json')
        self.assertEqual(response.status_code, 400)

    def test_bad_action(self):
        """ Test the response given an invalid action """
        data = {
            'emails': self.enrolled_student.email,
            'action': 'invalid-action',
            'courses': self.course_key,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 400)

    def test_invalid_email(self):
        """ Test the response given an invalid email. """
        data = {
            'emails': 'percivaloctavius@',
            'action': 'enroll',
            'email_students': False,
            'courses': self.course_key,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)

        # test the response data
        expected = {
            "action": "enroll",
            'email_students': False,
            "courses": {
                self.course_key: {
                    "action": "enroll",
                    "results": [
                        {
                            "identifier": {"email": 'percivaloctavius@'},
                            "invalidIdentifier": True,
                        }
                    ]
                }
            }
        }

        res_json = json.loads(response.content)
        self.assertEqual(res_json, expected)

    def test_invalid_username(self):
        """ Test the response given an invalid username. """
        data = {
            'usernames': 'percivaloctavius',
            'action': 'enroll',
            'email_students': False,
            'courses': self.course_key,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)

        # test the response data
        expected = {
            "action": "enroll",
            'email_students': False,
            "courses": {
                self.course_key: {
                    "action": "enroll",
                    "results": [
                        {
                            "identifier": {"username": 'percivaloctavius'},
                            "invalidIdentifier": True,
                        }
                    ]
                }
            }
        }

        res_json = json.loads(response.content)
        self.assertEqual(res_json, expected)

    def test_invalid_user_id(self):
        """ Test the response given an invalid user_id. """
        data = {
            'user_ids': '-1',
            'action': 'enroll',
            'email_students': False,
            'courses': self.course_key,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)

        # test the response data
        expected = {
            "action": "enroll",
            'email_students': False,
            "courses": {
                self.course_key: {
                    "action": "enroll",
                    "results": [
                        {
                            "identifier": {"user_id": '-1'},
                            "invalidIdentifier": True,
                        }
                    ]
                }
            }
        }

        res_json = json.loads(response.content)
        self.assertEqual(res_json, expected)

    def test_enroll_with_username(self):
        """ Test enrolling using usernames. """
        data = {
            'usernames': self.notenrolled_student.username,
            'action': 'enroll',
            'email_students': False,
            'courses': self.course_key,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)

        # test the response data
        expected = {
            "action": "enroll",
            "email_students": False,
            "courses": {
                self.course_key: {
                    "action": "enroll",
                    "results": [
                        {
                            "identifier": {"username": self.notenrolled_student.username},
                            "before": {
                                "enrollment": False,
                                "user": True,
                            },
                            "after": {
                                "enrollment": True,
                                "user": True,
                            }
                        }
                    ]
                }
            }
        }
        manual_enrollments = ManualEnrollmentAudit.objects.all()
        self.assertEqual(manual_enrollments.count(), 1)
        self.assertEqual(manual_enrollments[0].state_transition, UNENROLLED_TO_ENROLLED)
        res_json = json.loads(response.content)
        self.assertEqual(res_json, expected)

    def test_enroll_with_email(self):
        """ Test enrolling using emails. """
        data = {
            'emails': self.notenrolled_student.email,
            'action': 'enroll',
            'email_students': False,
            'courses': self.course_key,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)

        # test that the user is now enrolled
        user = User.objects.get(email=self.notenrolled_student.email)
        self.assertTrue(CourseEnrollment.is_enrolled(user, self.course.id))

        # test the response data
        expected = {
            "action": "enroll",
            "email_students": False,
            "courses": {
                self.course_key: {
                    "action": "enroll",
                    "results": [
                        {
                            "identifier": {"email": self.notenrolled_student.email},
                            "before": {
                                "enrollment": False,
                                "user": True,
                            },
                            "after": {
                                "enrollment": True,
                                "user": True,
                            }
                        }
                    ]
                }
            }
        }

        manual_enrollments = ManualEnrollmentAudit.objects.all()
        self.assertEqual(manual_enrollments.count(), 1)
        self.assertEqual(manual_enrollments[0].state_transition, UNENROLLED_TO_ENROLLED)
        res_json = json.loads(response.content)
        self.assertEqual(res_json, expected)

        # Check the outbox
        self.assertEqual(len(mail.outbox), 0)

    def test_enroll_with_user_id(self):
        """ Test enrolling using user_ids. """
        data = {
            'user_ids': unicode(self.notenrolled_student.id),
            'action': 'enroll',
            'email_students': False,
            'courses': self.course_key,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)

        # test that the user is now enrolled
        user = User.objects.get(email=self.notenrolled_student.email)
        self.assertTrue(CourseEnrollment.is_enrolled(user, self.course.id))

        # test the response data
        expected = {
            "action": "enroll",
            "email_students": False,
            "courses": {
                self.course_key: {
                    "action": "enroll",
                    "results": [
                        {
                            "identifier": {"user_id": unicode(self.notenrolled_student.id)},
                            "before": {
                                "enrollment": False,
                                "user": True,
                            },
                            "after": {
                                "enrollment": True,
                                "user": True,
                            }
                        }
                    ]
                }
            }
        }

        manual_enrollments = ManualEnrollmentAudit.objects.all()
        self.assertEqual(manual_enrollments.count(), 1)
        self.assertEqual(manual_enrollments[0].state_transition, UNENROLLED_TO_ENROLLED)
        res_json = json.loads(response.content)
        self.assertEqual(res_json, expected)

        # Check the outbox
        self.assertEqual(len(mail.outbox), 0)

    def test_unenroll(self):
        """ Test unenrolling users using emails. """
        data = {
            'emails': self.enrolled_student.email,
            'action': 'unenroll',
            'email_students': False,
            'courses': self.course_key,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)

        # test that the user is now unenrolled
        user = User.objects.get(email=self.enrolled_student.email)
        self.assertFalse(CourseEnrollment.is_enrolled(user, self.course.id))

        # test the response data
        expected = {
            "action": "unenroll",
            "email_students": False,
            "courses": {
                self.course_key: {
                    "action": "unenroll",
                    "results": [
                        {
                            "identifier": {"email": self.enrolled_student.email},
                            "before": {
                                "enrollment": True,
                                "user": True,
                            },
                            "after": {
                                "enrollment": False,
                                "user": True,
                            }
                        }
                    ]
                }
            }

        }

        manual_enrollments = ManualEnrollmentAudit.objects.all()
        self.assertEqual(manual_enrollments.count(), 1)
        self.assertEqual(manual_enrollments[0].state_transition, ENROLLED_TO_UNENROLLED)
        res_json = json.loads(response.content)
        self.assertEqual(res_json, expected)

        # Check the outbox
        self.assertEqual(len(mail.outbox), 0)
