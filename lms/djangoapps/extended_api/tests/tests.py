import unittest

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from social_django.models import UserSocialAuth
from triboo_analytics.models import LearnerCourseJsonReport
from six import text_type
from student.models import UserProfile, CourseEnrollment
from lms.djangoapps.course_api.tests.mixins import CourseApiFactoryMixin
from lms.djangoapps.extended_api.serializers import SSO_PROVIDER
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.factories import CourseFactory, XMODULE_FACTORY_LOCK
from student.roles import STUDIO_ADMIN_ACCESS_GROUP

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


class CreateUserTests(APITestCase):

    def setUp(self):
        create_mock_site_config()

        self.user = User.objects.create(
            username='edx',
            is_staff=True,
            is_superuser=True,
            email='edx@example.com'
        )
        UserProfile.objects.create(
            user=self.user,
            org="FooOrg"
        )
        self.client.force_authenticate(user=self.user)

    def test_successful_user_creation(self):
        url = reverse('extended_api:users-list')
        data = {
            "username": "user1",
            "email": "user1@example.com",
            "first_name": "first1",
            "last_name": "last1",
            "name": "One"
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('status'), 'user_created')
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(UserProfile.objects.count(), 2)
        self.assertTrue(User.objects.filter(username='user1').exists())
        self.assertTrue(UserProfile.objects.filter(name='One').exists())
        self.assertEqual(UserProfile.objects.get(user__username=data['username']).org, self.user.profile.org)

    def test_platform_role_user_creation(self):
        url = reverse('extended_api:users-list')

        data1 = {
            "username": "user1",
            "email": "user1@example.com",
            "first_name": "first1",
            "last_name": "last1",
            "name": "name1",
            "platform_role": "Studio Admin"
        }
        data2 = {
            "username": "user2",
            "email": "user2@example.com",
            "first_name": "first2",
            "last_name": "last2",
            "name": "name2",
            "platform_role": "Platform Admin"
        }
        data3 = {
            "username": "user3",
            "email": "user3@example.com",
            "first_name": "first3",
            "last_name": "last3",
            "name": "name3",
            "platform_role": "Platform Super Admin"
        }

        self.client.post(url, data1, format='json')
        self.client.post(url, data2, format='json')
        self.client.post(url, data3, format='json')

        user1 = User.objects.get(username=data1['username'])
        user2 = User.objects.get(username=data2['username'])
        user3 = User.objects.get(username=data3['username'])

        self.assertTrue(user1.groups.filter(name=STUDIO_ADMIN_ACCESS_GROUP).exists())
        self.assertFalse(user1.is_staff)
        self.assertFalse(user1.is_superuser)
        self.assertTrue(user2.is_staff)
        self.assertFalse(user2.is_superuser)
        self.assertFalse(user3.is_staff)
        self.assertFalse(user3.is_superuser)

    def test_inactive_user_creation(self):
        url = reverse('extended_api:users-list')

        data1 = {
            "username": "user1",
            "email": "user1@example.com",
            "first_name": "first1",
            "last_name": "last1",
            "name": "name1",
            "is_active": False
        }

        response = self.client.post(url, data1, format='json')

        user1 = User.objects.get(username=data1['username'])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('status'), 'user_created')
        self.assertTrue(response.data.get('is_active'))
        self.assertTrue(user1.is_active)

    def test_used_username_user_creation(self):
        url = reverse('extended_api:users-list')
        data = {
            "username": "edx",
            "email": "user2@example.com",
            "first_name": "first2",
            "last_name": "last2",
            "name": "Second"
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'Username already used')

    def test_used_email_user_creation(self):
        url = reverse('extended_api:users-list')
        data = {
            "username": "user3",
            "email": "edx@example.com",
            "first_name": "first3",
            "last_name": "last3",
            "name": "Three"
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'Email already used')


