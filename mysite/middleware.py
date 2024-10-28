from django.contrib.auth import authenticate, login
from django.utils.deprecation import MiddlewareMixin

class RequestLogger:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print(f"Original: {request.build_absolute_uri()}")
        print(f"Path : {request.path}")
        
        response = self.get_response(request)

        return response


class AutoLoginMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not request.user.is_authenticated:
            user = authenticate(username='admin', password='admin')
            if user:
                login(request, user)
