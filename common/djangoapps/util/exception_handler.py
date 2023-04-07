import logging

from traceback import format_exc as _format_exc

from rest_framework.response import Response as _Response
from rest_framework.status import HTTP_500_INTERNAL_SERVER_ERROR
from rest_framework.views import exception_handler as _drf_exception_handler

from django.conf import settings as _settings

log = logging.getLogger(__name__)


def learning_tribes_exception_handler(exc, context):
    response = _drf_exception_handler(exc, context)
    if response:
        return response

    desc = 'view[{}] , method [{}] , error: {}'.format(
        context['view'], context['request'].method, exc
    ) \
        if not _settings.DEBUG else _format_exc()

    log.error(desc)

    return _Response(
        {'api_error_message': desc},
        status=HTTP_500_INTERNAL_SERVER_ERROR
    )
