from django.urls import resolve
from django.http import Http404, HttpResponseNotFound
from django.contrib.auth.middleware import RemoteUserMiddleware

class RequestLogger:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print(f"Original: {request.build_absolute_uri()}")
        print(f"Path : {request.path}")
        
        response = self.get_response(request)

        return response


class AutoLoginMiddleware(RemoteUserMiddleware):
    header = "HTTP_X_AUTHENTIK_USERNAME"
