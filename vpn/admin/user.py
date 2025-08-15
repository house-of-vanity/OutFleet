"""
User admin interface
"""
import shortuuid
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.urls import path, reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.utils.timezone import localtime

from mysite.settings import EXTERNAL_ADDRESS
from vpn.models import User, ACL, ACLLink, Server, AccessLog, UserStatistics
from vpn.forms import UserForm
from .base import BaseVPNAdmin, format_bytes


@admin.register(User)
class UserAdmin(BaseVPNAdmin):
    form = UserForm
    list_display = ('username', 'comment', 'registration_date', 'hash_link', 'server_count')
    search_fields = ('username', 'hash', 'telegram_user_id', 'telegram_username')
    readonly_fields = ('hash_link', 'vpn_access_summary', 'user_statistics_summary', 'telegram_info_display')
    inlines = []  # All VPN access info is now in vpn_access_summary
    
    fieldsets = (
        ('User Information', {
            'fields': ('username', 'first_name', 'last_name', 'email', 'comment')
        }),
        ('Telegram Integration', {
            'fields': ('telegram_username', 'telegram_info_display'),
            'classes': ('collapse',),
            'description': 'Link existing users to Telegram by setting telegram_username (without @)'
        }),
        ('Access Information', {
            'fields': ('hash_link', 'is_active', 'vpn_access_summary')
        }),
        ('Statistics & Server Management', {
            'fields': ('user_statistics_summary',),
            'classes': ('wide',)
        }),
    )

    @admin.display(description='VPN Access Summary')
    def vpn_access_summary(self, obj):
        """Display summary of user's VPN access"""
        if not obj.pk:
            return "Save user first to see VPN access"
        
        # Get legacy VPN access
        acl_count = ACL.objects.filter(user=obj).count()
        legacy_links = ACLLink.objects.filter(acl__user=obj).count()
        
        # Get Xray access
        from vpn.models_xray import UserSubscription
        xray_subs = UserSubscription.objects.filter(user=obj, active=True).select_related('subscription_group')
        xray_groups = [sub.subscription_group.name for sub in xray_subs]
        
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">'
        
        # Legacy VPN section
        html += '<div style="margin-bottom: 15px;">'
        html += '<h4 style="margin: 0 0 10px 0; color: #495057;">📡 Legacy VPN (Outline/Wireguard)</h4>'
        if acl_count > 0:
            html += f'<p style="margin: 5px 0;">✅ Access to <strong>{acl_count}</strong> server(s)</p>'
            html += f'<p style="margin: 5px 0;">🔗 Total links: <strong>{legacy_links}</strong></p>'
        else:
            html += '<p style="margin: 5px 0; color: #6c757d;">No legacy VPN access</p>'
        html += '</div>'
        
        # Xray section
        html += '<div>'
        html += '<h4 style="margin: 0 0 10px 0; color: #495057;">🚀 Xray VPN</h4>'
        if xray_groups:
            html += f'<p style="margin: 5px 0;">✅ Active subscriptions: <strong>{len(xray_groups)}</strong></p>'
            html += '<ul style="margin: 5px 0; padding-left: 20px;">'
            for group in xray_groups:
                html += f'<li>{group}</li>'
            html += '</ul>'
            
            # Try to get traffic statistics for this user
            try:
                from vpn.server_plugins.xray_v2 import XrayServerV2
                traffic_total_up = 0
                traffic_total_down = 0
                servers_checked = set()
                
                # Get all Xray servers
                xray_servers = XrayServerV2.objects.filter(api_enabled=True, stats_enabled=True)
                
                for server in xray_servers:
                    if server.name not in servers_checked:
                        try:
                            from vpn.xray_api_v2.client import XrayClient
                            from vpn.xray_api_v2.stats import StatsManager
                            
                            client = XrayClient(server=server.api_address)
                            stats_manager = StatsManager(client)
                            
                            # Get user stats (use email format: username@servername)
                            user_email = f"{obj.username}@{server.name}"
                            user_stats = stats_manager.get_user_stats(user_email)
                            
                            if user_stats:
                                traffic_total_up += user_stats.get('uplink', 0)
                                traffic_total_down += user_stats.get('downlink', 0)
                            
                            servers_checked.add(server.name)
                        except Exception as e:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.debug(f"Could not get user stats from server {server.name}: {e}")
                
                # Format traffic if we got any
                if traffic_total_up > 0 or traffic_total_down > 0:
                    
                    html += f'<p style="margin: 10px 0 5px 0; color: #007cba;"><strong>📊 Traffic Statistics:</strong></p>'
                    html += f'<p style="margin: 5px 0 5px 20px;">↑ Upload: <strong>{format_bytes(traffic_total_up)}</strong></p>'
                    html += f'<p style="margin: 5px 0 5px 20px;">↓ Download: <strong>{format_bytes(traffic_total_down)}</strong></p>'
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Could not get traffic stats for user {obj.username}: {e}")
        else:
            html += '<p style="margin: 5px 0; color: #6c757d;">No Xray subscriptions</p>'
        html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    
    @admin.display(description='User Portal', ordering='hash')
    def hash_link(self, obj):
        portal_url = f"{EXTERNAL_ADDRESS}/u/{obj.hash}"
        json_url = f"{EXTERNAL_ADDRESS}/stat/{obj.hash}"
        return format_html(
            '<div style="display: flex; gap: 10px; flex-wrap: wrap;">' + 
            '<a href="{}" target="_blank" style="background: #4ade80; color: #000; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: bold;">🌐 Portal</a>' +
            '<a href="{}" target="_blank" style="background: #3b82f6; color: #fff; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: bold;">📄 JSON</a>' +
            '</div>',
            portal_url, json_url
        )
    
    @admin.display(description='User Statistics Summary')
    def user_statistics_summary(self, obj):
        """Display user statistics with integrated server management"""
        try:
            from vpn.models import UserStatistics
            from django.db import models
            
            # Get statistics for this user
            user_stats = UserStatistics.objects.filter(user=obj).aggregate(
                total_connections=models.Sum('total_connections'),
                recent_connections=models.Sum('recent_connections'),
                total_links=models.Count('id'),
                max_daily_peak=models.Max('max_daily')
            )
            
            # Get server breakdown
            server_breakdown = UserStatistics.objects.filter(user=obj).values('server_name').annotate(
                connections=models.Sum('total_connections'),
                links=models.Count('id')
            ).order_by('-connections')
            
            # Get all ACLs and links for this user
            user_acls = ACL.objects.filter(user=obj).select_related('server').prefetch_related('links')
            
            # Get available servers not yet assigned
            all_servers = Server.objects.all()
            assigned_server_ids = [acl.server.id for acl in user_acls]
            unassigned_servers = all_servers.exclude(id__in=assigned_server_ids)
            
            html = '<div class="user-management-section">'
            
            # Overall Statistics
            html += '<div style="background: #e7f3ff; border-left: 4px solid #007cba; padding: 12px; margin-bottom: 16px; border-radius: 4px;">'
            html += f'<div style="display: flex; gap: 20px; margin-bottom: 8px; flex-wrap: wrap;">'
            html += f'<div><strong>Total Uses:</strong> {user_stats["total_connections"] or 0}</div>'
            html += f'<div><strong>Recent (30d):</strong> {user_stats["recent_connections"] or 0}</div>'
            html += f'<div><strong>Total Links:</strong> {user_stats["total_links"] or 0}</div>'
            if user_stats["max_daily_peak"]:
                html += f'<div><strong>Daily Peak:</strong> {user_stats["max_daily_peak"]}</div>'
            html += f'</div>'
            html += '</div>'
            
            # Server Management
            if user_acls:
                html += '<h4 style="color: #007cba; margin: 16px 0 8px 0;">🔗 Server Access & Links</h4>'
                
                for acl in user_acls:
                    server = acl.server
                    links = list(acl.links.all())
                    
                    # Server header (no slow server status checks)
                    # Determine server type icon and label
                    if server.server_type == 'Outline':
                        type_icon = '🔵'
                        type_label = 'Outline'
                    elif server.server_type == 'Wireguard':
                        type_icon = '🟢'
                        type_label = 'Wireguard'
                    elif server.server_type in ['xray_core', 'xray_v2']:
                        type_icon = '🟣'
                        type_label = 'Xray'
                    else:
                        type_icon = '❓'
                        type_label = server.server_type
                    
                    html += f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">'
                    html += f'<h5 style="margin: 0; color: #333; font-size: 14px; font-weight: 600;">{type_icon} {server.name} ({type_label})</h5>'
                    
                    # Server stats
                    server_stat = next((s for s in server_breakdown if s['server_name'] == server.name), None)
                    if server_stat:
                        html += f'<span style="background: #f8f9fa; padding: 4px 8px; border-radius: 4px; font-size: 12px; color: #6c757d;">'
                        html += f'📊 {server_stat["connections"]} uses ({server_stat["links"]} links)'
                        html += f'</span>'
                    html += f'</div>'
                    
                    html += '<div class="server-section">'
                    
                    # Links display
                    if links:
                        for link in links:
                            # Get link stats
                            link_stats = UserStatistics.objects.filter(
                                user=obj, server_name=server.name, acl_link_id=link.link
                            ).first()
                            
                            html += '<div class="link-item">'
                            html += f'<div style="flex: 1;">'
                            html += f'<div style="font-family: monospace; font-size: 13px; color: #007cba; font-weight: 500;">'
                            html += f'{link.link[:16]}...' if len(link.link) > 16 else link.link
                            html += f'</div>'
                            if link.comment:
                                html += f'<div style="font-size: 11px; color: #6c757d;">{link.comment}</div>'
                            html += f'</div>'
                            
                            # Link stats and actions
                            html += f'<div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">'
                            if link_stats:
                                html += f'<span style="background: #d4edda; color: #155724; padding: 2px 6px; border-radius: 3px; font-size: 10px;">'
                                html += f'✨ {link_stats.total_connections}'
                                html += f'</span>'
                            
                            # Test link button
                            html += f'<a href="{EXTERNAL_ADDRESS}/ss/{link.link}#{server.name}" target="_blank" '
                            html += f'class="btn btn-sm btn-primary btn-sm-custom">🔗</a>'
                            
                            # Delete button
                            html += f'<button type="button" class="btn btn-sm btn-danger btn-sm-custom delete-link-btn" '
                            html += f'data-link-id="{link.id}" data-link-name="{link.link[:12]}">🗑️</button>'
                            
                            # Last access
                            if link.last_access_time:
                                local_time = localtime(link.last_access_time)
                                html += f'<span style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-size: 10px; color: #6c757d;">'
                                html += f'{local_time.strftime("%m-%d %H:%M")}'
                                html += f'</span>'
                            else:
                                html += f'<span style="background: #f8d7da; color: #721c24; padding: 2px 6px; border-radius: 3px; font-size: 10px;">'
                                html += f'Never'
                                html += f'</span>'
                            
                            html += f'</div></div>'
                    
                    # Add link button
                    html += f'<div style="text-align: center; margin-top: 12px;">'
                    html += f'<button type="button" class="btn btn-sm btn-success add-link-btn" '
                    html += f'data-server-id="{server.id}" data-server-name="{server.name}">'
                    html += f'➕ Add Link'
                    html += f'</button>'
                    html += f'</div>'
                    
                    html += '</div>'  # End server-section
            
            # Add server access section
            if unassigned_servers:
                html += '<div style="background: #d1ecf1; border-left: 4px solid #bee5eb; padding: 12px; margin-top: 16px; border-radius: 4px;">'
                html += '<h5 style="margin: 0 0 8px 0; color: #0c5460; font-size: 13px;">➕ Available Servers</h5>'
                html += '<div style="display: flex; gap: 8px; flex-wrap: wrap;">'
                for server in unassigned_servers:
                    # Determine server type icon and label
                    if server.server_type == 'Outline':
                        type_icon = '🔵'
                        type_label = 'Outline'
                    elif server.server_type == 'Wireguard':
                        type_icon = '🟢'
                        type_label = 'Wireguard'
                    elif server.server_type in ['xray_core', 'xray_v2']:
                        type_icon = '🟣'
                        type_label = 'Xray'
                    else:
                        type_icon = '❓'
                        type_label = server.server_type
                    
                    html += f'<button type="button" class="btn btn-sm btn-outline-info btn-sm-custom add-server-btn" '
                    html += f'data-server-id="{server.id}" data-server-name="{server.name}" '
                    html += f'title="{type_label} server">'
                    html += f'{type_icon} {server.name} ({type_label})'
                    html += f'</button>'
                html += '</div></div>'
            
            html += '</div>'  # End user-management-section
            return mark_safe(html)
            
        except Exception as e:
            return mark_safe(f'<span style="color: #dc3545;">Error loading management interface: {e}</span>')
    
    @admin.display(description='Recent Activity')
    def recent_activity_display(self, obj):
        """Display recent activity in compact admin-friendly format"""
        try:
            from datetime import timedelta
            from django.utils import timezone
            
            # Get recent access logs for this user (last 7 days, limited)
            seven_days_ago = timezone.now() - timedelta(days=7)
            recent_logs = AccessLog.objects.filter(
                user=obj.username,
                timestamp__gte=seven_days_ago
            ).order_by('-timestamp')[:15]  # Limit to 15 most recent
            
            if not recent_logs:
                return mark_safe('<div style="color: #6c757d; font-style: italic; padding: 12px; background: #f8f9fa; border-radius: 4px;">No recent activity (last 7 days)</div>')
            
            html = '<div style="background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 0; max-height: 300px; overflow-y: auto;">'
            
            # Header
            html += '<div style="background: #e9ecef; padding: 8px 12px; border-bottom: 1px solid #dee2e6; font-weight: 600; font-size: 12px; color: #495057;">'
            html += f'📊 Recent Activity ({recent_logs.count()} entries, last 7 days)'
            html += '</div>'
            
            # Activity entries
            for i, log in enumerate(recent_logs):
                bg_color = '#ffffff' if i % 2 == 0 else '#f8f9fa'
                local_time = localtime(log.timestamp)
                
                # Status icon and color
                if log.action == 'Success':
                    icon = '✅'
                    status_color = '#28a745'
                elif log.action == 'Failed':
                    icon = '❌'
                    status_color = '#dc3545'
                else:
                    icon = 'ℹ️'
                    status_color = '#6c757d'
                
                html += f'<div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 12px; border-bottom: 1px solid #f1f3f4; background: {bg_color};">' 
                
                # Left side - server and link info
                html += f'<div style="display: flex; gap: 8px; align-items: center; flex: 1; min-width: 0;">'
                html += f'<span style="color: {status_color}; font-size: 14px;">{icon}</span>'
                html += f'<div style="overflow: hidden;">'
                html += f'<div style="font-weight: 500; font-size: 12px; color: #495057; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{log.server}</div>'
                
                if log.acl_link_id:
                    link_short = log.acl_link_id[:12] + '...' if len(log.acl_link_id) > 12 else log.acl_link_id
                    html += f'<div style="font-family: monospace; font-size: 10px; color: #6c757d;">{link_short}</div>'
                
                html += f'</div></div>'
                
                # Right side - timestamp and status
                html += f'<div style="text-align: right; flex-shrink: 0;">'
                html += f'<div style="font-size: 10px; color: #6c757d;">{local_time.strftime("%m-%d %H:%M")}</div>'
                html += f'<div style="font-size: 9px; color: {status_color}; font-weight: 500;">{log.action}</div>'
                html += f'</div>'
                
                html += f'</div>'
            
            # Footer with summary if there are more entries
            total_recent = AccessLog.objects.filter(
                user=obj.username,
                timestamp__gte=seven_days_ago
            ).count()
            
            if total_recent > 15:
                html += f'<div style="background: #e9ecef; padding: 6px 12px; font-size: 11px; color: #6c757d; text-align: center;">'
                html += f'Showing 15 of {total_recent} entries from last 7 days'
                html += f'</div>'
            
            html += '</div>'
            return mark_safe(html)
            
        except Exception as e:
            return mark_safe(f'<span style="color: #dc3545; font-size: 12px;">Error loading activity: {e}</span>')

    @admin.display(description='Telegram Account')
    def telegram_info_display(self, obj):
        """Display Telegram account information"""
        if not obj.telegram_user_id:
            if obj.telegram_username:
                return mark_safe(f'<div style="background: #fff3cd; padding: 10px; border-radius: 5px; border-left: 4px solid #ffc107;">'
                               f'<span style="color: #856404;">🔗 Ready to link: @{obj.telegram_username}</span><br/>'
                               f'<small>User will be automatically linked when they message the bot</small></div>')
            else:
                return mark_safe('<span style="color: #6c757d;">No Telegram account linked</span>')
        
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">'
        html += '<h4 style="margin: 0 0 10px 0; color: #495057;">📱 Telegram Account Information</h4>'
        
        # Telegram User ID
        html += f'<p style="margin: 5px 0;"><strong>User ID:</strong> <code>{obj.telegram_user_id}</code></p>'
        
        # Telegram Username
        if obj.telegram_username:
            html += f'<p style="margin: 5px 0;"><strong>Username:</strong> @{obj.telegram_username}</p>'
        
        # Telegram Names
        name_parts = []
        if obj.telegram_first_name:
            name_parts.append(obj.telegram_first_name)
        if obj.telegram_last_name:
            name_parts.append(obj.telegram_last_name)
        
        if name_parts:
            full_name = ' '.join(name_parts)
            html += f'<p style="margin: 5px 0;"><strong>Name:</strong> {full_name}</p>'
        
        # Telegram Phone (if available)
        if obj.telegram_phone:
            html += f'<p style="margin: 5px 0;"><strong>Phone:</strong> {obj.telegram_phone}</p>'
        
        # Access requests count (if any)
        try:
            from telegram_bot.models import AccessRequest
            requests_count = AccessRequest.objects.filter(telegram_user_id=obj.telegram_user_id).count()
            if requests_count > 0:
                html += f'<p style="margin: 10px 0 5px 0; color: #007cba;"><strong>📝 Access Requests:</strong> {requests_count}</p>'
                
                # Show latest request status
                latest_request = AccessRequest.objects.filter(telegram_user_id=obj.telegram_user_id).order_by('-created_at').first()
                if latest_request:
                    status_color = '#28a745' if latest_request.approved else '#ffc107'
                    status_text = 'Approved' if latest_request.approved else 'Pending'
                    html += f'<p style="margin: 5px 0 5px 20px;">Latest: <span style="color: {status_color}; font-weight: bold;">{status_text}</span></p>'
        except:
            pass  # Telegram bot app might not be available
        
        # Add unlink button
        unlink_url = reverse('admin:vpn_user_unlink_telegram', args=[obj.pk])
        html += f'<div style="margin-top: 15px; padding-top: 10px; border-top: 1px solid #dee2e6;">'
        html += f'<a href="{unlink_url}" class="button" style="background: #dc3545; color: white; text-decoration: none; padding: 8px 15px; border-radius: 3px; font-size: 13px;" onclick="return confirm(\'Are you sure you want to unlink this Telegram account?\')">🔗💥 Unlink Telegram Account</a>'
        html += '</div>'
        
        html += '</div>'
        return mark_safe(html)

    @admin.display(description='Allowed servers', ordering='server_count')
    def server_count(self, obj):
        return obj.server_count
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(server_count=Count('acl'))
        return qs
    
    def get_urls(self):
        """Add custom URLs for link management"""
        urls = super().get_urls()
        custom_urls = [
            path('<int:user_id>/add-link/', self.admin_site.admin_view(self.add_link_view), name='user_add_link'),
            path('<int:user_id>/delete-link/<int:link_id>/', self.admin_site.admin_view(self.delete_link_view), name='user_delete_link'),
            path('<int:user_id>/add-server-access/', self.admin_site.admin_view(self.add_server_access_view), name='user_add_server_access'),
            path('<int:user_id>/unlink-telegram/', self.admin_site.admin_view(self.unlink_telegram_view), name='vpn_user_unlink_telegram'),
        ]
        return custom_urls + urls
    
    def add_link_view(self, request, user_id):
        """AJAX view to add a new link for user on specific server"""
        if request.method == 'POST':
            try:
                user = User.objects.get(pk=user_id)
                server_id = request.POST.get('server_id')
                comment = request.POST.get('comment', '')
                
                if not server_id:
                    return JsonResponse({'error': 'Server ID is required'}, status=400)
                
                server = Server.objects.get(pk=server_id)
                acl = ACL.objects.get(user=user, server=server)
                
                # Create new link
                new_link = ACLLink.objects.create(
                    acl=acl,
                    comment=comment,
                    link=shortuuid.ShortUUID().random(length=16)
                )
                
                return JsonResponse({
                    'success': True,
                    'link_id': new_link.id,
                    'link': new_link.link,
                    'comment': new_link.comment,
                    'url': f"{EXTERNAL_ADDRESS}/ss/{new_link.link}#{server.name}"
                })
                
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    def delete_link_view(self, request, user_id, link_id):
        """AJAX view to delete a specific link"""
        if request.method == 'POST':
            try:
                user = User.objects.get(pk=user_id)
                link = ACLLink.objects.get(pk=link_id, acl__user=user)
                link.delete()
                
                return JsonResponse({'success': True})
                
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    def add_server_access_view(self, request, user_id):
        """AJAX view to add server access for user"""
        if request.method == 'POST':
            try:
                user = User.objects.get(pk=user_id)
                server_id = request.POST.get('server_id')
                
                if not server_id:
                    return JsonResponse({'error': 'Server ID is required'}, status=400)
                
                server = Server.objects.get(pk=server_id)
                
                # Check if ACL already exists
                if ACL.objects.filter(user=user, server=server).exists():
                    return JsonResponse({'error': 'User already has access to this server'}, status=400)
                
                # Create new ACL (with default link)
                acl = ACL.objects.create(user=user, server=server)
                
                return JsonResponse({
                    'success': True,
                    'server_name': server.name,
                    'server_type': server.server_type,
                    'acl_id': acl.id
                })
                
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    def unlink_telegram_view(self, request, user_id):
        """Unlink Telegram account from user"""
        user = get_object_or_404(User, pk=user_id)
        
        if request.method == 'GET':
            # Store original Telegram info for logging
            telegram_info = {
                'user_id': user.telegram_user_id,
                'username': user.telegram_username,
                'first_name': user.telegram_first_name,
                'last_name': user.telegram_last_name
            }
            
            # Clear all Telegram fields
            user.telegram_user_id = None
            user.telegram_username = ""
            user.telegram_first_name = ""
            user.telegram_last_name = ""
            user.telegram_phone = ""
            user.save()
            
            # Also clean up any related access requests
            try:
                from telegram_bot.models import AccessRequest
                AccessRequest.objects.filter(telegram_user_id=telegram_info['user_id']).delete()
            except:
                pass  # Telegram bot app might not be available
            
            messages.success(
                request, 
                f"Telegram account {'@' + telegram_info['username'] if telegram_info['username'] else telegram_info['user_id']} "
                f"has been unlinked from user '{user.username}'"
            )
            
        return HttpResponseRedirect(reverse('admin:vpn_user_change', args=[user_id]))
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to add user management data and fix layout"""
        extra_context = extra_context or {}
        
        if object_id:
            try:
                user = User.objects.get(pk=object_id)
                extra_context.update({
                    'user_object': user,
                    'external_address': EXTERNAL_ADDRESS,
                })
                
            except User.DoesNotExist:
                pass
        
        return super().change_view(request, object_id, form_url, extra_context)