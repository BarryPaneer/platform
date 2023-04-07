import copy
import crum
import json

from collections import OrderedDict
from datetime import datetime
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.validators import ValidationError
from django.contrib.auth.models import User, Group
from django.contrib.admin.utils import NestedObjects
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils.translation import ugettext as _
from django_countries import countries

import accounts
import third_party_auth
from edxmako.shortcuts import marketing_link
from lms.djangoapps.program_enrollments.constants import ProgramEnrollmentStatuses
from lms.djangoapps.program_enrollments.models import ProgramEnrollment
from lms.djangoapps.program_enrollments.persistance.programs import PartialProgram
from lms.djangoapps.teams.models import ProgramAccessRole
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangolib.markup import HTML, Text
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.programs.models import ProgramsApiConfig
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.core.djangoapps.user_api.helpers import FormDescription
from openedx.core.djangoapps.user_api.models import UserPreference
from openedx.core.djangoapps.lang_pref import LANGUAGE_KEY
from openedx.features.enterprise_support.api import enterprise_customer_for_request
from student.forms import get_registration_extension_form
from student.models import CourseEnrollment, UserProfile
from student.roles import (
    STUDIO_ADMIN_ACCESS_GROUP,
    LEARNING_PATH_ADMIN_ACCESS_GROUP
)
from student.triboo_groups import (
    CATALOG_DENIED_GROUP,
    EDFLEX_DENIED_GROUP,
    CREHANA_DENIED_GROUP,
    ANDERSPINK_DENIED_GROUP,
    LEARNLIGHT_DENIED_GROUP,
    LINKEDIN_DENIED_GROUP,
    UDEMY_DENIED_GROUP,
    FOUNDERZ_DENIED_GROUP,
    SIEMENS_DENIED_GROUP,
    CENTRICAL_DENIED_GROUP
)
from student import forms as student_forms
from student import views as student_views
from student.roles import LT_DEVELOPER, LT_TESTER
from triboo_analytics.models import (
    ANALYTICS_ACCESS_GROUP,
    ANALYTICS_LIMITED_ACCESS_GROUP
)
from util.password_policy_validators import (
    password_complexity, password_instructions, password_max_length, password_min_length, validate_password
)
from util.json_request import JsonResponse
from util.date_utils import strftime_localized
from util.views import require_global_staff


FULL_USER_PROFILE_FIELDS = [
    'name',
    'service_id',
    'language',
    'location',
    'year_of_birth',
    'gender',
    'level_of_education',
    'mailing_address',
    'city',
    'country',
    'goals',
    'allow_certificate',
    'bio',
    'org',
    'lt_custom_country',
    'lt_area',
    'lt_sub_area',
    'lt_address',
    'lt_address_2',
    'lt_phone_number',
    'lt_gdpr',
    'lt_company',
    'lt_employee_id',
    'lt_hire_date',
    'lt_level',
    'lt_job_code',
    'lt_job_description',
    'lt_department',
    'lt_supervisor',
    'lt_learning_group',
    'lt_exempt_status',
    'lt_is_tos_agreed',
    'lt_comments',
    'lt_ilt_supervisor'
]


def get_password_reset_form():
    """Return a description of the password reset form.

    This decouples clients from the API definition:
    if the API decides to modify the form, clients won't need
    to be updated.

    See `user_api.helpers.FormDescription` for examples
    of the JSON-encoded form description.

    Returns:
        HttpResponse

    """
    form_desc = FormDescription("post", reverse("password_change_request"))

    # Translators: This label appears above a field on the password reset
    # form meant to hold the user's email address.
    email_label = _(u"Email")

    # Translators: This example email address is used as a placeholder in
    # a field on the password reset form meant to hold the user's email address.
    email_placeholder = _(u"username@domain.com")

    # Translators: These instructions appear on the password reset form,
    # immediately below a field meant to hold the user's email address.
    email_instructions = _(u"The email address you used to register with {platform_name}").format(
        platform_name=configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME)
    )

    form_desc.add_field(
        "email",
        field_type="email",
        label=email_label,
        placeholder=email_placeholder,
        instructions=email_instructions,
        restrictions={
            "min_length": accounts.EMAIL_MIN_LENGTH,
            "max_length": accounts.EMAIL_MAX_LENGTH,
        }
    )

    return form_desc


def get_login_session_form(request):
    """Return a description of the login form.

    This decouples clients from the API definition:
    if the API decides to modify the form, clients won't need
    to be updated.

    See `user_api.helpers.FormDescription` for examples
    of the JSON-encoded form description.

    Returns:
        HttpResponse

    """
    form_desc = FormDescription("post", reverse("user_api_login_session"))
    _apply_third_party_auth_overrides(request, form_desc)

    # Translators: This label appears above a field on the login form
    # meant to hold the user's email address.
    email_label = _(u"Email")

    # Translators: This example email address is used as a placeholder in
    # a field on the login form meant to hold the user's email address.
    email_placeholder = _(u"username@domain.com")

    # Translators: These instructions appear on the login form, immediately
    # below a field meant to hold the user's email address.
    email_instructions = _("The email address you used to register with {platform_name}").format(
        platform_name=configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME)
    )

    form_desc.add_field(
        "email",
        field_type="text",
        label=email_label,
        placeholder=email_placeholder,
        instructions=email_instructions,
        restrictions={
            "min_length": accounts.EMAIL_MIN_LENGTH,
            "max_length": accounts.EMAIL_MAX_LENGTH,
        }
    )

    # Translators: This label appears above a field on the login form
    # meant to hold the user's password.
    password_label = _(u"Password")

    form_desc.add_field(
        "password",
        label=password_label,
        field_type="password",
        restrictions={
            "max_length": password_max_length(),
        }
    )

    form_desc.add_field(
        "remember",
        field_type="checkbox",
        label=_("Remember me"),
        default=False,
        required=False,
    )

    return form_desc


