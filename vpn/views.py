from django.shortcuts import render


# views.py

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.utils import timezone


def shadowsocks(request, link):
    from .models import ACL
    acl = get_object_or_404(ACL, link=link)
    server_user = acl.server.get_user(acl.user, raw=True)
    config = {
        "info": "Managed by OutFleet_v2 [github.com/house-of-vanity/OutFleet/]",
        "password": server_user.password,
        "method": server_user.method,
        "prefix": "\u0005\u00dc_\u00e0\u0001",
        "server": acl.server.client_server_name,
        "server_port": server_user.port,
        "access_url": server_user.access_url,
    }
    return JsonResponse(config)