class UpdateUserTests(APITestCase):

    def setUp(self):
        create_mock_site_config()

        self.user = User.objects.create(
            username='edx',
            is_staff=True,
            is_superuser=True,
            email='edx@example.com'
        )
        UserProfile.objects.create(
            user=self.user,
            org="FooOrg"
        )
        self.client.force_authenticate(user=self.user)
        self.user1 = User.objects.create(
            username='user1',
            email='user1@example.com',
            first_name="first1",
            last_name="last1",
        )
        self.user1_profile = UserProfile.objects.create(
            user=self.user1,
            name='One',
            org="FooOrg"
        )

    def test_successful_user_update_by_id(self):
        url = reverse(
            'extended_api:users-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "name": "New_one_by_id"
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('status'), 'user_updated')
        self.assertEqual(response.data.get('name'), 'New_one_by_id')

    def test_user_not_found_update_by_id(self):
        url = reverse(
            'extended_api:users-detail',
            kwargs={'pk': 100}
        )
        data = {
            "name": "New_one_by_id"
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get('detail'), 'Not found.')

    def test_user_inactive_update_by_id(self):
        self.user1.is_active = False
        self.user1.save()
        url = reverse(
            'extended_api:users-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "name": "New_one_by_id"
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'User inactive')

    def test_user_inactive_to_active_update_by_id(self):
        self.user1.is_active = False
        self.user1.save()
        url = reverse(
            'extended_api:users-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "is_active": True
        }

        response = self.client.put(url, data, format='json')

        user1 = User.objects.get(username=self.user1.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('is_active'))
        self.assertTrue(user1.is_active)

    def test_user_active_to_inactive_update_by_id(self):
        self.user1.is_active = True
        self.user1.save()
        url = reverse(
            'extended_api:users-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "is_active": False
        }

        response = self.client.put(url, data, format='json')

        user1 = User.objects.get(username=self.user1.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data.get('is_active'))
        self.assertFalse(user1.is_active)

    def test_superuser_inactive_to_active_update_by_id(self):
        self.user1.is_superuser = True
        self.user1.is_active = False
        self.user1.save()
        url = reverse(
            'extended_api:users-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "is_active": True
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'User inactive')

    def test_superuser_active_to_inactive_update_by_id(self):
        self.user1.is_superuser = True
        self.user1.is_active = True
        self.user1.save()
        url = reverse(
            'extended_api:users-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "is_active": False
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'User is superuser')

    def test_username_used_update_by_id(self):
        url = reverse(
            'extended_api:users-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "username": "edx"
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'Username already used')

    def test_email_used_update_by_id(self):
        url = reverse(
            'extended_api:users-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "email": "edx@example.com"
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'Email already used')

    def test_successful_user_update_by_username(self):
        url = reverse(
            'extended_api:users_by_username-detail',
            kwargs={'username': self.user1.username}
        )
        data = {
            "name": "New_one_by_username"
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('status'), 'user_updated')
        self.assertEqual(response.data.get('name'), 'New_one_by_username')

    def test_user_not_found_update_by_username(self):
        url = reverse(
            'extended_api:users_by_username-detail',
            kwargs={'username': 'not_existing_username'}
        )
        data = {
            "name": "New_one_by_id"
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get('detail'), 'Not found.')

    def test_user_inactive_update_by_username(self):
        self.user1.is_active = False
        self.user1.save()
        url = reverse(
            'extended_api:users_by_username-detail',
            kwargs={'username': self.user1.username}
        )
        data = {
            "name": "New_one_by_id"
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'User inactive')

    def test_user_inactive_to_active_update_by_username(self):
        self.user1.is_active = False
        self.user1.save()
        url = reverse(
            'extended_api:users_by_username-detail',
            kwargs={'username': self.user1.username}
        )
        data = {
            "is_active": True
        }

        response = self.client.put(url, data, format='json')

        user1 = User.objects.get(username=self.user1.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('is_active'))
        self.assertTrue(user1.is_active)

    def test_user_active_to_inactive_update_by_username(self):
        self.user1.is_active = True
        self.user1.save()
        url = reverse(
            'extended_api:users_by_username-detail',
            kwargs={'username': self.user1.username}
        )
        data = {
            "is_active": False
        }

        response = self.client.put(url, data, format='json')

        user1 = User.objects.get(username=self.user1.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data.get('is_active'))
        self.assertFalse(user1.is_active)

    def test_superuser_inactive_to_active_update_by_username(self):
        self.user1.is_superuser = True
        self.user1.is_active = False
        self.user1.save()
        url = reverse(
            'extended_api:users_by_username-detail',
            kwargs={'username': self.user1.username}
        )
        data = {
            "is_active": True
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'User inactive')

    def test_superuser_active_to_inactive_update_by_username(self):
        self.user1.is_superuser = True
        self.user1.is_active = True
        self.user1.save()
        url = reverse(
            'extended_api:users_by_username-detail',
            kwargs={'username': self.user1.username}
        )
        data = {
            "is_active": False
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'User is superuser')

    def test_username_used_update_by_username(self):
        url = reverse(
            'extended_api:users_by_username-detail',
            kwargs={'username': self.user1.username}
        )
        data = {
            "username": "edx"
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'Username already used')

    def test_email_used_update_by_username(self):
        url = reverse(
            'extended_api:users_by_username-detail',
            kwargs={'username': self.user1.username}
        )
        data = {
            "email": "edx@example.com"
        }

        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'Email already used')


