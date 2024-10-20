from .generic import Server
from django.db import models
from polymorphic.admin import (
    PolymorphicChildModelAdmin,
)
from django.contrib import admin
from django.db.models import Count
from django.utils.safestring import mark_safe

class WireguardServer(Server):
    address = models.CharField(max_length=100)
    port = models.IntegerField()
    client_private_key = models.CharField(max_length=255)
    server_publick_key = models.CharField(max_length=255)

    class Meta:
        verbose_name = 'Wireguard'
        verbose_name_plural = 'Wireguard'

    def save(self, *args, **kwargs):
        self.server_type = 'Wireguard'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.address})"

    def get_server_status(self):
        status = super().get_server_status()
        status.update({
            "address": self.address,
            "port": self.port,
            "client_private_key": self.client_private_key,
            "server_publick_key": self.server_publick_key,
        })
        return status
    
class WireguardServerAdmin(PolymorphicChildModelAdmin):
    base_model = WireguardServer
    show_in_index = False  # Не отображать в главном списке админки
    list_display = (
        'name',
        'address',
        'port',
        'server_publick_key',
        'client_private_key',
        'server_status_inline',
        'user_count',
        'registration_date'
    )
    readonly_fields = ('server_status_full', )
    exclude = ('server_type',)

    @admin.display(description='Clients', ordering='user_count')
    def user_count(self, obj):
        return obj.user_count

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(user_count=Count('acl__user'))
        return qs

    def server_status_inline(self, obj):
        status = obj.get_server_status()
        if 'error' in status:
            return mark_safe(f"<span style='color: red;'>Error: {status['error']}</span>")
        return mark_safe(f"<pre>{status}</pre>")
    server_status_inline.short_description = "Server Status"

    def server_status_full(self, obj):
        if obj and obj.pk:
            status = obj.get_server_status()
            if 'error' in status:
                return mark_safe(f"<span style='color: red;'>Error: {status['error']}</span>")
            return mark_safe(f"<pre>{status}</pre>")
        return "N/A"

    server_status_full.short_description = "Server Status"

    def get_model_perms(self, request):
        """It disables display for sub-model"""
        return {}
    
admin.site.register(WireguardServer, WireguardServerAdmin)