def _apply_third_party_auth_overrides(request, form_desc):
    """Modify the login form if the user has authenticated with a third-party provider.
    If a user has successfully authenticated with a third-party provider,
    and an email is associated with it then we fill in the email field with readonly property.
    Arguments:
        request (HttpRequest): The request for the registration form, used
            to determine if the user has successfully authenticated
            with a third-party provider.
        form_desc (FormDescription): The registration form description
    """
    if third_party_auth.is_enabled():
        running_pipeline = third_party_auth.pipeline.get(request)
        if running_pipeline:
            current_provider = third_party_auth.provider.Registry.get_from_pipeline(running_pipeline)
            if current_provider and enterprise_customer_for_request(request):
                pipeline_kwargs = running_pipeline.get('kwargs')

                # Details about the user sent back from the provider.
                details = pipeline_kwargs.get('details')
                email = details.get('email', '')

                # override the email field.
                form_desc.override_field_properties(
                    "email",
                    default=email,
                    restrictions={"readonly": "readonly"} if email else {
                        "min_length": accounts.EMAIL_MIN_LENGTH,
                        "max_length": accounts.EMAIL_MAX_LENGTH,
                    }
                )


class RegistrationFormFactory(object):
    """HTTP end-points for creating a new user. """

    DEFAULT_FIELDS = ["email", "name", "username", "password"]

    EXTRA_FIELDS = [
        "confirm_email",
        "first_name",
        "last_name",
        "city",
        "state",
        "country",
        "gender",
        "year_of_birth",
        "level_of_education",
        "company",
        "job_title",
        "title",
        "mailing_address",
        "goals",
        "honor_code",
        "terms_of_service",
        "profession",
        "specialty",
        "lt_phone_number",
        "lt_gdpr",
        "lt_company",
        "lt_job_code",
        "lt_job_description",
        "lt_department",
        "lt_learning_group",
        "lt_comments",
    ]

    def _is_field_visible(self, field_name):
        """Check whether a field is visible based on Django settings. """
        return self._extra_fields_setting.get(field_name) in ["required", "optional"]

    def _is_field_required(self, field_name):
        """Check whether a field is required based on Django settings. """
        return self._extra_fields_setting.get(field_name) == "required"

    def __init__(self):

        # Backwards compatibility: Honor code is required by default, unless
        # explicitly set to "optional" in Django settings.
        self._extra_fields_setting = copy.deepcopy(configuration_helpers.get_value('REGISTRATION_EXTRA_FIELDS'))
        if not self._extra_fields_setting:
            self._extra_fields_setting = copy.deepcopy(settings.REGISTRATION_EXTRA_FIELDS)
        self._extra_fields_setting["honor_code"] = self._extra_fields_setting.get("honor_code", "required")

        # Check that the setting is configured correctly
        for field_name in self.EXTRA_FIELDS:
            if self._extra_fields_setting.get(field_name, "hidden") not in ["required", "optional", "hidden"]:
                msg = u"Setting REGISTRATION_EXTRA_FIELDS values must be either required, optional, or hidden."
                raise ImproperlyConfigured(msg)

        # Map field names to the instance method used to add the field to the form
        self.field_handlers = {}
        valid_fields = self.DEFAULT_FIELDS + self.EXTRA_FIELDS
        for field_name in valid_fields:
            handler = getattr(self, "_add_{field_name}_field".format(field_name=field_name))
            self.field_handlers[field_name] = handler

        field_order = configuration_helpers.get_value('REGISTRATION_FIELD_ORDER')
        if not field_order:
            field_order = settings.REGISTRATION_FIELD_ORDER or valid_fields

        # Check that all of the valid_fields are in the field order and vice versa, if not set to the default order
        # if set(valid_fields) != set(field_order):
        #     field_order = valid_fields
        field_order = [field for field in field_order if field in valid_fields]

        self.field_order = field_order

    def get_registration_form(self, request):
        """Return a description of the registration form.
        This decouples clients from the API definition:
        if the API decides to modify the form, clients won't need
        to be updated.
        This is especially important for the registration form,
        since different edx-platform installations might
        collect different demographic information.
        See `user_api.helpers.FormDescription` for examples
        of the JSON-encoded form description.
        Arguments:
            request (HttpRequest)
        Returns:
            HttpResponse
        """
        form_desc = FormDescription("post", reverse("user_api_registration"))
        self._apply_third_party_auth_overrides(request, form_desc)

        # Custom form fields can be added via the form set in settings.REGISTRATION_EXTENSION_FORM
        custom_form = get_registration_extension_form()

        if custom_form:
            # Default fields are always required
            for field_name in self.DEFAULT_FIELDS:
                self.field_handlers[field_name](form_desc, required=True)

            for field_name, field in custom_form.fields.items():
                restrictions = {}
                if getattr(field, 'max_length', None):
                    restrictions['max_length'] = field.max_length
                if getattr(field, 'min_length', None):
                    restrictions['min_length'] = field.min_length
                field_options = getattr(
                    getattr(custom_form, 'Meta', None), 'serialization_options', {}
                ).get(field_name, {})
                field_type = field_options.get('field_type', FormDescription.FIELD_TYPE_MAP.get(field.__class__))
                if not field_type:
                    raise ImproperlyConfigured(
                        "Field type '{}' not recognized for registration extension field '{}'.".format(
                            field_type,
                            field_name
                        )
                    )
                form_desc.add_field(
                    field_name, label=field.label,
                    default=field_options.get('default'),
                    field_type=field_options.get('field_type', FormDescription.FIELD_TYPE_MAP.get(field.__class__)),
                    placeholder=field.initial, instructions=field.help_text, required=field.required,
                    restrictions=restrictions,
                    options=getattr(field, 'choices', None), error_messages=field.error_messages,
                    include_default_option=field_options.get('include_default_option'),
                )

            # Extra fields configured in Django settings
            # may be required, optional, or hidden
            for field_name in self.EXTRA_FIELDS:
                if self._is_field_visible(field_name):
                    self.field_handlers[field_name](
                        form_desc,
                        required=self._is_field_required(field_name)
                    )
        else:
            # Go through the fields in the fields order and add them if they are required or visible
            for field_name in self.field_order:
                if field_name in self.DEFAULT_FIELDS:
                    self.field_handlers[field_name](form_desc, required=True)
                elif self._is_field_visible(field_name):
                    self.field_handlers[field_name](
                        form_desc,
                        required=self._is_field_required(field_name)
                    )

        return form_desc

    def get_admin_panel_registration_form(self, request):
        """
        Return a description of the registration form.
        This is used in Admin Panel user creation/ edit
        The form_desc includes a complete list of fields
        Arguments:
            request (HttpRequest)
        Returns:
            HttpResponse
        """
        form_desc = FormDescription("post", reverse("user_api_registration"))
        self._apply_third_party_auth_overrides(request, form_desc)

        # Go through the fields in the fields order and add them if they are required or visible
        for field_name in self.field_order:
            if field_name in self.DEFAULT_FIELDS:
                self.field_handlers[field_name](form_desc, required=True)
            else:
                self.field_handlers[field_name](
                    form_desc,
                    required=False
                )

        return form_desc

    def _add_email_field(self, form_desc, required=True):
        """Add an email field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """
        # Translators: This label appears above a field on the registration form
        # meant to hold the user's email address.
        email_label = _(u"Email")

        # Translators: These instructions appear on the registration form, immediately
        # below a field meant to hold the user's email address.
        email_instructions = _(u"This is what you will use to login.")

        form_desc.add_field(
            "email",
            field_type="email",
            label=email_label,
            instructions=email_instructions,
            restrictions={
                "min_length": accounts.EMAIL_MIN_LENGTH,
                "max_length": accounts.EMAIL_MAX_LENGTH,
            },
            required=required
        )

    def _add_confirm_email_field(self, form_desc, required=True):
        """Add an email confirmation field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """
        # Translators: This label appears above a field on the registration form
        # meant to confirm the user's email address.
        email_label = _(u"Confirm Email")

        error_msg = accounts.REQUIRED_FIELD_CONFIRM_EMAIL_MSG

        form_desc.add_field(
            "confirm_email",
            label=email_label,
            required=required,
            error_messages={
                "required": error_msg
            }
        )

    def _add_name_field(self, form_desc, required=True):
        """Add a name field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """
        # Translators: This label appears above a field on the registration form
        # meant to hold the user's full name.
        name_label = _(u"Full Name")

        # Translators: These instructions appear on the registration form, immediately
        # below a field meant to hold the user's full name.
        name_instructions = _(u"This name will be used on any certificates that you earn.")

        form_desc.add_field(
            "name",
            label=name_label,
            instructions=name_instructions,
            restrictions={
                "max_length": accounts.NAME_MAX_LENGTH,
            },
            required=required
        )

    def _add_username_field(self, form_desc, required=True):
        """Add a username field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """
        # Translators: This label appears above a field on the registration form
        # meant to hold the user's public username.
        username_label = _(u"Public Username")

        username_instructions = _(
            # Translators: These instructions appear on the registration form, immediately
            # below a field meant to hold the user's public username.
            u"The name that will identify you in your courses. "
            u"It cannot be changed later."
        )
        form_desc.add_field(
            "username",
            label=username_label,
            instructions=username_instructions,
            restrictions={
                "min_length": accounts.USERNAME_MIN_LENGTH,
                "max_length": accounts.USERNAME_MAX_LENGTH,
            },
            required=required
        )

    def _add_password_field(self, form_desc, required=True):
        """Add a password field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """
        # Translators: This label appears above a field on the registration form
        # meant to hold the user's password.
        password_label = _(u"Password")

        restrictions = {
            "min_length": password_min_length(),
            "max_length": password_max_length(),
        }

        complexities = password_complexity()
        for key, value in complexities.iteritems():
            api_key = key.lower().replace(' ', '_')
            restrictions[api_key] = value

        form_desc.add_field(
            "password",
            label=password_label,
            field_type="password",
            instructions=password_instructions(),
            restrictions=restrictions,
            required=required
        )

    def _add_level_of_education_field(self, form_desc, required=True):
        """Add a level of education field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """
        # Translators: This label appears above a dropdown menu on the registration
        # form used to select the user's highest completed level of education.
        education_level_label = _(u"Highest level of education completed")
        error_msg = accounts.REQUIRED_FIELD_LEVEL_OF_EDUCATION_MSG

        # The labels are marked for translation in UserProfile model definition.
        options = [(name, _(label)) for name, label in UserProfile.LEVEL_OF_EDUCATION_CHOICES]  # pylint: disable=translation-of-non-string
        form_desc.add_field(
            "level_of_education",
            label=education_level_label,
            field_type="select",
            options=options,
            include_default_option=True,
            required=required,
            error_messages={
                "required": error_msg
            }
        )

    def _add_gender_field(self, form_desc, required=True):
        """Add a gender field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """
        # Translators: This label appears above a dropdown menu on the registration
        # form used to select the user's gender.
        gender_label = _(u"Gender")

        # The labels are marked for translation in UserProfile model definition.
        options = [(name, _(label)) for name, label in UserProfile.GENDER_CHOICES]  # pylint: disable=translation-of-non-string
        form_desc.add_field(
            "gender",
            label=gender_label,
            field_type="select",
            options=options,
            include_default_option=True,
            required=required
        )

    def _add_year_of_birth_field(self, form_desc, required=True):
        """Add a year of birth field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """
        # Translators: This label appears above a dropdown menu on the registration
        # form used to select the user's year of birth.
        yob_label = _(u"Year of birth")

        options = [(unicode(year), unicode(year)) for year in UserProfile.VALID_YEARS]
        form_desc.add_field(
            "year_of_birth",
            label=yob_label,
            field_type="select",
            options=options,
            include_default_option=True,
            required=required
        )

    def _add_field_with_configurable_select_options(self, field_name, field_label, form_desc, required=False):
        """Add a field to a form description.
            If select options are given for this field, it will be a select type
            otherwise it will be a text type.

        Arguments:
            field_name: name of field
            field_label: label for the field
            form_desc: A form description

        Keyword Arguments:
            required (bool): Whether this field is required; defaults to False

        """

        extra_field_options = configuration_helpers.get_value('EXTRA_FIELD_OPTIONS')
        if extra_field_options is None or extra_field_options.get(field_name) is None:
            field_type = "text"
            include_default_option = False
            options = None
            error_msg = ''
            exec("error_msg = accounts.REQUIRED_FIELD_%s_TEXT_MSG" % (field_name.upper()))
        else:
            field_type = "select"
            include_default_option = True
            field_options = extra_field_options.get(field_name)
            options = [(unicode(option.lower()), option) for option in field_options]
            error_msg = ''
            exec("error_msg = accounts.REQUIRED_FIELD_%s_SELECT_MSG" % (field_name.upper()))

        form_desc.add_field(
            field_name,
            label=field_label,
            field_type=field_type,
            options=options,
            include_default_option=include_default_option,
            required=required,
            error_messages={
                "required": error_msg
            }
        )

    def _add_profession_field(self, form_desc, required=False):
        """Add a profession field to a form description.

        Arguments:
            form_desc: A form description

        Keyword Arguments:
            required (bool): Whether this field is required; defaults to False

        """
        # Translators: This label appears above a dropdown menu on the registration
        # form used to select the user's profession
        profession_label = _("Profession")

        self._add_field_with_configurable_select_options('profession', profession_label, form_desc, required=required)

    def _add_specialty_field(self, form_desc, required=False):
        """Add a specialty field to a form description.

        Arguments:
            form_desc: A form description

        Keyword Arguments:
            required (bool): Whether this field is required; defaults to False

        """
        # Translators: This label appears above a dropdown menu on the registration
        # form used to select the user's specialty
        specialty_label = _("Specialty")

        self._add_field_with_configurable_select_options('specialty', specialty_label, form_desc, required=required)

    def _add_mailing_address_field(self, form_desc, required=True):
        """Add a mailing address field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """
        # Translators: This label appears above a field on the registration form
        # meant to hold the user's mailing address.
        mailing_address_label = _(u"Mailing address")
        error_msg = accounts.REQUIRED_FIELD_MAILING_ADDRESS_MSG

        form_desc.add_field(
            "mailing_address",
            label=mailing_address_label,
            field_type="textarea",
            required=required,
            error_messages={
                "required": error_msg
            }
        )

    def _add_goals_field(self, form_desc, required=True):
        """Add a goals field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """
        # Translators: This phrase appears above a field on the registration form
        # meant to hold the user's reasons for registering with edX.
        goals_label = _(u"Tell us why you're interested in {platform_name}").format(
            platform_name=configuration_helpers.get_value("PLATFORM_NAME", settings.PLATFORM_NAME)
        )
        error_msg = accounts.REQUIRED_FIELD_GOALS_MSG

        form_desc.add_field(
            "goals",
            label=goals_label,
            field_type="textarea",
            required=required,
            error_messages={
                "required": error_msg
            }
        )

    def _add_city_field(self, form_desc, required=True):
        """Add a city field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """
        # Translators: This label appears above a field on the registration form
        # which allows the user to input the city in which they live.
        city_label = _(u"City")
        error_msg = accounts.REQUIRED_FIELD_CITY_MSG

        form_desc.add_field(
            "city",
            label=city_label,
            required=required,
            error_messages={
                "required": error_msg
            }
        )

    def _add_state_field(self, form_desc, required=False):
        """Add a State/Province/Region field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to False
        """
        # Translators: This label appears above a field on the registration form
        # which allows the user to input the State/Province/Region in which they live.
        state_label = _(u"State/Province/Region")

        form_desc.add_field(
            "state",
            label=state_label,
            required=required
        )

    def _add_company_field(self, form_desc, required=False):
        """Add a Company field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to False
        """
        # Translators: This label appears above a field on the registration form
        # which allows the user to input the Company
        company_label = _(u"Company")

        form_desc.add_field(
            "company",
            label=company_label,
            required=required
        )

    def _add_title_field(self, form_desc, required=False):
        """Add a Title field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to False
        """
        # Translators: This label appears above a field on the registration form
        # which allows the user to input the Title
        title_label = _(u"Title")

        form_desc.add_field(
            "title",
            label=title_label,
            required=required
        )

    def _add_job_title_field(self, form_desc, required=False):
        """Add a Job Title field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to False
        """
        # Translators: This label appears above a field on the registration form
        # which allows the user to input the Job Title
        job_title_label = _(u"Job Title")

        form_desc.add_field(
            "job_title",
            label=job_title_label,
            required=required
        )

    def _add_first_name_field(self, form_desc, required=False):
        """Add a First Name field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to False
        """
        # Translators: This label appears above a field on the registration form
        # which allows the user to input the First Name
        first_name_label = _(u"First Name")

        form_desc.add_field(
            "first_name",
            label=first_name_label,
            required=required
        )

    def _add_last_name_field(self, form_desc, required=False):
        """Add a Last Name field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to False
        """
        # Translators: This label appears above a field on the registration form
        # which allows the user to input the First Name
        last_name_label = _(u"Last Name")

        form_desc.add_field(
            "last_name",
            label=last_name_label,
            required=required
        )

    def _add_country_field(self, form_desc, required=True):
        """Add a country field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """
        # Translators: This label appears above a dropdown menu on the registration
        # form used to select the country in which the user lives.
        country_label = _(u"Country or Region of Residence")

        error_msg = accounts.REQUIRED_FIELD_COUNTRY_MSG

        # If we set a country code, make sure it's uppercase for the sake of the form.
        # pylint: disable=protected-access
        default_country = form_desc._field_overrides.get('country', {}).get('defaultValue')

        country_instructions = _(
            # Translators: These instructions appear on the registration form, immediately
            # below a field meant to hold the user's country.
            u"The country or region where you live."
        )
        if default_country:
            form_desc.override_field_properties(
                'country',
                default=default_country.upper()
            )

        form_desc.add_field(
            "country",
            label=country_label,
            instructions=country_instructions,
            field_type="select",
            options=list(countries),
            include_default_option=True,
            required=required,
            error_messages={
                "required": error_msg
            }
        )

    def _add_honor_code_field(self, form_desc, required=True):
        """Add an honor code field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """

        separate_honor_and_tos = self._is_field_visible("terms_of_service")
        # Separate terms of service and honor code checkboxes
        if separate_honor_and_tos:
            terms_label = _(u"Honor Code")
            terms_link = marketing_link("HONOR")

        # Combine terms of service and honor code checkboxes
        else:
            # Translators: This is a legal document users must agree to
            # in order to register a new account.
            terms_label = _(u"Terms of Service and Honor Code")
            terms_link = marketing_link("HONOR")

        # Translators: "Terms of Service" is a legal document users must agree to
        # in order to register a new account.
        label = Text(_(
            u"I agree to the {platform_name} {terms_of_service_link_start}{terms_of_service}{terms_of_service_link_end}"
        )).format(
            platform_name=configuration_helpers.get_value("PLATFORM_NAME", settings.PLATFORM_NAME),
            terms_of_service=terms_label,
            terms_of_service_link_start=HTML("<a href='{terms_link}' target='_blank'>").format(terms_link=terms_link),
            terms_of_service_link_end=HTML("</a>"),
        )

        # Translators: "Terms of Service" is a legal document users must agree to
        # in order to register a new account.
        error_msg = _(u"You must agree to the {platform_name} {terms_of_service}").format(
            platform_name=configuration_helpers.get_value("PLATFORM_NAME", settings.PLATFORM_NAME),
            terms_of_service=terms_label
        )
        field_type = 'checkbox'

        if not separate_honor_and_tos:
            current_request = crum.get_current_request()

            field_type = 'plaintext'

            tos_label = _(u"Terms of Service")
            tos_link = marketing_link("TOS")

            honor_label = (u"Honor Code")
            honor_link  = marketing_link("HONOR")

            pp_link = marketing_link("PRIVACY")
            label = Text(_(
                u"By creating an account with {platform_name}, you agree \
                  to abide by our {platform_name} \
                  {terms_of_service_link_start}{terms_of_service}{terms_of_service_link_end} and {honor_link_start}{honor_code}{honor_link_end} \
                  and agree to our {privacy_policy_link_start}Privacy Policy{privacy_policy_link_end}."
            )).format(
                platform_name=configuration_helpers.get_value("PLATFORM_NAME", settings.PLATFORM_NAME),
                terms_of_service_link_start=HTML("<a href='{tos_url}' target='_blank'>").format(tos_url=tos_link),
                terms_of_service=tos_label,
                terms_of_service_link_end=HTML("</a>"),
                honor_link_start=HTML("<a href='{honor_url}' target='_blank'>").format(honor_url=honor_link),
                honor_code=honor_label,
                honor_link_end=HTML("</a>"),
                privacy_policy_link_start=HTML("<a href='{pp_url}' target='_blank'>").format(pp_url=pp_link),
                privacy_policy_link_end=HTML("</a>"),
            )

        form_desc.add_field(
            "honor_code",
            label=label,
            field_type=field_type,
            default=False,
            required=required,
            error_messages={
                "required": error_msg
            },
        )

    def _add_terms_of_service_field(self, form_desc, required=True):
        """Add a terms of service field to a form description.
        Arguments:
            form_desc: A form description
        Keyword Arguments:
            required (bool): Whether this field is required; defaults to True
        """
        # Translators: This is a legal document users must agree to
        # in order to register a new account.
        terms_label = _(u"Terms of Service")
        terms_link = marketing_link("TOS")

        # Translators: "Terms of service" is a legal document users must agree to
        # in order to register a new account.
        label = Text(_(u"I agree to the {platform_name} {tos_link_start}{terms_of_service}{tos_link_end}")).format(
            platform_name=configuration_helpers.get_value("PLATFORM_NAME", settings.PLATFORM_NAME),
            terms_of_service=terms_label,
            tos_link_start=HTML("<a href='{terms_link}' target='_blank'>").format(terms_link=terms_link),
            tos_link_end=HTML("</a>"),
        )

        # Translators: "Terms of service" is a legal document users must agree to
        # in order to register a new account.
        error_msg = _(u"You must agree to the {platform_name} {terms_of_service}").format(
            platform_name=configuration_helpers.get_value("PLATFORM_NAME", settings.PLATFORM_NAME),
            terms_of_service=terms_label
        )

        form_desc.add_field(
            "terms_of_service",
            label=label,
            field_type="checkbox",
            default=False,
            required=required,
            error_messages={
                "required": error_msg
            },
        )

    def _add_lt_phone_number_field(self, form_desc, required=False):
        form_desc.add_field(
            "lt_phone_number",
            label=_(u"Phone number"),
            required=required
        )

    def _add_lt_gdpr_field(self, form_desc, required=False):
        gdpr_label = _(u"I agree to be contacted by email or phone as part of a recruitment process.")
        form_desc.add_field(
            "lt_gdpr",
            label=gdpr_label,
            field_type="checkbox",
            default=False,
            required=required
        )

    def _add_lt_company_field(self, form_desc, required=False):
        form_desc.add_field(
            "lt_company",
            label=_(u"Company"),
            required=required
        )

    def _add_lt_job_code_field(self, form_desc, required=False):
        form_desc.add_field(
            "lt_job_code",
            label=_(u"Job Code"),
            required=required
        )

    def _add_lt_job_description_field(self, form_desc, required=False):
        form_desc.add_field(
            "lt_job_description",
            label=_(u"Job Description"),
            required=required
        )

    def _add_lt_department_field(self, form_desc, required=False):
        form_desc.add_field(
            "lt_department",
            label=_(u"Department"),
            required=required
        )

    def _add_lt_learning_group_field(self, form_desc, required=False):
        form_desc.add_field(
            "lt_learning_group",
            label=_(u"Learning Group"),
            required=required
        )

    def _add_lt_comments_field(self, form_desc, required=False):
        form_desc.add_field(
            "lt_comments",
            label=_(u"Comments"),
            required=required
        )


    def _apply_third_party_auth_overrides(self, request, form_desc):
        """Modify the registration form if the user has authenticated with a third-party provider.
        If a user has successfully authenticated with a third-party provider,
        but does not yet have an account with EdX, we want to fill in
        the registration form with any info that we get from the
        provider.
        This will also hide the password field, since we assign users a default
        (random) password on the assumption that they will be using
        third-party auth to log in.
        Arguments:
            request (HttpRequest): The request for the registration form, used
                to determine if the user has successfully authenticated
                with a third-party provider.
            form_desc (FormDescription): The registration form description
        """
        if third_party_auth.is_enabled():
            running_pipeline = third_party_auth.pipeline.get(request)
            if running_pipeline:
                current_provider = third_party_auth.provider.Registry.get_from_pipeline(running_pipeline)

                if current_provider:
                    # Override username / email / full name
                    field_overrides = current_provider.get_register_form_data(
                        running_pipeline.get('kwargs')
                    )

                    # When the TPA Provider is configured to skip the registration form and we are in an
                    # enterprise context, we need to hide all fields except for terms of service and
                    # ensure that the user explicitly checks that field.
                    hide_registration_fields_except_tos = (
                        (
                            current_provider.skip_registration_form and enterprise_customer_for_request(request)
                        ) or current_provider.sync_learner_profile_data
                    )

                    for field_name in self.DEFAULT_FIELDS + self.EXTRA_FIELDS:
                        if field_name in field_overrides:
                            form_desc.override_field_properties(
                                field_name, default=field_overrides[field_name]
                            )

                            if (field_name not in ['terms_of_service', 'honor_code']
                                    and field_overrides[field_name]
                                    and hide_registration_fields_except_tos):

                                form_desc.override_field_properties(
                                    field_name,
                                    field_type="hidden",
                                    label="",
                                    instructions="",
                                )

                    # Hide the password field
                    form_desc.override_field_properties(
                        "password",
                        default="",
                        field_type="hidden",
                        required=False,
                        label="",
                        instructions="",
                        restrictions={}
                    )
                    # used to identify that request is running third party social auth
                    form_desc.add_field(
                        "social_auth_provider",
                        field_type="hidden",
                        label="",
                        default=current_provider.name if current_provider.name else "Third Party",
                        required=False,
                    )


