from django.conf import settings
from django.core.mail import send_mail

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers


def send_mail_with_alias(*args, **kwargs):
    """
    change the alias name of the from_email
    eg. Support <triboo@example.com>
    """
    args_list = list(args)
    # if email service is disabled, do nothing
    email_service_enabled = configuration_helpers.get_value('ENABLE_EMAIL_SERVICE', True)
    if not email_service_enabled:
        return
    try:
        from_alias = configuration_helpers.get_value('email_from_alias', settings.DEFAULT_FROM_EMAIL_ALIAS)
        args_list[2] = "{0} <{1}>".format(from_alias, args_list[2])
        no_email_address = getattr(settings, 'LEARNER_NO_EMAIL')
        if no_email_address:
            args_list[3] = [x for x in args_list[3] if not x.endswith(no_email_address)]
            if len(args_list[3]) == 0:
                return
    except AttributeError:
        pass
    return send_mail(*args_list, **kwargs)
