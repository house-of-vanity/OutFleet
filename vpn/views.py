import yaml
import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404
from mysite.settings import EXTERNAL_ADDRESS

def userFrontend(request, user_hash):
    from .models import User, ACLLink
    try:
        user = get_object_or_404(User, hash=user_hash)
    except Http404:
        return JsonResponse({"error": "Not allowed"}, status=403)

    acl_links = {}
    for link in ACLLink.objects.filter(acl__user=user).select_related('acl__server'):
        server_name = link.acl.server.name
        if server_name not in acl_links:
            acl_links[server_name] = []
        acl_links[server_name].append({"link": f"{EXTERNAL_ADDRESS}/ss/{link.link}#{link.acl.server.name}", "comment": link.comment})

    return JsonResponse(acl_links)

def shadowsocks(request, link):
    from .models import ACLLink, AccessLog
    try:
        acl_link = get_object_or_404(ACLLink, link=link)
        acl = acl_link.acl
    except Http404:
        AccessLog.objects.create(user=None, server="Unknown", action="Failed",
                                 data=f"ACL not found for link: {link}")
        return JsonResponse({"error": "Not allowed"}, status=403)

    try:
        server_user = acl.server.get_user(acl.user, raw=True)
    except Exception as e:
        AccessLog.objects.create(user=acl.user, server=acl.server.name, action="Failed",
                                 data=f"{e}")
        return JsonResponse({"error": f"Couldn't get credentials from server. {e}"})

    if request.GET.get('mode') == 'json':
      config = {
          "info": "Managed by OutFleet_2 [github.com/house-of-vanity/OutFleet/]",
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
      response = json.dumps(config, indent=2)
    else:
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
      response = yaml.dump(config, allow_unicode=True)

    AccessLog.objects.create(user=acl.user, server=acl.server.name, action="Success", data=response)

    return HttpResponse(response, content_type=f"{ 'application/json; charset=utf-8' if request.GET.get('mode') == 'json' else 'text/html' }")