def get_user_account_info(user):
    profile_fields = configuration_helpers.get_value(
        'ANALYTICS_USER_PROPERTIES',
        settings.FEATURES.get('ANALYTICS_USER_PROPERTIES', {})
    )
    profile_fields.update({'name': 'optional'})
    context = {
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_active': user.is_active,
        'user_id': user.id,
        'org': user.profile.org
    }
    user_groups = [group.name for group in user.groups.all()]

    analytics_access = '0'
    if ANALYTICS_ACCESS_GROUP in user_groups:
        analytics_access = '2'  # full access
    if ANALYTICS_LIMITED_ACCESS_GROUP in user_groups:
        analytics_access = '1'  # restricted

    platform_level = '0'  # learner
    if user.is_superuser:
        platform_level = '3'  # super admin
        analytics_access = '2'  # full access
    elif user.is_staff:
        platform_level = '2'  # platform admin
        analytics_access = '2'  # full access
    else:
        if LEARNING_PATH_ADMIN_ACCESS_GROUP in user_groups and STUDIO_ADMIN_ACCESS_GROUP in user_groups:
            platform_level = '4'    # Studio Super Admin
        elif STUDIO_ADMIN_ACCESS_GROUP in user_groups:
            platform_level = '1'    # Studio Admin

    catalog_access = False if CATALOG_DENIED_GROUP in user_groups else True
    edflex_access = False if EDFLEX_DENIED_GROUP in user_groups else True
    crehana_access = False if CREHANA_DENIED_GROUP in user_groups else True
    anderspink_access = False if ANDERSPINK_DENIED_GROUP in user_groups else True
    learnlight_access = False if LEARNLIGHT_DENIED_GROUP in user_groups else True
    linkedin_access = False if LINKEDIN_DENIED_GROUP in user_groups else True
    udemy_access = False if UDEMY_DENIED_GROUP in user_groups else True
    founderz_access = False if FOUNDERZ_DENIED_GROUP in user_groups else True
    siemens_access = False if SIEMENS_DENIED_GROUP in user_groups else True
    triboo_centrical_access = False if CENTRICAL_DENIED_GROUP in user_groups else True

    permissions = {
        "platform_level": platform_level,
        "catalog_access": catalog_access,
        "edflex_access": edflex_access,
        "crehana_access": crehana_access,
        "anderspink_access": anderspink_access,
        "learnlight_access": learnlight_access,
        "linkedin_access": linkedin_access,
        "udemy_access": udemy_access,
        "founderz_access": founderz_access,
        "siemens_access": siemens_access,
        "analytics_access": analytics_access,
        "triboo_centrical_access": triboo_centrical_access
    }

    profile_info = {key: getattr(user.profile, key) for key in profile_fields if key in FULL_USER_PROFILE_FIELDS}
    if 'country' in profile_info:
        profile_info['country'] = profile_info['country'].code
    if 'lt_hire_date' in profile_info:
        if profile_info['lt_hire_date']:
            profile_info['lt_hire_date'] = strftime_localized(profile_info['lt_hire_date'], "NUMBERIC_SHORT_DATE_SLASH")

    orgs = configuration_helpers.get_current_site_orgs()
    courses = CourseOverview.objects.filter(org__in=orgs)
    course_ids = {c.id: c.display_name for c in courses}
    enrollments = CourseEnrollment.enrollments_for_user(user).filter(course_id__in=course_ids)
    enrolled_course_ids = [i.course_id for i in enrollments]
    currently_enrolled = [{
        "name": course_ids.get(i.course_id), "course_id": unicode(i.course_id),
        "created": strftime_localized(i.created, "NUMBERIC_SHORT_DATE_SLASH"),
        "completed": strftime_localized(i.completed, "NUMBERIC_SHORT_DATE_SLASH") if i.completed else "-"
    } for i in enrollments]
    not_enrolled = [{"name": course_ids.get(i), "course_id": unicode(i)}
                    for i in course_ids if i not in enrolled_course_ids]
    currently_enrolled.sort(key=lambda x: x['name'].lower())
    not_enrolled.sort(key=lambda x: x['name'].lower())
    context.update(profile_info)
    context.update(permissions)
    context.update({
        "currently_enrolled": currently_enrolled, "not_enrolled": not_enrolled, "profile_fields": profile_fields
    })

    context.update({'language': UserPreference.get_value(user, LANGUAGE_KEY, '')})

    return context


