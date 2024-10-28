import json
from polymorphic.admin import (
    PolymorphicParentModelAdmin,
)
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.db.models import Count

from django.contrib.auth.admin import UserAdmin
from .models import User

from vpn.models import User, ACL
from vpn.forms import UserForm
from .server_plugins import (
    Server,
    WireguardServer,
    WireguardServerAdmin,
    OutlineServer,
    OutlineServerAdmin)


admin.site.site_title = "VPN Manager"
admin.site.site_header = "VPN Manager"
admin.site.index_title = "OutFleet"


@admin.register(Server)
class ServerAdmin(PolymorphicParentModelAdmin):
    base_model = Server
    child_models = (OutlineServer, WireguardServer)
    list_display = ('name', 'server_type', 'comment', 'registration_date', 'user_count', 'server_status_inline')
    search_fields = ('name', 'comment')
    list_filter = ('server_type', )

    @admin.display(description='User Count', ordering='user_count')
    def user_count(self, obj):
        return obj.user_count

    @admin.display(description='Status')
    def server_status_inline(self, obj):
        status = obj.get_server_status()
        if 'error' in status:
            return mark_safe(f"<span style='color: red;'>Error: {status['error']}</span>")
        import json
        pretty_status =  ", ".join(f"{key}: {value}" for key, value in status.items())
        return mark_safe(f"<pre>{pretty_status}</pre>")
    server_status_inline.short_description = "Status"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(user_count=Count('acl'))
        return qs

#admin.site.register(User, UserAdmin)
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserForm
    list_display = ('username', 'comment', 'registration_date', 'hash', 'server_count')
    search_fields = ('username', 'hash')
    readonly_fields = ('hash',)


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

        ACL.objects.filter(user=obj).exclude(server__in=selected_servers).delete()

        for server in selected_servers:
            ACL.objects.get_or_create(user=obj, server=server)


@admin.register(ACL)
class ACLAdmin(admin.ModelAdmin):
    list_display = ('user', 'server', 'server_type', 'link', 'created_at')
    list_filter = ('user', 'server__server_type')
    search_fields = ('user__name', 'server__name', 'server__comment', 'user__comment', 'link')
    readonly_fields = ('user_info', )

    @admin.display(description='Server Type', ordering='server__server_type')
    def server_type(self, obj):
        return obj.server.get_server_type_display()

    @admin.display(description='Client info')
    def user_info(self, obj):
        server = obj.server
        user = obj.user
        try:
            data = server.get_user(user)
            
            if isinstance(data, dict):
                formatted_data = json.dumps(data, indent=2)
                return mark_safe(f"<pre>{formatted_data}</pre>")
            elif isinstance(data, str):
                return mark_safe(f"<pre>{data}</pre>")
            else:
                return mark_safe(f"<pre>{str(data)}</pre>")
        except Exception as e:
            return mark_safe(f"<span style='color: red;'>Error: {e}</span>")