def userPortal(request, user_hash):
    """HTML portal for user to view their VPN access links and server information"""
    from .models import User, ACLLink, UserStatistics, AccessLog
    from django.utils import timezone
    from datetime import timedelta
    import logging
    
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
        logger.info(f"Found {acl_links.count()} ACL links for user {user.username}")
        
        # Calculate overall statistics from cached data (only where cache exists)
        user_stats = UserStatistics.objects.filter(user=user)
        if user_stats.exists():
            total_connections = sum(stat.total_connections for stat in user_stats)
            recent_connections = sum(stat.recent_connections for stat in user_stats)
            logger.info(f"User {user.username} cached stats: total_connections={total_connections}, recent_connections={recent_connections}")
        else:
            # No cache available, set to zero and suggest cache update
            total_connections = 0
            recent_connections = 0
            logger.warning(f"No cached statistics found for user {user.username}. Run statistics update task.")
        
        # Group links by server
        servers_data = {}
        total_links = 0
        
        for link in acl_links:
            server = link.acl.server
            server_name = server.name
            logger.debug(f"Processing link {link.link} for server {server_name}")
            
            if server_name not in servers_data:
                # Get server status and info
                try:
                    server_status = server.get_server_status()
                    server_accessible = True
                    server_error = None
                    logger.debug(f"Server {server_name} status retrieved successfully")
                except Exception as e:
                    logger.warning(f"Could not get status for server {server_name}: {e}")
                    server_status = {}
                    server_accessible = False
                    server_error = str(e)
                
                # Calculate server-level totals from cached stats (only where cache exists)
                server_stats = user_stats.filter(server_name=server_name)
                if server_stats.exists():
                    server_total_connections = sum(stat.total_connections for stat in server_stats)
                else:
                    server_total_connections = 0
                
                servers_data[server_name] = {
                    'server': server,
                    'status': server_status,
                    'accessible': server_accessible,
                    'error': server_error,
                    'links': [],
                    'server_type': server.server_type,
                    'total_connections': server_total_connections,
                }
                logger.debug(f"Created server data for {server_name} with {server_total_connections} cached connections")
            
            # Calculate time since last access
            last_access_display = "Never used"
            if link.last_access_time:
                time_diff = timezone.now() - link.last_access_time
                if time_diff.days > 0:
                    last_access_display = f"{time_diff.days} days ago"
                elif time_diff.seconds > 3600:
                    hours = time_diff.seconds // 3600
                    last_access_display = f"{hours} hours ago"
                elif time_diff.seconds > 60:
                    minutes = time_diff.seconds // 60
                    last_access_display = f"{minutes} minutes ago"
                else:
                    last_access_display = "Just now"
            
            # Get cached statistics for this specific link
            try:
                link_stats = UserStatistics.objects.get(
                    user=user,
                    server_name=server_name,
                    acl_link_id=link.link
                )
                logger.debug(f"Found cached stats for link {link.link}: {link_stats.total_connections} connections, max_daily={link_stats.max_daily}")
                
                link_connections = link_stats.total_connections
                link_recent_connections = link_stats.recent_connections
                daily_usage = link_stats.daily_usage or []
                max_daily = link_stats.max_daily
                
            except UserStatistics.DoesNotExist:
                logger.warning(f"No cached stats found for link {link.link} on server {server_name}, using fallback")
                
                # Fallback: Since AccessLog doesn't track specific links, show zero for link-specific stats
                # but keep server-level stats for context
                link_connections = 0
                link_recent_connections = 0
                daily_usage = [0] * 30  # Empty 30-day chart
                max_daily = 0
                
                logger.warning(f"Using zero stats for uncached link {link.link} - AccessLog doesn't track individual links")
            
            logger.debug(f"Link {link.link} stats: connections={link_connections}, recent={link_recent_connections}, max_daily={max_daily}")
            
            # Add link information with statistics
            link_url = f"{EXTERNAL_ADDRESS}/ss/{link.link}#{server_name}"
            
            link_data = {
                'link': link,
                'url': link_url,
                'comment': link.comment or 'Default',
                'last_access': link.last_access_time,
                'last_access_display': last_access_display,
                'connections': link_connections,
                'recent_connections': link_recent_connections,
                'daily_usage': daily_usage,
                'max_daily': max_daily,
            }
            
            servers_data[server_name]['links'].append(link_data)
            total_links += 1
            
            logger.debug(f"Added comprehensive link data for {link.link}")
        
        logger.info(f"Prepared data for {len(servers_data)} servers and {total_links} total links")
        logger.info(f"Portal statistics: total_connections={total_connections}, recent_connections={recent_connections}")
        
        # Check if user has access to any Xray servers
        from vpn.server_plugins import XrayCoreServer, XrayInboundServer
        has_xray_servers = any(
            isinstance(acl_link.acl.server.get_real_instance(), (XrayCoreServer, XrayInboundServer))
            for acl_link in acl_links
        )
        
        context = {
            'user': user,
            'user_links': acl_links,  # For accessing user's links in template
            'servers_data': servers_data,
            'total_servers': len(servers_data),
            'total_links': total_links,
            'total_connections': total_connections,
            'recent_connections': recent_connections,
            'external_address': EXTERNAL_ADDRESS,
            'has_xray_servers': has_xray_servers,
        }
        
        logger.debug(f"Context prepared with keys: {list(context.keys())}")
        logger.debug(f"Servers in context: {list(servers_data.keys())}")
        
        # Log sample server data for debugging
        for server_name, server_data in servers_data.items():
            logger.debug(f"Server {server_name}: total_connections={server_data['total_connections']}, links_count={len(server_data['links'])}")
            for i, link_data in enumerate(server_data['links']):
                logger.debug(f"  Link {i}: connections={link_data['connections']}, recent={link_data['recent_connections']}, last_access='{link_data['last_access_display']}'")
        
        return render(request, 'vpn/user_portal.html', context)
        
    except Exception as e:
        logger.error(f"Error loading user portal for {user.username}: {e}", exc_info=True)
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
    from django.utils import timezone
    
    logger = logging.getLogger(__name__)
    
    try:
        acl_link = get_object_or_404(ACLLink, link=link)
        acl = acl_link.acl
        logger.info(f"Found ACL link for user {acl.user.username} on server {acl.server.name}")
    except Http404:
        logger.warning(f"ACL link not found: {link}")
        AccessLog.objects.create(
            user=None, 
            server="Unknown", 
            acl_link_id=link,
            action="Failed",
            data=f"ACL not found for link: {link}"
        )
        return JsonResponse({"error": "Not allowed"}, status=403)

    try:
        server_user = acl.server.get_user(acl.user, raw=True)
        logger.info(f"Successfully retrieved user credentials for {acl.user.username} from {acl.server.name}")
    except Exception as e:
        logger.error(f"Failed to get user credentials for {acl.user.username} from {acl.server.name}: {e}")
        AccessLog.objects.create(
            user=acl.user.username, 
            server=acl.server.name, 
            acl_link_id=acl_link.link,
            action="Failed",
            data=f"Failed to get credentials: {e}"
        )
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

    # Update last access time for this specific link
    acl_link.last_access_time = timezone.now()
    acl_link.save(update_fields=['last_access_time'])
    
    # Create AccessLog with specific link tracking
    AccessLog.objects.create(
        user=acl.user.username, 
        server=acl.server.name, 
        acl_link_id=acl_link.link,
        action="Success", 
        data=response
    )

    return HttpResponse(response, content_type=f"{ 'application/json; charset=utf-8' if request.GET.get('mode') == 'json' else 'text/html' }")


