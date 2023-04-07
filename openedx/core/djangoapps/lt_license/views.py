import re
import logging

from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from smtplib import SMTPException

from openedx.core.lib.api.authentication import OAuth2AuthenticationAllowInactiveUser
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from util.email_utils import send_mail_with_alias as send_mail


log = logging.getLogger("job.lt-license")


def check_email_string(email):
    if re.match(r'[^@]*@[^@]+\.[^@]+', email):
        return email
    else:
        return False


def get_count_license():
    license_exclude_email_domain_list = ['@example.com']
    license_exclude_email_address_list = []

    if configuration_helpers.get_value('license_exclude_email', None):
        license_exclude_email_list = configuration_helpers.get_value('license_exclude_email')
        for i in license_exclude_email_list:
            if check_email_string(i):
                if i[0] == '@':
                    license_exclude_email_domain_list.append(i)
                else:
                    license_exclude_email_address_list.append(i)

    license_all = User.objects.all().filter(is_active=True)
    if license_exclude_email_domain_list:
        for email_domain in license_exclude_email_domain_list:
            license_all = license_all.exclude(email__iendswith=email_domain)
    if license_exclude_email_address_list:
        for email_address in license_exclude_email_address_list:
            license_all = license_all.exclude(email__iexact=email_address)

    license_number = int(license_all.count())
    return license_number


def get_check_license():
    license_number = get_count_license()
    max_license_number = 0
    if configuration_helpers.get_value('max_allowed_licenses', None):
        max_license_number = int(configuration_helpers.get_value('max_allowed_licenses'))
        if license_number > max_license_number:
            return False, license_number, max_license_number
        else:
            return True, license_number, max_license_number
    else:
        return True, license_number, max_license_number


@api_view(['GET', ])
@authentication_classes((OAuth2AuthenticationAllowInactiveUser, ))
@permission_classes((permissions.IsAdminUser, ))
def request_count_license(request):
    license_number = get_count_license()
    return Response(license_number, status=status.HTTP_200_OK)


@api_view(['GET', ])
@authentication_classes((OAuth2AuthenticationAllowInactiveUser, ))
@permission_classes((permissions.IsAdminUser, ))
def request_check_license(request):
    get_status, license_number, max_license_number = get_check_license()
    if get_status:
        info_text = 'License number is ' + str(license_number) + '.'
        return Response(info_text, status=status.HTTP_200_OK)
    else:
        warning_text = 'License number is ' + str(license_number) + '. Over ' + str(max_license_number) \
                       + ' max license number.'
        return Response(warning_text, status=status.HTTP_200_OK)
        

@api_view(['GET', ])
@authentication_classes((OAuth2AuthenticationAllowInactiveUser, ))
@permission_classes((permissions.IsAdminUser, ))
def request_send_mail_license(request):
    mail_template = """Hello,
 
This mail to alert you that {} has exceeded its allowed licenses quota defined in the current licensing agreement.  
     
The number of licenses defined in the agreement : {}
The current number of licenses on the platform : {}
     
As you are the designated account manager for this platform, please, contact as soon as possible your client to clear the situation. If it's an exception, please contact directly the Triboo team.
     
Once the new number of licenses agreed with the client, you can address a request for change to support@learning-tribes.com in order to update with the new agreed quota.
     
Note 1: you will receive this notification everyday until the new quota is defined in the system.
Note 2: no automatic actions to restrict the access or new account creation on the platform will be applied. This is only a notification part of the Triboo account management process.
     
Thank you,
Best regards,
     
The Triboo team."""
    get_status, license_number, max_license_number = get_check_license()
    from_mail_address = settings.CONTACT_EMAIL
    recipient_mail_address = configuration_helpers.get_value('sales_manager_mail', None)
    if recipient_mail_address:
        if get_status:
            return Response('No Sent mail. Below max license number.', status=status.HTTP_200_OK)
        else:
            try:
                mail_subject = '[Triboo Notification] ' + configuration_helpers.get_value('platform_name', 'customer') \
                               + ' licences exceed allowed quota'
                mail_message = mail_template.format(
                    configuration_helpers.get_value('platform_name'), max_license_number, license_number
                )
                send_mail(
                    mail_subject,
                    mail_message,
                    from_mail_address,
                    [recipient_mail_address],
                    fail_silently=False
                )
                log.warning("sending e-mail for %s to %s", from_mail_address, recipient_mail_address)
                return Response('Sent mail. Above max license number.', status=status.HTTP_200_OK)
            except SMTPException:
                log.warning("Failure sending e-mail for %s to %s", from_mail_address, recipient_mail_address)
                return Response('Sent mail failed', status=status.HTTP_404_NOT_FOUND)
    else:
        return Response('No Sent mail. No sales manager mail address', status=status.HTTP_404_NOT_FOUND) 