@require_global_staff
def get_user_full_account_info(request, user_id):
    user = User.objects.select_related('profile').get(id=user_id)
    user_fields = [
        "username",
        "email",
        "first_name",
        "last_name",
        'is_active',
        'is_superuser',
        'is_staff'
    ]

    if request.method == "POST":
        if user.is_superuser and not request.user.is_superuser:
            return JsonResponse(status=403)
        update = json.loads(request.body)
        field_errors = {}
        if "email" in update:
            new_email = update["email"]

            try:
                student_views.validate_new_email(user, new_email)
            except ValueError as err:
                field_errors["email"] = {
                    "developer_message": u"Error thrown from validate_new_email: '{}'".format(unicode(err)),
                    "user_message": unicode(err)
                }

        if "name" in update:
            try:
                student_forms.validate_name(update['name'])
            except ValidationError as err:
                field_errors["name"] = {
                    "developer_message": u"Error thrown from validate_name: '{}'".format(err.message),
                    "user_message": err.message
                }
        if "password" in update:
            try:
                validate_password(update["password"], user=user)
                user.set_password(update["password"])
                user.save()
            except ValidationError as err:
                field_errors["password"] = {
                    "developer_message": u"Error thrown from validate_password: '{}'".format(err.message),
                    "user_message": err.message
                }

        if "year_of_birth" in update:
            year_str = update["year_of_birth"]
            update["year_of_birth"] = int(year_str) if year_str is not None else None

        if "platform_level" in update:

            def is_program_powered_role(user):
                """Only Platform Super Admin / Platform Admin / Studio Super Admin could access programs
                """
                user_groups = [group.name for group in user.groups.all()]

                return user.is_staff or user.is_superuser or (
                        STUDIO_ADMIN_ACCESS_GROUP in user_groups and LEARNING_PATH_ADMIN_ACCESS_GROUP in user_groups
                )

            platform_level = update.pop("platform_level")
            if ProgramsApiConfig.is_student_dashboard_enabled() and \
                    is_program_powered_role(user) and \
                    platform_level in ('0', '1'):
                user_programs_team_count = ProgramAccessRole.objects.filter(
                    user_id=user.id
                ).values(
                    'program_id'
                ).distinct().count()

                if user_programs_team_count > 0:
                    return JsonResponse(
                        {
                            'user_programs_team_count': user_programs_team_count
                        },
                        status=409
                    )

            studio_admin_group = Group.objects.get(name=STUDIO_ADMIN_ACCESS_GROUP)
            program_admin_group = Group.objects.get(name=LEARNING_PATH_ADMIN_ACCESS_GROUP)
            if platform_level == "0":
                update["is_staff"] = False
                update["is_superuser"] = False
                user.groups.remove(studio_admin_group)
                user.groups.remove(program_admin_group)     # Role: `Learner`
            elif platform_level == "1":
                update["is_staff"] = False
                update["is_superuser"] = False
                user.groups.add(studio_admin_group)
                user.groups.remove(program_admin_group)     # Role: `Studio Admin`
            elif platform_level == "4":
                update["is_staff"] = False
                update["is_superuser"] = False
                user.groups.add(studio_admin_group)
                user.groups.add(program_admin_group)        # Role: Studio Super Admin
            elif platform_level == "2":
                update["is_staff"] = True
                update["is_superuser"] = False
                # user.groups.remove(program_admin_group)
                # user.groups.remove(studio_admin_group)      # Role: Platform Admin
            else:
                if request.user.is_superuser:
                    update["is_staff"] = True
                    update["is_superuser"] = True
                    # user.groups.remove(program_admin_group)
                    # user.groups.remove(studio_admin_group)      # Role: Platform Super
                else:
                    return JsonResponse(status=403) 

        if "catalog_access" in update:
            catalog_denied_group = Group.objects.get(name=CATALOG_DENIED_GROUP)
            catalog_access = update.pop("catalog_access")
            if catalog_access:
                user.groups.remove(catalog_denied_group)
            else:
                user.groups.add(catalog_denied_group)

        if "edflex_access" in update:
            edflex_denied_group = Group.objects.get(name=EDFLEX_DENIED_GROUP)
            edflex_access = update.pop("edflex_access")
            if edflex_access:
                user.groups.remove(edflex_denied_group)
            else:
                user.groups.add(edflex_denied_group)

        if "crehana_access" in update:
            crehana_denied_group = Group.objects.get(name=CREHANA_DENIED_GROUP)
            crehana_access = update.pop("crehana_access")
            if crehana_access:
                user.groups.remove(crehana_denied_group)
            else:
                user.groups.add(crehana_denied_group)

        if "anderspink_access" in update:
            anderspink_denied_group = Group.objects.get(name=ANDERSPINK_DENIED_GROUP)
            anderspink_access = update.pop("anderspink_access")
            if anderspink_access:
                user.groups.remove(anderspink_denied_group)
            else:
                user.groups.add(anderspink_denied_group)

        if "learnlight_access" in update:
            learnlight_denied_group = Group.objects.get(name=LEARNLIGHT_DENIED_GROUP)
            learnlight_access = update.pop("learnlight_access")
            if learnlight_access:
                user.groups.remove(learnlight_denied_group)
            else:
                user.groups.add(learnlight_denied_group)

        if "linkedin_access" in update:
            linkedin_denied_group = Group.objects.get(name=LINKEDIN_DENIED_GROUP)
            linkedin_access = update.pop("linkedin_access")
            if linkedin_access:
                user.groups.remove(linkedin_denied_group)
            else:
                user.groups.add(linkedin_denied_group)

        if "udemy_access" in update:
            udemy_denied_group = Group.objects.get(name=UDEMY_DENIED_GROUP)
            udemy_access = update.pop("udemy_access")
            if udemy_access:
                user.groups.remove(udemy_denied_group)
            else:
                user.groups.add(udemy_denied_group)

        if "founderz_access" in update:
            founderz_denied_group = Group.objects.get(name=FOUNDERZ_DENIED_GROUP)
            if update.pop("founderz_access", None):
                user.groups.remove(founderz_denied_group)
            else:
                user.groups.add(founderz_denied_group)

        if "siemens_access" in update:
            siemens_denied_group = Group.objects.get(name=SIEMENS_DENIED_GROUP)
            if update.pop("siemens_access", None):
                user.groups.remove(siemens_denied_group)
            else:
                user.groups.add(siemens_denied_group)

        if "triboo_centrical_access" in update:
            centrical_denied_group = Group.objects.get(name=CENTRICAL_DENIED_GROUP)
            if update.pop("triboo_centrical_access", None):
                user.groups.remove(centrical_denied_group)
            else:
                user.groups.add(centrical_denied_group)

        if "analytics_access" in update:
            full_access_group = Group.objects.get(name=ANALYTICS_ACCESS_GROUP)  # Analytics
            limited_access_group = Group.objects.get(name=ANALYTICS_LIMITED_ACCESS_GROUP)  # Analytics
            analytics_access = update.pop("analytics_access")
            if analytics_access == "0":
                user.groups.remove(full_access_group)
                user.groups.remove(limited_access_group)
            elif analytics_access == "1":
                user.groups.remove(full_access_group)
                user.groups.add(limited_access_group)
            else:
                user.groups.add(full_access_group)
                user.groups.remove(limited_access_group)

        # If we have encountered any validation errors, return them to the user.
        if field_errors:
            error_list = [v['user_message'] for _, v in field_errors.items()]
            return JsonResponse({'error': error_list}, status=409)

        user_properties = {key: update[key] for key in user_fields if key in update}
        profile_properties = {key: update[key] for key in FULL_USER_PROFILE_FIELDS if key in update}
        if 'lt_hire_date' in profile_properties:
            profile_properties['lt_hire_date'] = datetime.strptime(
                profile_properties['lt_hire_date'], student_views.get_date_format()[0]
            )
        
        if 'language' in update:
            UserPreference.objects.update_or_create(user=user,
                                                    key=LANGUAGE_KEY,
                                                    defaults={'value': update['language']})

        User.objects.filter(id=user_id).update(**user_properties)
        UserProfile.objects.filter(user=user).update(**profile_properties)

    context = get_user_account_info(User.objects.select_related('profile').get(id=user_id))
    return JsonResponse(context)