class GetUserTests(APITestCase):

    def setUp(self):
        create_mock_site_config()

        self.user = User.objects.create(
            username='edx',
            is_staff=True,
            is_superuser=True,
            email='edx@example.com'
        )
        UserProfile.objects.create(
            user=self.user,
            org="FooOrg"
        )
        self.client.force_authenticate(user=self.user)
        self.user1 = User.objects.create(
            username='user1',
            email='user1@example.com',
            first_name="first1",
            last_name="last1",
        )
        self.user1_profile = UserProfile.objects.create(
            user=self.user1,
            name='One',
            org="FooOrg"
        )
        self.user2 = User.objects.create(
            username='user2',
            email='user2@example.com',
            first_name="first2",
            last_name="last2",
        )
        self.user2_profile = UserProfile.objects.create(
            user=self.user2,
            name='Two',
            org="FooOrg"
        )

    def test_get_users(self):
        url = reverse('extended_api:users-list')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results")), 3)

    def test_get_users_org_filtering(self):
        self.user2_profile.org = ""
        self.user2_profile.save()
        url = reverse('extended_api:users-list')

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results")), 2)

    def test_get_user_by_id(self):
        url = reverse(
            'extended_api:users-detail',
            args=[self.user1.id]
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("username"), "user1")
        self.assertEqual(response.data.get("platform_role"), "Learner")
        self.assertTrue(response.data.get("is_active"))

    def test_platform_role(self):
        self.user1.is_staff = True
        self.user1.save()
        studio_admin_group, _ = Group.objects.get_or_create(name=STUDIO_ADMIN_ACCESS_GROUP)
        self.user2.groups.add(studio_admin_group)
        url = reverse(
            'extended_api:users-detail',
            kwargs={'pk': self.user.id}
        )
        url1 = reverse(
            'extended_api:users-detail',
            kwargs={'pk': self.user1.id}
        )
        url2 = reverse(
            'extended_api:users-detail',
            kwargs={'pk': self.user2.id}
        )

        response = self.client.get(url)
        response1 = self.client.get(url1)
        response2 = self.client.get(url2)

        self.assertEqual(response.data.get("platform_role"), "Platform Super Admin")
        self.assertEqual(response1.data.get("platform_role"), "Platform Admin")
        self.assertEqual(response2.data.get("platform_role"), "Studio Admin")

    def test_get_users_by_ids(self):
        url = "{}?{}".format(
            reverse('extended_api:users-list'),
            "user_id={},{}".format(self.user1.id, self.user2.id)
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results")), 2)
        self.assertEqual(response.data.get("results")[0].get("user_id"), self.user1.id)
        self.assertEqual(response.data.get("results")[1].get("user_id"), self.user2.id)

    def test_get_user_by_id_not_found(self):
        url = reverse(
            'extended_api:users-detail',
            args=[123]
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("detail"), "Not found.")

    def test_get_user_by_username(self):
        url = reverse(
            'extended_api:users_by_username-detail',
            args=[self.user1.username]
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("username"), "user1")
        self.assertTrue(response.data.get("is_active"))

    def test_get_users_by_usernames(self):
        url = "{}?{}".format(
            reverse('extended_api:users_by_username-list'),
            "username={},{}".format(self.user1.username, self.user2.username)
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results")), 2)
        self.assertEqual(response.data.get("results")[0].get("username"), self.user1.username)
        self.assertEqual(response.data.get("results")[1].get("username"), self.user2.username)

    def test_get_user_by_username_not_found(self):
        url = reverse(
            'extended_api:users_by_username-detail',
            kwargs={'username': 'not_existing_username'}
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("detail"), "Not found.")

    def test_get_user_by_email(self):
        url = reverse(
            'extended_api:users_by_email-detail',
            args=[self.user1.email]
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("email"), "user1@example.com")
        self.assertTrue(response.data.get("is_active"))

    def test_get_users_by_emails(self):
        url = "{}?{}".format(
            reverse('extended_api:users_by_email-list'),
            "email={},{}".format(self.user1.email, self.user2.email)
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results")), 2)
        self.assertEqual(response.data.get("results")[0].get("email"), self.user1.email)
        self.assertEqual(response.data.get("results")[1].get("email"), self.user2.email)

    def test_get_user_by_email_not_found(self):
        url = reverse(
            'extended_api:users_by_email-detail',
            kwargs={'email': 'not_existing_email@example.com'}
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("detail"), "Not found.")


class DeactivateUserTests(APITestCase):

    def setUp(self):
        create_mock_site_config()

        self.user = User.objects.create(
            username='edx',
            is_staff=True,
            is_superuser=True,
            email='edx@example.com'
        )
        UserProfile.objects.create(
            user=self.user,
            org="FooOrg"
        )
        self.client.force_authenticate(user=self.user)
        self.user1 = User.objects.create(
            username='user1',
            email='user1@example.com',
            first_name="first1",
            last_name="last1",
        )
        self.user1_profile = UserProfile.objects.create(
            user=self.user1,
            name='One',
            org="FooOrg"
        )
        self.user2 = User.objects.create(
            username='user2',
            email='user2@example.com',
            first_name="first2",
            last_name="last2",
        )
        self.user2_profile = UserProfile.objects.create(
            user=self.user2,
            name='Two',
            org="FooOrg"
        )

    def test_deactivate_user_by_id(self):
        url = reverse(
            'extended_api:users-detail',
            kwargs={'pk': self.user1.id}
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("username"), self.user1.username)
        self.assertEqual(response.data.get("status"), "user_deactivated")
        self.assertEqual(response.data.get("user_id"), self.user1.id)

    def test_deactivate_users_by_ids(self):
        url = "{}?{}".format(
            reverse('extended_api:users-list'),
            "user_id={},{}".format(self.user1.id, self.user2.id)
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0].get("username"), self.user1.username)
        self.assertEqual(response.data[0].get("status"), "user_deactivated")
        self.assertEqual(response.data[0].get("user_id"), self.user1.id)

        self.assertEqual(response.data[1].get("username"), self.user2.username)
        self.assertEqual(response.data[1].get("status"), "user_deactivated")
        self.assertEqual(response.data[1].get("user_id"), self.user2.id)

    def test_deactivate_user_by_id_already_deactivated(self):
        self.user1.is_active = False
        self.user1.save()
        url = reverse(
            'extended_api:users-detail',
            kwargs={'pk': self.user1.id}
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get("detail"), "User already inactive")

    def test_deactivate_user_by_id_not_found(self):
        url = reverse(
            'extended_api:users-detail',
            kwargs={'pk': 123}
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("detail"), "Not found.")

    def test_deactivate_user_by_username(self):
        url = reverse(
            'extended_api:users_by_username-detail',
            kwargs={'username': self.user1.username}
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("username"), self.user1.username)
        self.assertEqual(response.data.get("status"), "user_deactivated")
        self.assertEqual(response.data.get("user_id"), self.user1.id)

    def test_deactivate_users_by_usernames(self):
        url = "{}?{}".format(
            reverse('extended_api:users_by_username-list'),
            "username={},{}".format(self.user1.username, self.user2.username)
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0].get("username"), self.user1.username)
        self.assertEqual(response.data[0].get("status"), "user_deactivated")
        self.assertEqual(response.data[0].get("user_id"), self.user1.id)

        self.assertEqual(response.data[1].get("username"), self.user2.username)
        self.assertEqual(response.data[1].get("status"), "user_deactivated")
        self.assertEqual(response.data[1].get("user_id"), self.user2.id)

    def test_deactivate_user_by_username_already_deactivated(self):
        self.user1.is_active = False
        self.user1.save()
        url = reverse(
            'extended_api:users_by_username-detail',
            kwargs={'username': self.user1.username}
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get("detail"), "User already inactive")

    def test_deactivate_user_by_username_not_found(self):
        url = reverse(
            'extended_api:users_by_username-detail',
            kwargs={'username': 'not_existing_username'}
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("detail"), "Not found.")


class CoursesTests(CourseApiFactoryMixin, APITestCase):

    def setUp(self):
        create_mock_site_config()

        XMODULE_FACTORY_LOCK.enable()

        if not CourseOverview.objects.all() and modulestore().get_courses():
            CourseOverview.load_from_module_store(modulestore().get_courses()[0].id)
        else:
            self.create_course()

        self.user = User.objects.create(
            username='edx',
            is_staff=True,
            is_superuser=True,
            email='edx@example.com'
        )
        UserProfile.objects.create(
            user=self.user,
            org="FooOrg"
        )
        self.client.force_authenticate(user=self.user)

    def test_get_courses(self):
        test_course = CourseOverview.objects.first()
        test_course.org = "FooOrg"
        test_course.save()
        url = reverse('extended_api:courses-list')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results")), 1)
        self.assertEqual(len(response.data.get("results")[0].keys()), 15)

    def test_get_course_without_org(self):
        test_course = CourseOverview.objects.first()
        test_course.org = ""
        test_course.save()
        url = reverse('extended_api:courses-list')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("results"), [])


