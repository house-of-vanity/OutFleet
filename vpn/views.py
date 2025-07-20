def userPortal(request, user_hash):
    """HTML portal for user to view their VPN access links and server information"""
    from .models import User, ACLLink, AccessLog
    import logging
    from django.db.models import Count, Q
    
    logger = logging.getLogger(__name__)
    
    try:
        user = get_object_or_404(User, hash=user_hash)
        logger.info(f"User portal accessed for user {user.username}")
    except Http404:
        logger.warning(f"User portal access attempt with invalid hash: {user_hash}")
        return render(request, 'vpn/user_portal_error.html', {
            'error_title': 'Access Denied',
            'error_message': 'Invalid access link. Please contact your administrator.'
        }, status=403)
    
    try:
        # Get all ACL links for the user with server information
        acl_links = ACLLink.objects.filter(acl__user=user).select_related('acl__server', 'acl')
        
        # Get connection statistics for all user's links
        # Count successful connections for each specific link
        connection_stats = {}
        recent_connection_stats = {}
        usage_frequency = {}
        total_connections = 0
        
        # Get date ranges for analysis
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        recent_date = now - timedelta(days=30)
        
        for acl_link in acl_links:
            # Since we can't reliably track individual link usage from AccessLog.data,
            # we'll count all successful connections to the server for this user
            # and distribute them among all links for this server
            
            # Get all successful connections for this user on this server
            server_connections = AccessLog.objects.filter(
                user=user.username,
                server=acl_link.acl.server.name,
                action='Success'
            ).count()
            
            # Get recent connections (last 30 days)
            server_recent_connections = AccessLog.objects.filter(
                user=user.username,
                server=acl_link.acl.server.name,
                action='Success',
                timestamp__gte=recent_date
            ).count()
            
            # Get number of links for this server for this user
            user_links_on_server = ACLLink.objects.filter(
                acl__user=user,
                acl__server=acl_link.acl.server
            ).count()
            
            # Distribute connections evenly among links
            link_connections = server_connections // user_links_on_server if user_links_on_server > 0 else 0
            recent_connections = server_recent_connections // user_links_on_server if user_links_on_server > 0 else 0
            
            # Calculate daily usage for the last 30 days
            daily_usage = []
            for i in range(30):
                day_start = now - timedelta(days=i+1)
                day_end = now - timedelta(days=i)
                
                day_connections = AccessLog.objects.filter(
                    user=user.username,
                    server=acl_link.acl.server.name,
                    action='Success',
                    timestamp__gte=day_start,
                    timestamp__lt=day_end
                ).count()
                
                # Distribute daily connections among links
                day_link_connections = day_connections // user_links_on_server if user_links_on_server > 0 else 0
                daily_usage.append(day_link_connections)
            
            # Reverse to show oldest to newest
            daily_usage.reverse()
            
            connection_stats[acl_link.link] = link_connections
            recent_connection_stats[acl_link.link] = recent_connections
            usage_frequency[acl_link.link] = daily_usage
            total_connections += link_connections
        
        # Group links by server
        servers_data = {}
        total_links = 0
        
        for link in acl_links:
            server = link.acl.server
            server_name = server.name
            
            if server_name not in servers_data:
                # Get server status and info
                try:
                    server_status = server.get_server_status()
                    server_accessible = True
                    server_error = None
                except Exception as e:
                    logger.warning(f"Could not get status for server {server_name}: {e}")
                    server_status = {}
                    server_accessible = False
                    server_error = str(e)
                
                servers_data[server_name] = {
                    'server': server,
                    'status': server_status,
                    'accessible': server_accessible,
                    'error': server_error,
                    'links': [],
                    'server_type': server.server_type,
                    'total_connections': 0,
                }
            
            # Add link information with connection stats
            link_url = f"{EXTERNAL_ADDRESS}/ss/{link.link}#{server_name}"
            connection_count = connection_stats.get(link.link, 0)
            recent_count = recent_connection_stats.get(link.link, 0)
            daily_usage = usage_frequency.get(link.link, [0] * 30)
            
            servers_data[server_name]['links'].append({
                'link': link,
                'url': link_url,
                'comment': link.comment or 'Default',
                'connections': connection_count,
                'recent_connections': recent_count,
                'daily_usage': daily_usage,
                'max_daily': max(daily_usage) if daily_usage else 0,
            })
            servers_data[server_name]['total_connections'] += connection_count
            total_links += 1
        
        # Calculate total recent connections from all links
        total_recent_connections = sum(recent_connection_stats.values())
        
        context = {
            'user': user,
            'servers_data': servers_data,
            'total_servers': len(servers_data),
            'total_links': total_links,
            'total_connections': total_connections,
            'recent_connections': total_recent_connections,
            'external_address': EXTERNAL_ADDRESS,
        }
        
        return render(request, 'vpn/user_portal.html', context)
        
    except Exception as e:
        logger.error(f"Error loading user portal for {user.username}: {e}")
        return render(request, 'vpn/user_portal_error.html', {
            'error_title': 'Server Error',
            'error_message': 'Unable to load your VPN information. Please try again later or contact support.'
        }, status=500)
import yaml
import json
import logging
from django.shortcuts import get_object_or_404, render
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
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        acl_link = get_object_or_404(ACLLink, link=link)
        acl = acl_link.acl
        logger.info(f"Found ACL link for user {acl.user.username} on server {acl.server.name}")
    except Http404:
        logger.warning(f"ACL link not found: {link}")
        AccessLog.objects.create(user=None, server="Unknown", action="Failed",
                                 data=f"ACL not found for link: {link}")
        return JsonResponse({"error": "Not allowed"}, status=403)

    try:
        server_user = acl.server.get_user(acl.user, raw=True)
        logger.info(f"Successfully retrieved user credentials for {acl.user.username} from {acl.server.name}")
    except Exception as e:
        logger.error(f"Failed to get user credentials for {acl.user.username} from {acl.server.name}: {e}")
        AccessLog.objects.create(user=acl.user, server=acl.server.name, action="Failed",
                                 data=f"Failed to get credentials: {e}")
        return JsonResponse({"error": f"Couldn't get credentials from server. {e}"}, status=500)

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

