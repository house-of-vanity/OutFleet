from django.urls import resolve
from django.http import Http404, HttpResponseNotFound

class RequestLogger:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print(f"Original: {request.build_absolute_uri()}")
        print(f"Path : {request.path}")
        
        response = self.get_response(request)

        return response


from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth.models import Group

class AutoLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            user_email = request.META.get('HTTP_X_AUTHENTIK_EMAIL')
            user_name = request.META.get('HTTP_X_AUTHENTIK_USERNAME')
            user_groups = request.META.get('HTTP_X_AUTHENTIK_GROUPS')
            
            if user_email and user_name:
                User = get_user_model()
                try:
                    user = User.objects.get(email=user_email)
                except User.DoesNotExist:
                    user = User.objects.create_user(
                        username=user_name,
                        email=user_email
                    )
                
                if user_groups:
                    groups_list = user_groups.split(',')
                    for group_name in groups_list:
                        group, created = Group.objects.get_or_create(name=group_name.strip())
                        user.groups.add(group)
                
                login(request, user)
        
        response = self.get_response(request)
        return response