@require_POST
@require_global_staff
def search_users(request):
    post_data = json.loads(request.body)
    query = post_data["query"]
    users = User.objects.filter(
        Q(username__icontains=query) | Q(email__icontains=query)).select_related('profile')

    orgs = '+'.join(configuration_helpers.get_current_site_orgs())
    if request.user.profile.org in (LT_DEVELOPER, LT_TESTER):
        users = users & users.filter(Q(profile__org=orgs) | Q(profile__org=None) | Q(profile__org=LT_TESTER))
    else:
        users = users & users.filter(Q(profile__org=orgs) | Q(profile__org=None))

    show_more = False
    if users.count() > 20:
        users = users[:20]
        show_more = True
    search_result = []
    for user in users:
        info = get_user_account_info(user)
        search_result.append(info)
    return JsonResponse({"search_result": search_result, "show_more": show_more})


def get_user_related_objects(user):
    collector = NestedObjects(using='default')
    collector.collect([user])
    to_delete = collector.nested()
    related_objects = OrderedDict({'User': 1})
    for i in to_delete[1]:
        if type(i) == list:
            for j in i:
                if type(j) == list:
                    for x in j:
                        name = x._meta.verbose_name
                        if name in related_objects:
                            related_objects[name] += 1
                        else:
                            related_objects[name] = 1
                else:
                    name = j._meta.verbose_name
                    if name in related_objects:
                        related_objects[name] += 1
                    else:
                        related_objects[name] = 1
        else:
            name = i._meta.verbose_name
            if name in related_objects:
                related_objects[name] += 1
            else:
                related_objects[name] = 1
    return related_objects


