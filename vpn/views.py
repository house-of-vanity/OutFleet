import yaml
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
        "transport": {
            "$type": "tcpudp",
            "tcp": {
                "$type": "shadowsocks",
                "endpoint": f"{acl.server.client_hostname}:{server_user.port}",
                "cipher": f"{server_user.method}",
                "secret": f"{server_user.password}",
                "prefix": "\u0005\u00dc_\u00e0\u0001"
            },
            "udp": {
                "$type": "shadowsocks",
                "endpoint": f"{acl.server.client_hostname}:{server_user.port}",
                "cipher": f"{server_user.method}",
                "secret": f"{server_user.password}",
                "prefix": "\u0005\u00dc_\u00e0\u0001"
            }
        }
    }

    AccessLog.objects.create(user=acl.user, server=acl.server.name, action="Success", data=json.dumps(config, indent=2))

    yaml_data = yaml.dump(config, allow_unicode=True)
    return HttpResponse(yaml_data, content_type="application/x-yaml")
