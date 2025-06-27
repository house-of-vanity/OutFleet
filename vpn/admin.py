import json
from polymorphic.admin import (
    PolymorphicParentModelAdmin,
)
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.db.models import Count
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import path, reverse
from django.http import HttpResponseRedirect

from django.contrib.auth.admin import UserAdmin
from .models import User, AccessLog
from django.utils.timezone import localtime
from vpn.models import User, ACL, ACLLink
from vpn.forms import UserForm
from mysite.settings import EXTERNAL_ADDRESS
from .server_plugins import (
    Server,
    WireguardServer,
    WireguardServerAdmin,
    OutlineServer,
    OutlineServerAdmin)


admin.site.site_title = "VPN Manager"
admin.site.site_header = "VPN Manager"
admin.site.index_title = "OutFleet"

def format_object(data):
    try:  
        if isinstance(data, dict):
            formatted_data = json.dumps(data, indent=2)
            return mark_safe(f"<pre>{formatted_data}</pre>")
        elif isinstance(data, str):
            return mark_safe(f"<pre>{data}</pre>")
        else:
            return mark_safe(f"<pre>{str(data)}</pre>")
    except Exception as e:
        return mark_safe(f"<span style='color: red;'>Error: {e}</span>")

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

@admin.register(Server)
class ServerAdmin(PolymorphicParentModelAdmin):
    base_model = Server
    child_models = (OutlineServer, WireguardServer)
    list_display = ('name', 'server_type', 'comment', 'registration_date', 'user_count', 'server_status_inline')
    search_fields = ('name', 'comment')
    list_filter = ('server_type', )
    actions = ['move_clients_action']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('move-clients/', self.admin_site.admin_view(self.move_clients_view), name='server_move_clients'),
        ]
        return custom_urls + urls

    def move_clients_action(self, request, queryset):
        if queryset.count() == 0:
            self.message_user(request, "Select al least two servers.", level=messages.ERROR)
            return
        
        selected_ids = ','.join(str(server.id) for server in queryset)
        return HttpResponseRedirect(f"{reverse('admin:server_move_clients')}?servers={selected_ids}")

    move_clients_action.short_description = "Move client links between servers"

    def move_clients_view(self, request):
        """View for moving clients between servers"""
        if request.method == 'GET':
            # Get selected servers from URL parameters
            server_ids = request.GET.get('servers', '').split(',')
            if not server_ids or server_ids == ['']:
                messages.error(request, "No servers selected.")
                return redirect('admin:vpn_server_changelist')
            
            try:
                # Only work with database objects, don't check server connectivity
                servers = Server.objects.filter(id__in=server_ids)
                all_servers = Server.objects.all()
                
                # Get ACL links for selected servers with related data
                # This is purely database operation, no server connectivity required
                links_by_server = {}
                for server in servers:
                    try:
                        # Get all ACL links for this server with user and ACL data
                        links = ACLLink.objects.filter(
                            acl__server=server
                        ).select_related('acl__user', 'acl__server').order_by('acl__user__username', 'comment')
                        links_by_server[server] = links
                    except Exception as e:
                        # Log the error but continue with other servers
                        messages.warning(request, f"Warning: Could not load links for server {server.name}: {e}")
                        links_by_server[server] = []
                
                context = {
                    'title': 'Move Client Links Between Servers',
                    'servers': servers,
                    'all_servers': all_servers,
                    'links_by_server': links_by_server,
                }
                
                return render(request, 'admin/move_clients.html', context)
                
            except Exception as e:
                messages.error(request, f"Database error while loading data: {e}")
                return redirect('admin:vpn_server_changelist')
        
        elif request.method == 'POST':
            # Process the transfer of ACL links - purely database operations
            try:
                source_server_id = request.POST.get('source_server')
                target_server_id = request.POST.get('target_server')
                selected_link_ids = request.POST.getlist('selected_links')
                
                if not source_server_id or not target_server_id:
                    messages.error(request, "Please select both source and target servers.")
                    return redirect(request.get_full_path())
                
                if source_server_id == target_server_id:
                    messages.error(request, "Source and target servers cannot be the same.")
                    return redirect(request.get_full_path())
                
                if not selected_link_ids:
                    messages.error(request, "Please select at least one link to move.")
                    return redirect(request.get_full_path())
                
                # Get server objects from database only
                try:
                    source_server = Server.objects.get(id=source_server_id)
                    target_server = Server.objects.get(id=target_server_id)
                except Server.DoesNotExist:
                    messages.error(request, "One of the selected servers was not found in database.")
                    return redirect('admin:vpn_server_changelist')
                
                moved_count = 0
                errors = []
                users_processed = set()
                
                # Process each selected link - database operations only
                for link_id in selected_link_ids:
                    try:
                        # Get the ACL link with related ACL and user data
                        acl_link = ACLLink.objects.select_related('acl__user', 'acl__server').get(
                            id=link_id, 
                            acl__server=source_server
                        )
                        user = acl_link.acl.user
                        
                        # Check if user already has ACL on target server
                        target_acl = ACL.objects.filter(user=user, server=target_server).first()
                        
                        if target_acl:
                            created = False
                        else:
                            # Create new ACL without auto-creating default link
                            target_acl = ACL(user=user, server=target_server)
                            target_acl.save(auto_create_link=False)
                            created = True
                        
                        # Move the link to target ACL - pure database operation
                        acl_link.acl = target_acl
                        acl_link.save()
                        
                        moved_count += 1
                        users_processed.add(user.username)
                        
                        if created:
                            messages.info(request, f"Created new ACL for user {user.username} on server {target_server.name}")
                        
                    except ACLLink.DoesNotExist:
                        errors.append(f"Link with ID {link_id} not found on source server")
                    except Exception as e:
                        errors.append(f"Database error moving link {link_id}: {e}")
                
                # Clean up empty ACLs on source server - database operation only
                try:
                    empty_acls = ACL.objects.filter(
                        server=source_server,
                        links__isnull=True
                    )
                    deleted_acls_count = empty_acls.count()
                    empty_acls.delete()
                except Exception as e:
                    messages.warning(request, f"Warning: Could not clean up empty ACLs: {e}")
                    deleted_acls_count = 0
                
                if moved_count > 0:
                    messages.success(request, 
                        f"Successfully moved {moved_count} link(s) for {len(users_processed)} user(s) "
                        f"from '{source_server.name}' to '{target_server.name}'. "
                        f"Cleaned up {deleted_acls_count} empty ACL(s)."
                    )
                
                if errors:
                    for error in errors:
                        messages.error(request, error)
                
                return redirect('admin:vpn_server_changelist')
                
            except Exception as e:
                messages.error(request, f"Database error during link transfer: {e}")
                return redirect('admin:vpn_server_changelist')

    @admin.display(description='User Count', ordering='user_count')
    def user_count(self, obj):
        return obj.user_count

    @admin.display(description='Status')
    def server_status_inline(self, obj):
        try:
            status = obj.get_server_status()
            if 'error' in status:
                return mark_safe(f"<span style='color: red;'>Error: {status['error']}</span>")
            import json
            pretty_status = ", ".join(f"{key}: {value}" for key, value in status.items())
            return mark_safe(f"<pre>{pretty_status}</pre>")
        except Exception as e:
            # Don't let server connectivity issues break the admin interface
            return mark_safe(f"<span style='color: orange;'>Status unavailable: {e}</span>")
    server_status_inline.short_description = "Status"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(user_count=Count('acl'))
        return qs