@require_global_staff
def delete_user(request, user_id):
    user = User.objects.get(id=user_id)
    if request.method == 'GET':
        related_objects = get_user_related_objects(user)
        return JsonResponse(related_objects)
    if request.method == 'POST':
        if user.is_superuser and not request.user.is_superuser:
            return JsonResponse(status=403)
        try:
            user.delete()
            return JsonResponse({"deleted": True})
        except Exception:
            return JsonResponse(status=500)


@require_POST
@require_global_staff
def update_course_enrollment(request, course_id, user_id):
    course_key = CourseKey.from_string(course_id)
    user = User.objects.get(id=user_id)
    action = json.loads(request.body)["action"]

    if action == "enroll":
        enrollment = CourseEnrollment.enroll(user, course_key)
        result = {"created": strftime_localized(enrollment.created, "NUMBERIC_SHORT_DATE_SLASH"),
                  "completed": strftime_localized(enrollment.completed, "NUMBERIC_SHORT_DATE_SLASH")
                  if enrollment.completed else "-",
                  "course_id": course_id}
        return JsonResponse({"info": result})

    else:
        if ProgramsApiConfig.is_student_dashboard_enabled():
            _filter = {
                'courses.course_runs.key': str(course_id)
            }
            _programs_uuids = [
                program.to_dict()['uuid']
                for program in PartialProgram.query(
                    _filter
                )
            ]
            user_enrolled_programs_count = ProgramEnrollment.objects.filter(
                program_uuid__in=_programs_uuids,
                user_id=user_id,
                status=ProgramEnrollmentStatuses.ENROLLED
            ).count()
            # course cannot be unenrolled if this course is engaged by some programs of this `user_id`.
            if user_enrolled_programs_count > 0:
                return JsonResponse(
                    {'user_enrolled_programs_count': user_enrolled_programs_count}
                )

        CourseEnrollment.unenroll(user, course_key)
        result = {"course_id": course_id}
        return JsonResponse({"info": result})


@require_POST
@require_global_staff
def update_user_status(request):
    user_list = request.POST.get("user_list")
    user_list = json.loads(user_list)
    action = request.POST.get("action")
    if action == "1":
        is_active = True
    else:
        is_active = False

    User.objects.filter(id__in=user_list).update(is_active=is_active)
    return JsonResponse({"success": True})
