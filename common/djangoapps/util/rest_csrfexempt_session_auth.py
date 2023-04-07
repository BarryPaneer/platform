from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Extension class for rest framekwork view class.

        *** Remove Csrf exemption in Session Authentication for RestFramework Api ***


        Usage:

            from common.djangoapps.util.rest_csrfexempt_session_auth import CsrfExemptSessionAuthentication

            class NewDjangoRestViewset(APIView):
                ...
                authentication_classes = (CsrfExemptSessionAuthentication, BasicAuthentication)
                ...


        Note:
            `from django.views.decorators.csrf import csrf_exempt` is not supported by (Django)RestFramework.

            So, Please don't use it on `ViewSet` or `ApiView` anymore.

    """
    def enforce_csrf(self, request):
        return  # To not perform the csrf check previously happening
