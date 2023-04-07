# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime, timedelta
from pytz import utc
from django import forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import pgettext_lazy
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers


AVAILABLE_CHOICES = {
    'name': _('Name'),
    'first_name': _('First Name'),
    'last_name': _('Last Name'),
    'email': _('Email'),
    'username': _('Username'),
    'date_joined': _('Date Joined'),
    'level_of_education': _('Education'),
    'gender': _('Gender'),
    'country': _('Country'),
    'lt_area': _('Commercial Zone'),
    'lt_sub_area': _('Commercial Region'),
    'city': _('City'),
    'year_of_birth': _('Year of Birth'),
    'location': pgettext_lazy('user.profile', 'Location'),
    'lt_address': pgettext_lazy('user.profile', 'Address'),
    'lt_address_2': _('Address 2'),
    'lt_phone_number': _('Phone Number'),
    'lt_gdpr': _('GDPR'),
    'lt_company': _('Company'),
    'lt_employee_id': _('Employee ID'),
    'lt_hire_date': _('Hire Date'),
    'lt_level': _('Level'),
    'lt_job_code': _('Job Code'),
    'lt_job_description': _('Job Description'),
    'lt_department': _('Department'),
    'lt_supervisor': _('Supervisor'),
    'lt_ilt_supervisor': _('ILT Supervisor'),
    'lt_learning_group': _('Learning Group'),
    'lt_exempt_status': _('Exempt Status'),
    'lt_comments': _('Comments'),
}


class UserPropertiesHelper():
    def __init__(self):
        config_properties = configuration_helpers.get_value('ANALYTICS_USER_PROPERTIES',
                                                            settings.FEATURES.get('ANALYTICS_USER_PROPERTIES', {}))

        self.possible_choices_db_prefix = []
        self.possible_choices = []
        self.initial_choices = ["user_name"]
        self.possible_choices2 = []
        for prop in AVAILABLE_CHOICES.keys():
            if prop in config_properties.keys():
                prefix = "user_"
                db_prefix = "user__"
                if prop not in ['email', 'username', 'date_joined']:
                    db_prefix += "profile__"

                self.possible_choices.append(("%s%s" % (prefix, prop), AVAILABLE_CHOICES[prop]))
                self.possible_choices2.append(("%s%s" % (prefix, prop), AVAILABLE_CHOICES[prop], config_properties[prop]))
                self.possible_choices_db_prefix.append(("%s%s" % (db_prefix, prop), AVAILABLE_CHOICES[prop]))

                if config_properties[prop] == "default":
                    self.initial_choices.append("%s%s" % (prefix, prop))

        self.possible_choices.sort(key=lambda choice: choice[1])
        self.possible_choices2.sort(key=lambda choice: choice[1])
        self.possible_choices_db_prefix.sort(key=lambda choice: choice[1])

    def get_possible_choices(self, db_prefix=True):
        if db_prefix:
            return self.possible_choices_db_prefix
        return self.possible_choices

    def get_possible_choices2(self, db_prefix=True):
        return self.possible_choices2

    def get_name_value_mapping(self):
        d = dict()
        for c in self.possible_choices:
            d[c[1]] = c[0]
        return d

    def get_initial_choices(self):
        return self.initial_choices


class TableFilterForm(forms.Form):
    queried_field = forms.ChoiceField(required=False, label=_('Field'))
    query_string = forms.CharField(required=False, initial='', label=_('Query'))

    course_id = forms.CharField(widget=forms.HiddenInput(), required=False)
    report = forms.CharField(widget=forms.HiddenInput(), required=False)
    selected_properties = forms.CharField(widget=forms.MultipleHiddenInput(), required=False)
    from_day = forms.CharField(widget=forms.HiddenInput(), required=False)
    to_day = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, data=None, choices=[]):
        super(TableFilterForm, self).__init__(data)
        self.fields['queried_field'].choices = [('user__profile__name', _('Name'))] + choices


class UserPropertiesForm(forms.Form):
    selected_properties = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_('Select the user properties to display')
    )

    course_id = forms.CharField(widget=forms.HiddenInput(), required=False)
    report = forms.CharField(widget=forms.HiddenInput(), required=False)
    page = forms.CharField(widget=forms.HiddenInput(), required=False)
    query_string = forms.CharField(widget=forms.HiddenInput(), required=False)
    queried_field = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, data=None, choices=[], initial={}):
        super(UserPropertiesForm, self).__init__(data, initial={'selected_properties': initial})
        self.fields['selected_properties'].choices = choices
        self.fields['selected_properties'].initial = initial


    def clean(self):
        cleaned_data = super(UserPropertiesForm, self).clean()
        all_properties = ["user_%s" % prop for prop in AVAILABLE_CHOICES.keys()]
        if len(cleaned_data['selected_properties']) > 0:
            cleaned_data['excluded_properties'] = set(all_properties) - set(cleaned_data['selected_properties'])
        else:
            cleaned_data['excluded_properties'] = set(all_properties) - set(self.initial['selected_properties'])
        return cleaned_data
