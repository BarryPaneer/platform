from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework import status, permissions
from openedx.core.lib.api.authentication import OAuth2AuthenticationAllowInactiveUser
from slack_lt.views import InitialSlack


import logging

log = logging.getLogger(__name__)


@api_view(['POST'])
@authentication_classes((OAuth2AuthenticationAllowInactiveUser, ))
@permission_classes((permissions.IsAdminUser, ))
def request_slack_send_message(request):
    request_slack = InitialSlack()
    channel_id = request.data['channel_id'] if 'channel_id' in request.data else None
    title = request.data['title'] if 'title' in request.data else None
    sc_result = request_slack.slack_send_message(request.data['content'], channel_id, title)
    if sc_result:
        return Response('Sent Message', status=status.HTTP_200_OK)
    return Response('Failed to send message', status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@authentication_classes((OAuth2AuthenticationAllowInactiveUser, ))
@permission_classes((permissions.IsAdminUser, ))
def request_slack_lookup_email(request):
    request_slack = InitialSlack()
    sc_result = request_slack.slack_lookup_email(request.query_params['user_email'])
    if sc_result:
        return Response(sc_result, status=status.HTTP_200_OK)
    return Response("Faile to find user's slack", status=status.HTTP_400_BAD_REQUEST)