class UserProgressReportTests(CourseApiFactoryMixin, APITestCase):

    def setUp(self):
        create_mock_site_config()
        XMODULE_FACTORY_LOCK.enable()
        if not CourseOverview.objects.all() and modulestore().get_courses():
            CourseOverview.load_from_module_store(modulestore().get_courses()[0].id)
        else:
            self.create_course()

        test_course = CourseOverview.objects.first()

        self.user = User.objects.create(
            username='edx',
            is_staff=True,
            is_superuser=True,
            email='edx@example.com'
        )
        UserProfile.objects.create(
            user=self.user,
            org="FooOrg"
        )
        self.client.force_authenticate(user=self.user)
        self.user1 = User.objects.create(
            username='user1',
            email='user1@example.com',
            first_name="first1",
            last_name="last1",
        )
        self.user1_profile = UserProfile.objects.create(
            user=self.user1,
            name='One',
            org="FooOrg"
        )
        self.user2 = User.objects.create(
            username='user2',
            email='user2@example.com',
            first_name="first2",
            last_name="last2",
        )
        self.user2_profile = UserProfile.objects.create(
            user=self.user2,
            name='Two',
            org="FooOrg"
        )
        CourseEnrollment.objects.create(
            user=self.user1,
            course=test_course
        )
        CourseEnrollment.objects.create(
            user=self.user2,
            course=test_course
        )
        LearnerCourseJsonReport.objects.create(
            user=self.user1,
            course_id=test_course.id,
            org="FooOrg"
        )
        LearnerCourseJsonReport.objects.create(
            user=self.user2,
            course_id=test_course.id,
            org="FooOrg"
        )

    def test_get_user_progress_report_by_id(self):
        test_course = CourseOverview.objects.first()
        test_course.org = "FooOrg"
        test_course.save()
        url = reverse(
            'extended_api:user_progress_report-detail',
            args=[self.user1.id]
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("username"), self.user1.username)
        self.assertEqual(len(response.data.get("courses")), 1)
        self.assertEqual(len(response.data.get("courses")[0].keys()), 9)

    def test_get_users_progress_reports_by_ids(self):
        CourseOverview.objects.update(org="FooOrg")
        url = "{}?{}".format(
            reverse('extended_api:user_progress_report-list'),
            "?user_id={},{}".format(self.user1.id, self.user2.id)
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results")), 3)

    def test_get_user_progress_report_without_org_by_id(self):
        LearnerCourseJsonReport.objects.update(org="")
        CourseOverview.objects.update(org="")
        self.user1_profile.org = ""
        self.user1_profile.save()
        url = reverse(
            'extended_api:user_progress_report-detail',
            kwargs={'pk': self.user1.id}
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("detail"), "Not found.")

    def test_get_user_progress_report_by_username(self):
        test_course = CourseOverview.objects.first()
        test_course.org = "FooOrg"
        test_course.save()
        url = reverse(
            'extended_api:user_progress_report_by_username-detail',
            args=[self.user1.username]
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("username"), self.user1.username)
        self.assertEqual(len(response.data.get("courses")), 1)
        self.assertEqual(len(response.data.get("courses")[0].keys()), 9)

    def test_get_users_progress_reports_by_usernames(self):
        test_course = CourseOverview.objects.first()
        test_course.org = "FooOrg"
        test_course.save()
        url = "{}?{}".format(
            reverse('extended_api:user_progress_report_by_username-list'),
            "?username={},{}".format(self.user1.username, self.user2.username)
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results")), 3)

    def test_get_user_progress_report_without_org_by_username(self):
        LearnerCourseJsonReport.objects.update(org="")
        CourseOverview.objects.update(org="")
        self.user1_profile.org = ""
        self.user1_profile.save()
        url = reverse(
            'extended_api:user_progress_report_by_username-detail',
            kwargs={'username': self.user1.username}
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("detail"), "Not found.")

    def test_get_user_progress_report_by_email(self):
        test_course = CourseOverview.objects.first()
        test_course.org = "FooOrg"
        test_course.save()
        url = reverse(
            'extended_api:user_progress_report_by_email-detail',
            args=[self.user1.email]
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("email"), self.user1.email)
        self.assertEqual(len(response.data.get("courses")), 1)
        self.assertEqual(len(response.data.get("courses")[0].keys()), 9)

    def test_get_users_progress_reports_by_emails(self):
        test_course = CourseOverview.objects.first()
        test_course.org = "FooOrg"
        test_course.save()
        url = "{}?{}".format(
            reverse('extended_api:user_progress_report_by_email-list'),
            "?email={},{}".format(self.user1.email, self.user2.email)
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results")), 3)

    def test_get_user_progress_report_without_org_by_email(self):
        LearnerCourseJsonReport.objects.update(org="")
        CourseOverview.objects.update(org="")
        self.user1_profile.org = ""
        self.user1_profile.save()
        url = reverse(
            'extended_api:user_progress_report_by_email-detail',
            kwargs={'email': self.user1.email}
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("detail"), "Not found.")


class CourseProgressReportTests(CourseApiFactoryMixin, APITestCase):

    def setUp(self):
        create_mock_site_config()
        XMODULE_FACTORY_LOCK.enable()
        if not CourseOverview.objects.all() and modulestore().get_courses():
            CourseOverview.load_from_module_store(modulestore().get_courses()[0].id)
        else:
            self.create_course()

        test_course = CourseOverview.objects.first()

        self.user = User.objects.create(
            username='edx',
            is_staff=True,
            is_superuser=True,
            email='edx@example.com'
        )
        UserProfile.objects.create(
            user=self.user,
            org="FooOrg"
        )
        self.client.force_authenticate(user=self.user)
        self.user1 = User.objects.create(
            username='user1',
            email='user1@example.com',
            first_name="first1",
            last_name="last1",
        )
        self.user1_profile = UserProfile.objects.create(
            user=self.user1,
            name='One',
            org="FooOrg"
        )
        self.user2 = User.objects.create(
            username='user2',
            email='user2@example.com',
            first_name="first2",
            last_name="last2",
        )
        self.user2_profile = UserProfile.objects.create(
            user=self.user2,
            name='Two',
            org="FooOrg"
        )
        CourseEnrollment.objects.create(
            user=self.user1,
            course=test_course
        )
        CourseEnrollment.objects.create(
            user=self.user2,
            course=test_course
        )
        LearnerCourseJsonReport.objects.create(
            user=self.user1,
            course_id=test_course.id,
            org="FooOrg"
        )
        LearnerCourseJsonReport.objects.create(
            user=self.user2,
            course_id=test_course.id,
            org="FooOrg"
        )

    @unittest.skip("Test success on devstack but fails in CI")
    def test_get_course_progress_report_by_id(self):
        test_course = CourseOverview.objects.first()
        test_course.org = "FooOrg"
        test_course.save()
        url = reverse('extended_api:course_progress_report-detail', args=[text_type(test_course.id)])

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("course_id"), '%s' % test_course.id)
        self.assertEqual(len(response.data.get("enrollments")), 2)
        self.assertEqual(len(response.data.get("enrollments")[0].keys()), 9)

    @unittest.skip("Test success on devstack but fails in CI")
    def test_get_course_progress_report_without_org_by_id(self):
        test_course = CourseOverview.objects.first()
        LearnerCourseJsonReport.objects.update(org="")
        CourseOverview.objects.update(org="")
        self.user1_profile.org = ""
        self.user1_profile.save()
        url = reverse('extended_api:course_progress_report-detail', args=[text_type(test_course.id)])

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("detail"), "Not found.")


class GetUserSSOTests(APITestCase):

    def setUp(self):
        create_mock_site_config()

        self.user = User.objects.create(
            username='edx',
            is_staff=True,
            is_superuser=True,
            email='edx@example.com'
        )
        UserProfile.objects.create(
            user=self.user,
            org="FooOrg"
        )
        self.client.force_authenticate(user=self.user)
        self.user1 = User.objects.create(
            username='user1',
            email='user1@example.com',
            first_name="first1",
            last_name="last1",
        )
        self.user1_profile = UserProfile.objects.create(
            user=self.user1,
            name='One',
            org="FooOrg"
        )
        self.user1_sso = UserSocialAuth.objects.create(
            user=self.user1,
            provider=SSO_PROVIDER,
            uid='FooOrg:user1',
            extra_data={}
        )

    def test_get_user_sso_by_id(self):
        url = reverse(
            'extended_api:user_sso-detail',
            args=[self.user1.id]
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("username"), "user1")
        self.assertEqual(list(response.data.get("uid")), ['FooOrg:user1'])

    def test_get_user_sso_by_id_not_found(self):
        url = reverse(
            'extended_api:user_sso-detail',
            args=[123]
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("detail"), "Not found.")

    def test_get_user_sso_by_username(self):
        url = reverse(
            'extended_api:user_sso_by_username-detail',
            args=[self.user1.username]
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("username"), "user1")
        self.assertEqual(list(response.data.get("uid")), ['FooOrg:user1'])

    def test_get_user_sso_by_username_not_found(self):
        url = reverse(
            'extended_api:user_sso_by_username-detail',
            kwargs={'username': 'not_existing_username'}
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("detail"), "Not found.")


class UpdateUserSSOTests(APITestCase):

    def setUp(self):
        create_mock_site_config()

        self.user = User.objects.create(
            username='edx',
            is_staff=True,
            is_superuser=True,
            email='edx@example.com'
        )
        UserProfile.objects.create(
            user=self.user,
            org="FooOrg"
        )
        self.client.force_authenticate(user=self.user)
        self.user1 = User.objects.create(
            username='user1',
            email='user1@example.com',
            first_name="first1",
            last_name="last1",
        )
        self.user1_profile = UserProfile.objects.create(
            user=self.user1,
            name='One',
            org="FooOrg"
        )
        self.user1_sso = UserSocialAuth.objects.create(
            user=self.user1,
            provider=SSO_PROVIDER,
            uid='FooOrg:user1',
            extra_data={}
        )

    def test_successful_user_update_sso_by_id(self):
        url = reverse(
            'extended_api:user_sso-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "uid": ["FooOrg:user1_new_by_id"]
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('username'), 'user1')
        self.assertEqual(list(response.data.get('uid')), ["FooOrg:user1", "FooOrg:user1_new_by_id"])

    def test_user_not_found_update_sso_by_id(self):
        url = reverse(
            'extended_api:user_sso-detail',
            kwargs={'pk': 100}
        )
        data = {
            "uid": ["FooOrg:user1_new_by_id"]
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get('detail'), 'Not found.')

    def test_user_inactive_update_sso_by_id(self):
        self.user1.is_active = False
        self.user1.save()
        url = reverse(
            'extended_api:user_sso-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "uid": ["FooOrg:user1_new_by_id"]
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'User inactive')

    def test_successful_user_update_sso_by_username(self):
        url = reverse(
            'extended_api:user_sso_by_username-detail',
            kwargs={'username': self.user1.username}
        )
        data = {
            "uid": ["FooOrg:user1_new_by_username"]
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('username'), 'user1')
        self.assertEqual(list(response.data.get('uid')), ["FooOrg:user1", "FooOrg:user1_new_by_username"])

    def test_user_not_found_update_sso_by_username(self):
        url = reverse(
            'extended_api:user_sso_by_username-detail',
            kwargs={'username': 'not_existing_username'}
        )
        data = {
            "uid": ["FooOrg:user1_new_by_username"]
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get('detail'), 'Not found.')

    def test_user_inactive_update_sso_by_username(self):
        self.user1.is_active = False
        self.user1.save()
        url = reverse(
            'extended_api:user_sso_by_username-detail',
            kwargs={'username': self.user1.username}
        )
        data = {
            "uid": ["FooOrg:user1_new_by_username"]
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'User inactive')

    def test_user_update_sso_already_exist(self):
        url = reverse(
            'extended_api:user_sso-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "uid": ["FooOrg:user1"]
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'Conflicting UID')

    def test_user_update_sso_invalid(self):
        url = reverse(
            'extended_api:user_sso-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "uid": ["user1_new_by_id"]
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('detail'), 'Invalid UID')


class DeleteUserSSOTests(APITestCase):

    def setUp(self):
        create_mock_site_config()

        self.user = User.objects.create(
            username='edx',
            is_staff=True,
            is_superuser=True,
            email='edx@example.com'
        )
        UserProfile.objects.create(
            user=self.user,
            org="FooOrg"
        )
        self.client.force_authenticate(user=self.user)
        self.user1 = User.objects.create(
            username='user1',
            email='user1@example.com',
            first_name="first1",
            last_name="last1",
        )
        self.user1_profile = UserProfile.objects.create(
            user=self.user1,
            name='One',
            org="FooOrg"
        )
        self.user1_sso = UserSocialAuth.objects.create(
            user=self.user1,
            provider=SSO_PROVIDER,
            uid='FooOrg:user1',
            extra_data={}
        )
        self.user2 = User.objects.create(
            username='user2',
            email='user2@example.com',
            first_name="first2",
            last_name="last2",
        )
        self.user2_profile = UserProfile.objects.create(
            user=self.user2,
            name='Two',
            org="FooOrg"
        )
        self.user2_sso = UserSocialAuth.objects.create(
            user=self.user2,
            provider=SSO_PROVIDER,
            uid='FooOrg:user2',
            extra_data={}
        )
        self.user2_sso = UserSocialAuth.objects.create(
            user=self.user2,
            provider=SSO_PROVIDER,
            uid='FooOrg:user2_uid2',
            extra_data={}
        )

    def test_delete_user_sso_by_id(self):
        url = reverse(
            'extended_api:user_sso-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "uid": ["FooOrg:user1"]
        }

        response = self.client.delete(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("username"), self.user1.username)
        self.assertEqual(list(response.data.get("uid")), [])

    def test_delete_user_sso_by_id_inactive(self):
        self.user1.is_active = False
        self.user1.save()
        url = reverse(
            'extended_api:user_sso-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "uid": ["FooOrg:user1"]
        }

        response = self.client.delete(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get("detail"), "User inactive")

    def test_delete_user_sso_by_id_not_found(self):
        url = reverse(
            'extended_api:user_sso-detail',
            kwargs={'pk': 123}
        )
        data = {
            "uid": ["FooOrg:user1"]
        }

        response = self.client.delete(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("detail"), "Not found.")

    def test_delete_user_sso_by_username(self):
        url = reverse(
            'extended_api:user_sso_by_username-detail',
            kwargs={'username': self.user2.username}
        )
        data = {
            "uid": ["FooOrg:user2_uid2"]
        }

        response = self.client.delete(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("username"), self.user2.username)
        self.assertEqual(list(response.data.get("uid")), ["FooOrg:user2"])

    def test_delete_user_sso_by_username_inactive(self):
        self.user1.is_active = False
        self.user1.save()
        url = reverse(
            'extended_api:user_sso_by_username-detail',
            kwargs={'username': self.user1.username}
        )
        data = {
            "uid": ["FooOrg:user1"]
        }

        response = self.client.delete(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get("detail"), "User inactive")

    def test_delete_user_sso_by_username_not_found(self):
        url = reverse(
            'extended_api:user_sso_by_username-detail',
            kwargs={'username': 'not_existing_username'}
        )
        data = {
            "uid": ["FooOrg:user1"]
        }

        response = self.client.delete(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("detail"), "Not found.")

    def test_delete_user_sso_not_exist_for_user(self):
        url = reverse(
            'extended_api:user_sso-detail',
            kwargs={'pk': self.user1.id}
        )
        data = {
            "uid": ["FooOrg:user2"]
        }

        response = self.client.delete(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get("detail"), "Unknown UID")