#admin.site.register(User, UserAdmin)
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserForm
    list_display = ('username', 'comment', 'registration_date', 'hash_link', 'server_count')
    search_fields = ('username', 'hash')
    readonly_fields = ('hash_link',)

    @admin.display(description='API access', ordering='hash')
    def hash_link(self, obj):
        url = f"{EXTERNAL_ADDRESS}/stat/{obj.hash}"
        return format_html('<a href="{}">JSON server list</a>', url, obj.hash)

    @admin.display(description='Allowed servers', ordering='server_count')
    def server_count(self, obj):
        return obj.server_count

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(server_count=Count('acl'))
        return qs

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        selected_servers = form.cleaned_data.get('servers', [])

        # Remove ACLs that are no longer selected
        ACL.objects.filter(user=obj).exclude(server__in=selected_servers).delete()

        # Create new ACLs for newly selected servers (with default links)
        for server in selected_servers:
            acl, created = ACL.objects.get_or_create(user=obj, server=server)
            # Note: get_or_create will use the default save() method which creates default links

@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'server', 'action', 'formatted_timestamp')
    list_filter = ('user', 'server', 'action', 'timestamp')
    search_fields = ('user', 'server', 'action', 'timestamp', 'data')
    readonly_fields = ('server', 'user', 'formatted_timestamp', 'action', 'formated_data')

    @admin.display(description='Timestamp')
    def formatted_timestamp(self, obj):
        local_time = localtime(obj.timestamp)
        return local_time.strftime('%Y-%m-%d %H:%M:%S %Z')
    
    @admin.display(description='Details')
    def formated_data(self, obj):
        return format_object(obj.data)


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
class ACLAdmin(admin.ModelAdmin):

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
            data = server.get_user(user)
            return format_object(data)
        except Exception as e:
            return mark_safe(f"<span style='color: red;'>Error: {e}</span>")

    @admin.display(description='Dynamic Config Links')
    def display_links(self, obj):
        links = obj.links.all()
        formatted_links = [f"{link.comment} - {EXTERNAL_ADDRESS}/ss/{link.link}#{link.acl.server.name}" for link in links]
        return mark_safe('<br>'.join(formatted_links))

try:
    from django_celery_results.models import GroupResult
    from django_celery_beat.models import (
        PeriodicTask, 
        ClockedSchedule, 
        CrontabSchedule, 
        IntervalSchedule, 
        SolarSchedule
    )
    
    admin.site.unregister(GroupResult)
    admin.site.unregister(PeriodicTask)
    admin.site.unregister(ClockedSchedule)
    admin.site.unregister(CrontabSchedule)
    admin.site.unregister(IntervalSchedule)
    admin.site.unregister(SolarSchedule)
    
except (ImportError, admin.sites.NotRegistered):
    pass
