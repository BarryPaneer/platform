from django.contrib.auth.models import User
from oauth2_provider.models import Application
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from django.core.exceptions import MultipleObjectsReturned
import json
import urllib
from openedx.core.lib.api.authentication import OAuth2AuthenticationAllowInactiveUser


@api_view(['GET', ])
@authentication_classes((OAuth2AuthenticationAllowInactiveUser, ))
@permission_classes((permissions.IsAdminUser, ))
def request_user_application(request, email):
    try:
        user = User.objects.get(email=email)
        if not user.is_active:
            return Response('Account is disable', status=status.HTTP_403_FORBIDDEN)
    except User.DoesNotExist:
        return Response('No exist user account', status=status.HTTP_404_NOT_FOUND)
    try:
        application = Application.objects.get(user=user)
    except Application.DoesNotExist:
        return Response('No exist user DOT application', status=status.HTTP_404_NOT_FOUND)
    except MultipleObjectsReturned:
        return Response('Exist more than one user DOT application', status=status.HTTP_417_EXPECTATION_FAILED)
    response_data = json.dumps({'DOT Application Name': application.name, 'client_id': application.client_id, 'client_secret': application.client_secret})
    return Response(response_data, status=status.HTTP_200_OK)

@api_view(['POST', 'DELETE' ])
@authentication_classes((OAuth2AuthenticationAllowInactiveUser, ))
@permission_classes((permissions.IsAdminUser, ))
def request_user_application_action(request):
    if request.method == 'POST':
        create_application = False
        try:
            user = User.objects.get(email=request.POST['email'])
        except User.DoesNotExist:
            return Response('No exist user account', status=status.HTTP_404_NOT_FOUND)
        try:
            application = Application.objects.get(user=user)
        except Application.DoesNotExist:
            create_application = True
        except MultipleObjectsReturned:
            return Response('Already exist user DOT application', status=status.HTTP_417_EXPECTATION_FAILED)
        if not create_application:
            return Response('Already exist user DOT application', status=status.HTTP_417_EXPECTATION_FAILED)

        application_name = 'DOT-' + user.email
        application = Application.objects.create(
            name = application_name,
            user = user,
            client_type = Application.CLIENT_PUBLIC,
            authorization_grant_type = Application.GRANT_CLIENT_CREDENTIALS
            )
        application.save()
        client_id = application.client_id
        client_secret = application.client_secret
        response_data = json.dumps({"client_id": client_id, "client_secret": client_secret}) 
        return Response(response_data, status=status.HTTP_201_CREATED)
    elif request.method == 'DELETE':
        body_str = request.body
        email = urllib.unquote(body_str).split('=')[1]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response('No exist user account', status=status.HTTP_404_NOT_FOUND)
        try:
            application = Application.objects.filter(user=user)
        except Application.DoesNotExist:
            return Response('No exist user DOT application', status=status.HTTP_404_NOT_FOUND)    
        application.delete()
        return Response('Done to delete user DOT application', status=status.HTTP_200_OK)