def xray_subscription(request, link):
    """
    Return Xray subscription with all available protocols for the user.
    This generates a single subscription link that includes all inbounds the user has access to.
    """
    from .models import ACLLink, AccessLog
    from vpn.server_plugins import XrayCoreServer, XrayInboundServer
    import logging
    from django.utils import timezone
    import base64
    
    logger = logging.getLogger(__name__)
    
    try:
        acl_link = get_object_or_404(ACLLink, link=link)
        acl = acl_link.acl
        logger.info(f"Found ACL link for user {acl.user.username} on server {acl.server.name}")
    except Http404:
        logger.warning(f"ACL link not found: {link}")
        AccessLog.objects.create(
            user=None, 
            server="Unknown", 
            acl_link_id=link,
            action="Failed",
            data=f"ACL not found for link: {link}"
        )
        return HttpResponse("Not found", status=404)

    try:
        # Get all servers this user has access to
        user_acls = acl.user.acl_set.all()
        subscription_configs = []
        
        for user_acl in user_acls:
            server = user_acl.server.get_real_instance()
            
            # Handle XrayInboundServer (individual inbounds)
            if isinstance(server, XrayInboundServer):
                if server.xray_inbound:
                    config = server.get_user(acl.user, raw=True)
                    if config and 'connection_string' in config:
                        subscription_configs.append(config['connection_string'])
                        logger.info(f"Added XrayInboundServer config for {server.name}")
            
            # Handle XrayCoreServer (parent server with multiple inbounds)
            elif isinstance(server, XrayCoreServer):
                try:
                    # Get all inbounds for this server that have this user
                    for inbound in server.inbounds.filter(enabled=True):
                        # Check if user has a client in this inbound
                        client = inbound.clients.filter(user=acl.user).first()
                        if client:
                            connection_string = server._generate_connection_string(client)
                            if connection_string:
                                subscription_configs.append(connection_string)
                                logger.info(f"Added inbound {inbound.tag} config for user {acl.user.username}")
                except Exception as e:
                    logger.warning(f"Failed to get configs from XrayCoreServer {server.name}: {e}")
        
        if not subscription_configs:
            logger.warning(f"No Xray configurations found for user {acl.user.username}")
            AccessLog.objects.create(
                user=acl.user.username, 
                server="Multiple", 
                acl_link_id=acl_link.link,
                action="Failed",
                data="No Xray configurations available"
            )
            return HttpResponse("No configurations available", status=404)
        
        # Join all configs with newlines and encode in base64 for subscription format
        subscription_content = '\n'.join(subscription_configs)
        logger.info(f"Raw subscription content for {acl.user.username}:\n{subscription_content}")
        
        subscription_b64 = base64.b64encode(subscription_content.encode('utf-8')).decode('utf-8')
        logger.info(f"Base64 subscription length: {len(subscription_b64)}")
        
        # Update last access time
        acl_link.last_access_time = timezone.now()
        acl_link.save(update_fields=['last_access_time'])
        
        # Create access log
        AccessLog.objects.create(
            user=acl.user.username, 
            server="Xray-Subscription", 
            acl_link_id=acl_link.link,
            action="Success", 
            data=f"Generated subscription with {len(subscription_configs)} configs. Content: {subscription_content[:200]}..."
        )
        
        logger.info(f"Generated Xray subscription for {acl.user.username} with {len(subscription_configs)} configs")
        
        # Return with proper headers for subscription
        response = HttpResponse(subscription_b64, content_type="text/plain; charset=utf-8")
        response['Content-Disposition'] = 'attachment; filename="xray_subscription.txt"'
        response['Cache-Control'] = 'no-cache'
        return response
        
    except Exception as e:
        logger.error(f"Failed to generate Xray subscription for {acl.user.username}: {e}")
        AccessLog.objects.create(
            user=acl.user.username, 
            server="Xray-Subscription", 
            acl_link_id=acl_link.link,
            action="Failed",
            data=f"Failed to generate subscription: {e}"
        )
        return HttpResponse(f"Error generating subscription: {e}", status=500)

