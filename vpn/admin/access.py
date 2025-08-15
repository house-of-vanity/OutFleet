"""
Access control admin interfaces (ACL, ACLLink)
"""
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.timezone import localtime
from django.db.models import Q

from mysite.settings import EXTERNAL_ADDRESS
from vpn.models import ACL, ACLLink, User
from .base import BaseVPNAdmin
from vpn.utils import format_object


class UserNameFilter(admin.SimpleListFilter):
    title = 'User'
    parameter_name = 'user'

    def lookups(self, request, model_admin):
        users = set(User.objects.values_list('username', flat=True))
        return [(user, user) for user in users]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(user__username=self.value())
        return queryset


class ServerNameFilter(admin.SimpleListFilter):
    title = 'Server Name'
    parameter_name = 'acl__server__name'

    def lookups(self, request, model_admin):
        servers = set(ACL.objects.values_list('server__name', flat=True))
        return [(server, server) for server in servers]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(acl__server__name=self.value())
        return queryset


class LastAccessFilter(admin.SimpleListFilter):
    title = 'Last Access'
    parameter_name = 'last_access_status'

    def lookups(self, request, model_admin):
        return [
            ('never', 'Never accessed'),
            ('week', 'Last week'),
            ('month', 'Last month'),
            ('old', 'Older than 3 months'),
        ]

    def queryset(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        
        if self.value() == 'never':
            # Links that have never been accessed
            return queryset.filter(last_access_time__isnull=True)
        elif self.value() == 'week':
            # Links accessed in the last week
            week_ago = timezone.now() - timedelta(days=7)
            return queryset.filter(last_access_time__gte=week_ago)
        elif self.value() == 'month':
            # Links accessed in the last month
            month_ago = timezone.now() - timedelta(days=30)
            return queryset.filter(last_access_time__gte=month_ago)
        elif self.value() == 'old':
            # Links not accessed for more than 3 months
            three_months_ago = timezone.now() - timedelta(days=90)
            return queryset.filter(last_access_time__lt=three_months_ago)
        return queryset


class ACLLinkInline(admin.TabularInline):
    model = ACLLink
    extra = 1
    help_text = 'Add or change ACL links'
    verbose_name = 'Dynamic link'
    verbose_name_plural = 'Dynamic links'
    fields = ('link', 'generate_link_button', 'comment')
    readonly_fields = ('generate_link_button',)

    @admin.display(description="Generate")
    def generate_link_button(self, obj=None):
        return format_html(
            '<button type="button" class="generate-link" onclick="generateLink(this)">🔄</button>'
        )

    class Media:
        js = ('admin/js/generate_link.js',)


@admin.register(ACL)
class ACLAdmin(BaseVPNAdmin):
    list_display = ('user', 'server', 'server_type', 'display_links', 'created_at')
    list_filter = (UserNameFilter, 'server__server_type', ServerNameFilter)
    # Fixed search_fields - removed problematic polymorphic server fields
    search_fields = ('user__username', 'user__comment', 'links__link')
    readonly_fields = ('user_info',)
    inlines = [ACLLinkInline]

    @admin.display(description='Server Type', ordering='server__server_type')
    def server_type(self, obj):
        return obj.server.get_server_type_display()

    @admin.display(description='Client info')
    def user_info(self, obj):
        server = obj.server
        user = obj.user
        try:
            # Use cached statistics instead of direct server requests
            from vpn.models import UserStatistics
            user_stats = UserStatistics.objects.filter(
                user=user,
                server_name=server.name
            ).first()
            
            if user_stats:
                # Format cached data nicely
                data = {
                    'user': user.username,
                    'server': server.name,
                    'total_connections': user_stats.total_connections,
                    'recent_connections': user_stats.recent_connections,
                    'max_daily': user_stats.max_daily,
                    'last_updated': user_stats.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'from_cache'
                }
                return format_object(data)
            else:
                # Fallback to minimal server check (avoid slow API calls on admin pages)
                return mark_safe(
                    '<div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 8px; border-radius: 4px;">' +
                    '<strong>ℹ️ User Statistics:</strong><br>' +
                    'No cached statistics available.<br>' +
                    '<small>Run "Update user statistics cache" action to populate data.</small>' +
                    '</div>'
                )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get cached user info for {user.username} on {server.name}: {e}")
            return mark_safe(f"<span style='color: red;'>Cache error: {e}</span>")

    @admin.display(description='User Links')
    def display_links(self, obj):
        links_count = obj.links.count()
        portal_url = f"{EXTERNAL_ADDRESS}/u/{obj.user.hash}"
        
        return format_html(
            '<div style="font-size: 12px; margin-bottom: 8px;">'
            '<strong>🔗 {} link(s)</strong>'
            '</div>'
            '<a href="{}" target="_blank" style="background: #4ade80; color: #000; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 11px; font-weight: bold;">🌐 User Portal</a>',
            links_count, portal_url
        )


# Note: UserStatistics is not registered separately as admin model.
# All user statistics functionality is integrated into ACLLinkAdmin below.
@admin.register(ACLLink)
class ACLLinkAdmin(BaseVPNAdmin):
    list_display = ('link_display', 'user_display', 'server_display', 'comment_display', 'stats_display', 'usage_chart_display', 'last_access_display', 'created_display')
    list_filter = ('acl__server__name', 'acl__server__server_type', LastAccessFilter, 'acl__user__username')
    search_fields = ('link', 'comment', 'acl__user__username', 'acl__server__name')
    list_per_page = 100
    actions = ['delete_selected_links', 'update_statistics_action']
    list_select_related = ('acl__user', 'acl__server')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related('acl__user', 'acl__server')
        return qs

    @admin.display(description='Link', ordering='link')
    def link_display(self, obj):
        link_url = f"{EXTERNAL_ADDRESS}/ss/{obj.link}#{obj.acl.server.name}"
        return format_html(
            '<a href="{}" target="_blank" style="color: #2563eb; text-decoration: none; font-family: monospace;">{}</a>',
            link_url, obj.link[:16] + '...' if len(obj.link) > 16 else obj.link
        )

    @admin.display(description='User', ordering='acl__user__username')
    def user_display(self, obj):
        return obj.acl.user.username

    @admin.display(description='Server', ordering='acl__server__name')
    def server_display(self, obj):
        server_type_icons = {
            'outline': '🔵',
            'wireguard': '🟢',
            'xray_core': '🟣',
        }
        icon = server_type_icons.get(obj.acl.server.server_type, '⚪')
        return f"{icon} {obj.acl.server.name}"

    @admin.display(description='Comment', ordering='comment')
    def comment_display(self, obj):
        if obj.comment:
            return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
        return '-'

    @admin.display(description='Statistics')
    def stats_display(self, obj):
        try:
            from vpn.models import UserStatistics
            stats = UserStatistics.objects.get(
                user=obj.acl.user,
                server_name=obj.acl.server.name,
                acl_link_id=obj.link
            )
            
            # Color coding based on usage
            if stats.total_connections > 100:
                color = '#16a34a'  # green - high usage
            elif stats.total_connections > 10:
                color = '#eab308'  # yellow - medium usage
            elif stats.total_connections > 0:
                color = '#f97316'  # orange - low usage
            else:
                color = '#9ca3af'  # gray - no usage
            
            return mark_safe(
                f'<div style="font-size: 12px;">'
                f'<span style="color: {color}; font-weight: bold;">✨ {stats.total_connections} total</span><br>'
                f'<span style="color: #6b7280;">📅 {stats.recent_connections} last 30d</span>'
                f'</div>'
            )
        except:
            return mark_safe('<span style="color: #dc2626; font-size: 12px;">No cache</span>')

    @admin.display(description='30-day Chart')
    def usage_chart_display(self, obj):
        try:
            from vpn.models import UserStatistics
            stats = UserStatistics.objects.get(
                user=obj.acl.user,
                server_name=obj.acl.server.name,
                acl_link_id=obj.link
            )
            
            if not stats.daily_usage:
                return mark_safe('<span style="color: #9ca3af; font-size: 11px;">No data</span>')
            
            # Create wider mini chart for better visibility
            max_val = max(stats.daily_usage) if stats.daily_usage else 1
            chart_html = '<div style="display: flex; align-items: end; gap: 1px; height: 35px; width: 180px;">'
            
            # Show last 30 days with wider bars for better visibility
            for day_count in stats.daily_usage[-30:]:  # Last 30 days
                if max_val > 0:
                    height_percent = (day_count / max_val) * 100
                else:
                    height_percent = 0
                
                color = '#4ade80' if day_count > 0 else '#e5e7eb'
                chart_html += f'<div style="background: {color}; width: 5px; height: {height_percent}%; min-height: 1px; border-radius: 1px;" title="{day_count} connections"></div>'
            
            chart_html += '</div>'
            
            # Add summary info below chart
            total_last_30 = sum(stats.daily_usage[-30:]) if stats.daily_usage else 0
            avg_daily = total_last_30 / 30 if total_last_30 > 0 else 0
            chart_html += f'<div style="font-size: 10px; color: #6b7280; margin-top: 2px;">'
            chart_html += f'Max: {max_val} | Avg: {avg_daily:.1f}'
            chart_html += f'</div>'
            
            return mark_safe(chart_html)
        except:
            return mark_safe('<span style="color: #dc2626; font-size: 11px;">-</span>')

    @admin.display(description='Last Access', ordering='last_access_time')
    def last_access_display(self, obj):
        if obj.last_access_time:
            from django.utils import timezone
            from datetime import timedelta
            
            local_time = localtime(obj.last_access_time)
            now = timezone.now()
            diff = now - obj.last_access_time
            
            # Color coding based on age
            if diff <= timedelta(days=7):
                color = '#16a34a'  # green - recent
            elif diff <= timedelta(days=30):
                color = '#eab308'  # yellow - medium
            elif diff <= timedelta(days=90):
                color = '#f97316'  # orange - old
            else:
                color = '#dc2626'  # red - very old
            
            formatted_date = local_time.strftime('%Y-%m-%d %H:%M')
            
            # Add relative time info
            if diff.days > 365:
                relative = f'{diff.days // 365}y ago'
            elif diff.days > 30:
                relative = f'{diff.days // 30}mo ago'
            elif diff.days > 0:
                relative = f'{diff.days}d ago'
            elif diff.seconds > 3600:
                relative = f'{diff.seconds // 3600}h ago'
            else:
                relative = 'Recently'
            
            return mark_safe(
                f'<span style="color: {color}; font-weight: bold; font-size: 12px;">{formatted_date}</span>'
                f'<br><small style="color: {color}; font-size: 10px;">{relative}</small>'
            )
        return mark_safe('<span style="color: #dc2626; font-weight: bold; font-size: 12px;">Never</span>')

    @admin.display(description='Created', ordering='acl__created_at')
    def created_display(self, obj):
        local_time = localtime(obj.acl.created_at)
        return local_time.strftime('%Y-%m-%d %H:%M')

    def delete_selected_links(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'Successfully deleted {count} ACL link(s).')
    delete_selected_links.short_description = "Delete selected ACL links"
    
    def update_statistics_action(self, request, queryset):
        """Trigger comprehensive statistics update for all users and links"""
        # This action doesn't require selected items
        try:
            from vpn.tasks import update_user_statistics
            
            # Start the statistics update task
            task = update_user_statistics.delay()
            
            self.message_user(
                request,
                f'📊 Statistics update started successfully! Task ID: {task.id}. '
                f'This will recalculate usage statistics for all users and links. '
                f'Refresh this page in a few moments to see updated data.',
                level=messages.SUCCESS
            )
            
        except Exception as e:
            self.message_user(
                request,
                f'❌ Failed to start statistics update: {e}',
                level=messages.ERROR
            )
    update_statistics_action.short_description = "📊 Update all user statistics and usage data"

    def get_actions(self, request):
        """Remove default delete action and keep only custom one"""
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return True
    
    def changelist_view(self, request, extra_context=None):
        # Handle actions that don't require item selection
        if 'action' in request.POST:
            action = request.POST['action']
            if action == 'update_statistics_action':
                # Call the action directly without queryset requirement
                self.update_statistics_action(request, None)
                # Return redirect to prevent AttributeError
                return redirect(request.get_full_path())
        
        # Add comprehensive statistics to the changelist
        extra_context = extra_context or {}
        
        # Get queryset for statistics
        queryset = self.get_queryset(request)
        
        total_links = queryset.count()
        never_accessed = queryset.filter(last_access_time__isnull=True).count()
        
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count, Max, Min
        
        now = timezone.now()
        one_week_ago = now - timedelta(days=7)
        one_month_ago = now - timedelta(days=30)
        three_months_ago = now - timedelta(days=90)
        
        # Access time statistics
        old_links = queryset.filter(
            Q(last_access_time__lt=three_months_ago) | Q(last_access_time__isnull=True)
        ).count()
        
        recent_week = queryset.filter(last_access_time__gte=one_week_ago).count()
        recent_month = queryset.filter(last_access_time__gte=one_month_ago).count()
        
        # Calculate comprehensive statistics from cache
        try:
            from vpn.models import UserStatistics
            from django.db import models
            
            # Total usage statistics
            cached_stats = UserStatistics.objects.aggregate(
                total_uses=models.Sum('total_connections'),
                recent_uses=models.Sum('recent_connections'),
                max_daily_peak=models.Max('max_daily')
            )
            total_uses = cached_stats['total_uses'] or 0
            recent_uses = cached_stats['recent_uses'] or 0
            max_daily_peak = cached_stats['max_daily_peak'] or 0
            
            # Server and user breakdown
            server_stats = UserStatistics.objects.values('server_name').annotate(
                total_connections=models.Sum('total_connections'),
                link_count=models.Count('id')
            ).order_by('-total_connections')[:5]  # Top 5 servers
            
            user_stats = UserStatistics.objects.values('user__username').annotate(
                total_connections=models.Sum('total_connections'),
                link_count=models.Count('id')
            ).order_by('-total_connections')[:5]  # Top 5 users
            
            # Links with cache data count
            cached_links_count = UserStatistics.objects.filter(
                acl_link_id__isnull=False
            ).count()
            
        except Exception as e:
            total_uses = 0
            recent_uses = 0
            max_daily_peak = 0
            server_stats = []
            user_stats = []
            cached_links_count = 0
        
        # Active vs inactive breakdown
        active_links = total_links - never_accessed - old_links
        if active_links < 0:
            active_links = 0
        
        extra_context.update({
            'total_links': total_links,
            'never_accessed': never_accessed,
            'old_links': old_links,
            'active_links': active_links,
            'recent_week': recent_week,
            'recent_month': recent_month,
            'total_uses': total_uses,
            'recent_uses': recent_uses,
            'max_daily_peak': max_daily_peak,
            'server_stats': server_stats,
            'user_stats': user_stats,
            'cached_links_count': cached_links_count,
            'cache_coverage_percent': (cached_links_count * 100 // total_links) if total_links > 0 else 0,
        })
        
        return super().changelist_view(request, extra_context)
    
    def get_ordering(self, request):
        """Allow sorting by annotated fields"""
        # Handle sorting by last_access_time if requested
        order_var = request.GET.get('o')
        if order_var:
            try:
                field_index = int(order_var.lstrip('-'))
                # Check if this corresponds to the last_access column (index 6 in list_display)
                if field_index == 6:  # last_access_display is at index 6
                    if order_var.startswith('-'):
                        return ['-last_access_time']
                    else:
                        return ['last_access_time']
            except (ValueError, IndexError):
                pass
        
        # Default ordering
        return ['-acl__created_at', 'acl__user__username']