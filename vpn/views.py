def userPortal(request, user_hash):
    """HTML portal for user to view their VPN access links and subscription groups"""
    from .models import User
    from .models_xray import UserSubscription, SubscriptionGroup, Inbound
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
        # Get all active subscription groups for the user
        user_subscriptions = UserSubscription.objects.filter(
            user=user, 
            active=True,
            subscription_group__is_active=True
        ).select_related('subscription_group').prefetch_related('subscription_group__inbounds')
        
        logger.info(f"Found {user_subscriptions.count()} active subscription groups for user {user.username}")
        
        # Calculate overall Xray subscription statistics
        from .models import AccessLog
        total_connections = AccessLog.objects.filter(
            user=user.username,
            action='Success',
            server='Xray-Subscription'
        ).count()
        
        recent_connections = AccessLog.objects.filter(
            user=user.username,
            action='Success',
            server='Xray-Subscription',
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        logger.info(f"Xray statistics for user {user.username}: total={total_connections}, recent={recent_connections}")
        
        # Determine protocol scheme
        scheme = 'https' if request.is_secure() else 'http'
        
        # Group inbounds by subscription group
        groups_data = {}
        total_inbounds = 0
        
        for subscription in user_subscriptions:
            group = subscription.subscription_group
            group_name = group.name
            logger.debug(f"Processing subscription group {group_name}")
            
            # Get all deployed inbounds for this group (count actual server deployments)
            from .models_xray import ServerInbound
            deployed_inbounds = ServerInbound.objects.filter(
                inbound__in=group.inbounds.all(),
                active=True
            ).select_related('inbound', 'server')
            
            # Calculate connections for this specific group
            group_connections = AccessLog.objects.filter(
                user=user.username,
                action='Success',
                server='Xray-Subscription',
                data__icontains=f'"group": "{group_name}"'
            ).count()
            
            groups_data[group_name] = {
                'group': group,
                'subscription': subscription,
                'inbounds': [],
                'total_connections': group_connections,
                'deployed_count': deployed_inbounds.count(),  # Actual deployed inbounds count
            }
            
            # Process each deployed inbound (each server-inbound combination)
            for server_inbound in deployed_inbounds:
                inbound = server_inbound.inbound
                logger.debug(f"Processing inbound {inbound.name} in group {group_name}")
                
                # Generate connection URLs based on protocol
                connection_urls = []
                
                if inbound.protocol == 'vless':
                    # Generate VLESS URL - this is a placeholder implementation
                    # In the real implementation, you'd generate proper VLESS URLs with user UUID
                    connection_url = f"vless://user-uuid@{EXTERNAL_ADDRESS}:{inbound.port}#{inbound.name}"
                    connection_urls.append({
                        'url': connection_url,
                        'protocol': 'VLESS',
                        'name': inbound.name
                    })
                elif inbound.protocol == 'vmess':
                    # Generate VMess URL - placeholder
                    connection_url = f"vmess://user-config@{EXTERNAL_ADDRESS}:{inbound.port}#{inbound.name}"
                    connection_urls.append({
                        'url': connection_url,
                        'protocol': 'VMess',
                        'name': inbound.name
                    })
                elif inbound.protocol == 'trojan':
                    # Generate Trojan URL - placeholder
                    connection_url = f"trojan://user-password@{EXTERNAL_ADDRESS}:{inbound.port}#{inbound.name}"
                    connection_urls.append({
                        'url': connection_url,
                        'protocol': 'Trojan',
                        'name': inbound.name
                    })
                elif inbound.protocol == 'shadowsocks':
                    # Generate Shadowsocks URL - placeholder
                    connection_url = f"ss://user-config@{EXTERNAL_ADDRESS}:{inbound.port}#{inbound.name}"
                    connection_urls.append({
                        'url': connection_url,
                        'protocol': 'Shadowsocks',
                        'name': inbound.name
                    })
                
                inbound_data = {
                    'inbound': inbound,
                    'connection_urls': connection_urls,
                    'protocol': inbound.protocol.upper(),
                    'port': inbound.port,
                    'domain': EXTERNAL_ADDRESS,
                    'network': inbound.network,
                    'security': inbound.security,
                    'connections': 0,  # Placeholder during transition
                    'last_access_display': "Never used",  # Placeholder
                    'server': server_inbound.server,  # Server that deployed this inbound
                    'server_name': server_inbound.server.name,  # Server name for display
                }
                
                groups_data[group_name]['inbounds'].append(inbound_data)
                total_inbounds += 1
                
                logger.debug(f"Added inbound data for {inbound.name}")
        
        logger.info(f"Prepared data for {len(groups_data)} subscription groups and {total_inbounds} total inbounds")
        logger.info(f"Portal statistics: total_connections={total_connections}, recent_connections={recent_connections}")
        
        # Check if user has any Xray subscription groups
        has_xray_access = user_subscriptions.exists()
        
        # Also get old-style ACL links for backwards compatibility
        acl_links = []
        try:
            from .models import ACLLink
            acl_links = ACLLink.objects.filter(acl__user=user).select_related('acl__server', 'acl')
        except:
            pass

        context = {
            'user': user,
            'user_subscriptions': user_subscriptions,  # For accessing user's subscriptions in template
            'groups_data': groups_data,
            'total_groups': len(groups_data),
            'total_inbounds': total_inbounds,
            'total_connections': total_connections,
            'recent_connections': recent_connections,
            'external_address': EXTERNAL_ADDRESS,
            'has_xray_access': has_xray_access,
            'force_scheme': scheme,  # Override request.scheme in template
            'acl_links': acl_links,  # For backwards compatibility
            'has_old_links': len(acl_links) > 0,
            'xray_subscription_url': f"{EXTERNAL_ADDRESS}/xray/{user.hash}",
        }
        
        logger.debug(f"Context prepared with keys: {list(context.keys())}")
        logger.debug(f"Groups in context: {list(groups_data.keys())}")
        
        # Log sample group data for debugging
        for group_name, group_data in groups_data.items():
            logger.debug(f"Group {group_name}: total_connections={group_data['total_connections']}, inbounds_count={len(group_data['inbounds'])}")
            for i, inbound_data in enumerate(group_data['inbounds']):
                logger.debug(f"  Inbound {i}: protocol={inbound_data['protocol']}, port={inbound_data['port']}, connections={inbound_data['connections']}")
        
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

    # Handle both dict and object formats for server_user
    if isinstance(server_user, dict):
        password = server_user.get('password', '')
        method = server_user.get('method', 'aes-128-gcm')
        port = server_user.get('port', 8080)
        access_url = server_user.get('access_url', '')
    else:
        password = getattr(server_user, 'password', '')
        method = getattr(server_user, 'method', 'aes-128-gcm')
        port = getattr(server_user, 'port', 8080)
        access_url = getattr(server_user, 'access_url', '')

    if request.GET.get('mode') == 'json':
      config = {
          "info": "Managed by OutFleet_2 [github.com/house-of-vanity/OutFleet/]",
          "password": password,
          "method": method,
          "prefix": "\u0005\u00dc_\u00e0\u0001",
          "server": acl.server.client_hostname,
          "server_port": port,
          "access_url": access_url,
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
                  "endpoint": f"{acl.server.client_hostname}:{port}",
                  "cipher": f"{method}",
                  "secret": f"{password}",
                  "prefix": "\u0005\u00dc_\u00e0\u0001"
             },
             "udp": {
                  "$type": "shadowsocks",
                  "endpoint": f"{acl.server.client_hostname}:{port}",
                  "cipher": f"{method}",
                  "secret": f"{password}",
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


def xray_subscription(request, user_hash):
    """
    Return Xray subscription with all available protocols for the user.
    This generates configs based on user's subscription groups.
    """
    from .models import User, AccessLog
    from .models_xray import UserSubscription
    import logging
    from django.utils import timezone
    import base64
    import uuid
    import json
    
    logger = logging.getLogger(__name__)
    
    # Clean user_hash from any trailing slashes
    user_hash = user_hash.rstrip('/')
    
    try:
        user = get_object_or_404(User, hash=user_hash)
        logger.info(f"Found user {user.username} for Xray subscription generation")
    except Http404:
        logger.warning(f"User not found for hash: {user_hash}")
        AccessLog.objects.create(
            user=None, 
            server="Unknown", 
            acl_link_id=user_hash,
            action="Failed",
            data=f"User not found for hash: {user_hash}"
        )
        return HttpResponse("Not found", status=404)

    # Check if this is a JSON request for web display
    if request.GET.get('format') == 'json':
        return xray_subscription_json(request, user, user_hash)

    try:
        # Check if specific group is requested
        group_filter = request.GET.get('group')
        
        # Get subscription groups for the user
        user_subscriptions = UserSubscription.objects.filter(
            user=user, 
            active=True,
            subscription_group__is_active=True
        ).select_related('subscription_group').prefetch_related('subscription_group__inbounds')
        
        # Filter by specific group if requested
        if group_filter:
            user_subscriptions = user_subscriptions.filter(subscription_group__name=group_filter)
            logger.info(f"Filtering subscription for group: {group_filter}")
        
        subscription_configs = []
        
        for subscription in user_subscriptions:
            group = subscription.subscription_group
            logger.info(f"Processing subscription group {group.name} for user {user.username}")
            
            # Get all inbounds from this group
            for inbound in group.inbounds.all():
                try:
                    # Find all servers where this inbound is deployed
                    from .models_xray import ServerInbound
                    deployed_servers = ServerInbound.objects.filter(
                        inbound=inbound, 
                        active=True
                    ).select_related('server')
                    
                    # Generate connection string for each server where inbound is deployed
                    for server_inbound in deployed_servers:
                        server = server_inbound.server
                        # Get server's client_hostname for XrayServerV2
                        server_hostname = getattr(server.get_real_instance(), 'client_hostname', None)
                        connection_string = generate_xray_connection_string(user, inbound, server.name, server_hostname)
                        
                        if connection_string:
                            subscription_configs.append(connection_string)
                            logger.info(f"Added {inbound.protocol} config for inbound {inbound.name} on server {server.name}")
                        
                except Exception as e:
                    logger.warning(f"Failed to generate config for inbound {inbound.name}: {e}")
                    continue
        
        if not subscription_configs:
            group_msg = f" for group '{group_filter}'" if group_filter else ""
            logger.warning(f"No Xray configurations found for user {user.username}{group_msg}")
            AccessLog.objects.create(
                user=user.username, 
                server="Xray-Subscription", 
                acl_link_id=user_hash,
                action="Failed",
                data=f"No Xray configurations available{group_msg}"
            )
            return HttpResponse(f"No configurations available{group_msg}", status=404)
        
        # Join all configs with newlines and encode in base64 for subscription format
        subscription_content = '\n'.join(subscription_configs)
        logger.info(f"Raw subscription content for {user.username}: {len(subscription_configs)} configs")
        
        subscription_b64 = base64.b64encode(subscription_content.encode('utf-8')).decode('utf-8')
        logger.info(f"Base64 subscription length: {len(subscription_b64)}")
        
        # Create access log
        group_msg = f" for group '{group_filter}'" if group_filter else ""
        AccessLog.objects.create(
            user=user.username, 
            server="Xray-Subscription", 
            acl_link_id=user_hash,
            action="Success", 
            data=f"Generated subscription with {len(subscription_configs)} configs from {user_subscriptions.count()} groups{group_msg}"
        )
        
        logger.info(f"Generated Xray subscription for {user.username} with {len(subscription_configs)} configs{group_msg}")
        
        # Return with proper headers for subscription
        response = HttpResponse(subscription_b64, content_type="text/plain; charset=utf-8")
        response['Content-Disposition'] = f'attachment; filename="{user.username}_xray_subscription.txt"'
        response['Cache-Control'] = 'no-cache'
        return response
        
    except Exception as e:
        logger.error(f"Failed to generate Xray subscription for {user.username}: {e}")
        AccessLog.objects.create(
            user=user.username, 
            server="Xray-Subscription", 
            acl_link_id=user_hash,
            action="Failed",
            data=f"Failed to generate subscription: {e}"
        )
        return HttpResponse(f"Error generating subscription: {e}", status=500)


def xray_subscription_json(request, user, user_hash):
    """Return Xray subscription in JSON format for web display"""
    from .models_xray import UserSubscription
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get all active subscription groups for the user
        user_subscriptions = UserSubscription.objects.filter(
            user=user, 
            active=True,
            subscription_group__is_active=True
        ).select_related('subscription_group').prefetch_related('subscription_group__inbounds')
        
        groups_data = {}
        
        for subscription in user_subscriptions:
            group = subscription.subscription_group
            group_configs = []
            
            # Get all inbounds from this group
            for inbound in group.inbounds.all():
                try:
                    # Find all servers where this inbound is deployed
                    from .models_xray import ServerInbound
                    deployed_servers = ServerInbound.objects.filter(
                        inbound=inbound, 
                        active=True
                    ).select_related('server')
                    
                    # Generate connection string for each server where inbound is deployed
                    for server_inbound in deployed_servers:
                        server = server_inbound.server
                        # Get server's client_hostname for XrayServerV2
                        server_hostname = getattr(server.get_real_instance(), 'client_hostname', None)
                        connection_string = generate_xray_connection_string(user, inbound, server.name, server_hostname)
                        
                        if connection_string:
                            config_name = f"{server.name} {inbound.name}"
                            group_configs.append({
                            'name': config_name,
                            'protocol': inbound.protocol.upper(),
                            'port': inbound.port,
                            'network': inbound.network,
                            'security': inbound.security,
                            'domain': host,
                            'connection_string': connection_string
                        })
                        
                except Exception as e:
                    logger.warning(f"Failed to generate config for inbound {inbound.name}: {e}")
                    continue
            
            if group_configs:
                groups_data[group.name] = {
                    'group_name': group.name,
                    'description': group.description,
                    'configs': group_configs
                }
        
        return JsonResponse(groups_data)
        
    except Exception as e:
        logger.error(f"Failed to generate Xray JSON for {user.username}: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def generate_xray_connection_string(user, inbound, server_name=None, server_hostname=None):
    """Generate Xray connection string for user and inbound"""
    import uuid
    import base64
    import json
    from urllib.parse import quote
    
    try:
        # Generate user UUID based on user ID and inbound
        user_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{user.username}-{inbound.name}"))
        
        # Get host (use server's client_hostname if available, fallback to EXTERNAL_ADDRESS)
        host = server_hostname if server_hostname else EXTERNAL_ADDRESS
        
        if inbound.protocol == 'vless':
            # VLESS URL format: vless://uuid@host:port?params#name
            params = []
            
            if inbound.network != 'tcp':
                params.append(f"type={inbound.network}")
            
            if inbound.security != 'none':
                params.append(f"security={inbound.security}")
                if inbound.security == 'tls' and host:
                    params.append(f"sni={host}")
            
            if inbound.network == 'ws':
                params.append(f"path=/{inbound.name}")
            elif inbound.network == 'grpc':
                params.append(f"serviceName={inbound.name}")
            
            param_string = '&'.join(params)
            query_part = f"?{param_string}" if param_string else ""
            
            # Generate config name: ServerName InboundName (e.g., "Israel VLESS-Premium")
            config_name = f"{server_name} {inbound.name}" if server_name else inbound.name
            connection_string = f"vless://{user_uuid}@{host}:{inbound.port}{query_part}#{quote(config_name)}"
            
        elif inbound.protocol == 'vmess':
            # VMess JSON format encoded in base64
            # Generate config name: ServerName InboundName (e.g., "Israel VMESS-Premium")
            config_name = f"{server_name} {inbound.name}" if server_name else inbound.name
            vmess_config = {
                "v": "2",
                "ps": config_name,
                "add": host,
                "port": str(inbound.port),
                "id": user_uuid,
                "aid": "0",
                "scy": "auto",
                "net": inbound.network,
                "type": "none",
                "host": host if host else "",
                "path": f"/{inbound.name}" if inbound.network == 'ws' else "",
                "tls": inbound.security if inbound.security != 'none' else ""
            }
            
            vmess_json = json.dumps(vmess_config)
            vmess_b64 = base64.b64encode(vmess_json.encode()).decode()
            connection_string = f"vmess://{vmess_b64}"
            
        elif inbound.protocol == 'trojan':
            # Trojan URL format: trojan://password@host:port?params#name
            # Use user UUID as password
            params = []
            
            if inbound.security != 'none' and host:
                params.append(f"sni={host}")
            
            if inbound.network != 'tcp':
                params.append(f"type={inbound.network}")
                if inbound.network == 'ws':
                    params.append(f"path=/{inbound.name}")
                elif inbound.network == 'grpc':
                    params.append(f"serviceName={inbound.name}")
            
            param_string = '&'.join(params)
            query_part = f"?{param_string}" if param_string else ""
            
            # Generate config name: ServerName InboundName (e.g., "Israel TROJAN-Premium")
            config_name = f"{server_name} {inbound.name}" if server_name else inbound.name
            connection_string = f"trojan://{user_uuid}@{host}:{inbound.port}{query_part}#{quote(config_name)}"
            
        else:
            # Fallback for unknown protocols
            config_name = f"{server_name} {inbound.name}" if server_name else inbound.name
            connection_string = f"{inbound.protocol}://{user_uuid}@{host}:{inbound.port}#{quote(config_name)}"
        
        return connection_string
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to generate connection string for {inbound.name}: {e}")
        return None

