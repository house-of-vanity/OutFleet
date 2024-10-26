from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.http import HttpResponse

def print_headers(request):
    headers = {key: value for key, value in request.META.items() if key.startswith('HTTP_')}
    
    for key, value in headers.items():
        print(f'{key}: {value}')
    
    return HttpResponse(f"Headers: {headers}")

def shadowsocks(request, link):
    from .models import ACL
    acl = get_object_or_404(ACL, link=link)
    try:
        server_user = acl.server.get_user(acl.user, raw=True)
    except Exception as e:
        return JsonResponse({"error": f"Couldn't get credentials from server. {e}"})

    config = {
        "info": "Managed by OutFleet_v2 [github.com/house-of-vanity/OutFleet/]",
        "password": server_user.password,
        "method": server_user.method,
        "prefix": "\u0005\u00dc_\u00e0\u0001",
        "server": acl.server.client_hostname,
        "server_port": server_user.port,
        "access_url": server_user.access_url,
    }
    return JsonResponse(config)


