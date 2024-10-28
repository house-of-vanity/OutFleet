import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404


def shadowsocks(request, link):
    from .models import ACLLink, AccessLog
    try:
        acl_link = get_object_or_404(ACLLink, link=link)
        acl = acl_link.acl
    except Http404:
        AccessLog.objects.create(user=None, server="Unknown", action="Failed", data=f"ACL not found for link: {link}")
        return JsonResponse({"error": "Not allowed"}, status=403)
    
    try:
        server_user = acl.server.get_user(acl.user, raw=True)
    except Exception as e:
        AccessLog.objects.create(user=acl.user, server=acl.server.name, action="Failed", data=f"{e}")
        return JsonResponse({"error": f"Couldn't get credentials from server. {e}"})

    config = {
        "info": "Managed by OutFleet_v2 [github.com/house-of-vanity/OutFleet/]",
        "password": server_user.password,
        "method": server_user.method,
        "prefix": "\u0005\u00dc_\u00e0\u0001",
        "server": acl.server.client_hostname,
        "server_port": server_user.port,
        "access_url": server_user.access_url,
        "outfleet": {
            "acl_link": link,
            "server_name": acl.server.name,
            "server_type": acl.server.server_type,
        }
    }
    
    AccessLog.objects.create(user=acl.user, server=acl.server.name, action="Success", data=json.dumps(config, indent=2))
    
    return JsonResponse(config)