"""
Tests for Course API forms.
"""

from itertools import product
from urllib import urlencode

import ddt
from django.contrib.auth.models import AnonymousUser
from django.http import QueryDict

from openedx.core.djangoapps.util.test_forms import FormTestMixin
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from ..forms import CourseDetailGetForm, CourseListGetForm


class UsernameTestMixin(object):
    """
    Tests the username Form field.
    """
    shard = 4

    def test_no_user_param_anonymous_access(self):
        self.set_up_data(AnonymousUser())
        self.form_data.pop('username')
        self.assert_valid(self.cleaned_data)

    def test_no_user_param(self):
        self.set_up_data(AnonymousUser())
        self.form_data.pop('username')
        self.assert_valid(self.cleaned_data)


class TestCourseDetailGetForm(FormTestMixin, UsernameTestMixin, SharedModuleStoreTestCase):
    """
    Tests for CourseDetailGetForm
    """
    shard = 4
    FORM_CLASS = CourseDetailGetForm

    @classmethod
    def setUpClass(cls):
        super(TestCourseDetailGetForm, cls).setUpClass()

        cls.course = CourseFactory.create()

    def setUp(self):
        super(TestCourseDetailGetForm, self).setUp()

        self.student = UserFactory.create()
        self.set_up_data(self.student)

    def set_up_data(self, user):
        """
        Sets up the initial form data and the expected clean data.
        """
        self.initial = {'requesting_user': user}
        self.form_data = QueryDict(
            urlencode({
                'username': user.username,
                'course_key': unicode(self.course.id),
            }),
            mutable=True,
        )
        self.cleaned_data = {
            'username': user.username,
            'course_key': self.course.id,
        }

    def test_basic(self):
        self.assert_valid(self.cleaned_data)

    #-- course key --#

    def test_no_course_key_param(self):
        self.form_data.pop('course_key')
        self.assert_error('course_key', "This field is required.")

    def test_invalid_course_key(self):
        self.form_data['course_key'] = 'invalid_course_key'
        self.assert_error('course_key', "'invalid_course_key' is not a valid course key.")
