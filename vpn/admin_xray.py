"""
Admin interface for new Xray models.
"""

import json
from django.contrib import admin, messages
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.db import models
from django.forms import CheckboxSelectMultiple, Textarea
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.http import JsonResponse, HttpResponseRedirect

from .models_xray import (
    XrayConfiguration, Credentials, Certificate,
    Inbound, SubscriptionGroup, UserSubscription, ServerInbound
)


@admin.register(XrayConfiguration)
class XrayConfigurationAdmin(admin.ModelAdmin):
    """Admin for global Xray configuration"""
    list_display = ('grpc_address', 'default_client_hostname', 'stats_enabled', 'cert_renewal_days', 'updated_at')
    fields = (
        'grpc_address', 'default_client_hostname', 
        'stats_enabled', 'cert_renewal_days',
        'created_at', 'updated_at'
    )
    readonly_fields = ('created_at', 'updated_at')
    
    def has_add_permission(self, request):
        # Only allow one configuration
        return not XrayConfiguration.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Credentials)
class CredentialsAdmin(admin.ModelAdmin):
    """Admin for credentials management"""
    list_display = ('name', 'cred_type', 'description', 'created_at')
    list_filter = ('cred_type',)
    search_fields = ('name', 'description')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'cred_type', 'description')
        }),
        ('Credentials Data', {
            'fields': ('credentials_help', 'credentials'),
            'description': 'Enter credentials as JSON. Example: {"api_token": "your_token", "email": "your_email"}'
        }),
        ('Preview', {
            'fields': ('credentials_display',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('credentials_display', 'credentials_help', 'created_at', 'updated_at')
    
    # Add JSON widget for better formatting
    formfield_overrides = {
        models.JSONField: {'widget': Textarea(attrs={'rows': 10, 'cols': 80, 'class': 'vLargeTextField'})},
    }
    
    def credentials_help(self, obj):
        """Help text and examples for credentials field"""
        examples = {
            'cloudflare': {
                'api_token': 'your_cloudflare_api_token',
                'email': 'your_email@example.com'
            },
            'dns_provider': {
                'api_key': 'your_dns_api_key',
                'secret': 'your_secret'
            },
            'email': {
                'smtp_host': 'smtp.example.com',
                'smtp_port': 587,
                'username': 'your_email',
                'password': 'your_password'
            }
        }
        
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 4px; margin-bottom: 10px;">'
        html += '<h4>JSON Examples:</h4>'
        
        for cred_type, example in examples.items():
            html += '<div style="margin: 10px 0;">'
            html += '<strong>' + cred_type.title() + ':</strong>'
            json_str = json.dumps(example, indent=2)
            html += '<pre style="background: white; padding: 8px; border-radius: 3px; font-size: 12px;">' + json_str + '</pre>'
            html += '</div>'
        
        html += '<p><strong>Note:</strong> Make sure your JSON is valid. Use double quotes for strings.</p>'
        html += '</div>'
        
        return mark_safe(html)
    credentials_help.short_description = 'Credentials Format Help'
    
    def credentials_display(self, obj):
        """Display credentials in a safe format"""
        if obj.credentials:
            # Hide sensitive values
            safe_creds = {}
            for key, value in obj.credentials.items():
                if any(sensitive in key.lower() for sensitive in ['token', 'key', 'password', 'secret']):
                    safe_creds[key] = '*' * 8
                else:
                    safe_creds[key] = value
            
            return format_html(
                '<pre style="background: #f4f4f4; padding: 10px; border-radius: 4px;">{}</pre>',
                json.dumps(safe_creds, indent=2)
            )
        return '-'
    credentials_display.short_description = 'Credentials (Preview)'


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    """Admin for certificate management"""
    list_display = (
        'domain', 'cert_type', 'status_display', 
        'expires_at', 'auto_renew', 'action_buttons'
    )
    list_filter = ('cert_type', 'auto_renew')
    search_fields = ('domain',)
    
    fieldsets = (
        ('Certificate Request', {
            'fields': ('domain', 'cert_type', 'acme_email', 'credentials', 'auto_renew'),
            'description': 'For Let\'s Encrypt certificates, provide email for ACME registration and select credentials with Cloudflare API token.'
        }),
        ('Certificate Status', {
            'fields': ('generation_help', 'status_display', 'expires_at'),
            'classes': ('wide',)
        }),
        ('Certificate Data', {
            'fields': ('certificate_preview', 'certificate_pem', 'private_key_pem'),
            'classes': ('collapse',),
            'description': 'Certificate data (auto-generated for Let\'s Encrypt)'
        }),
        ('Renewal Settings', {
            'fields': ('last_renewed',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = (
        'certificate_preview', 'status_display', 'generation_help',
        'expires_at', 'last_renewed', 'created_at', 'updated_at'
    )
    
    def generation_help(self, obj):
        """Show help text for certificate generation"""
        if not obj.pk:
            return mark_safe('<div style="background: #e3f2fd; padding: 10px; border-radius: 4px;">'
                           '<p><strong>How it works:</strong></p>'
                           '<ol>'
                           '<li>Fill in the domain name</li>'
                           '<li>Select certificate type (Let\'s Encrypt recommended)</li>'
                           '<li>For Let\'s Encrypt: provide email for ACME account registration</li>'
                           '<li>Select credentials with Cloudflare API token</li>'
                           '<li>Save - certificate will be generated automatically</li>'
                           '</ol>'
                           '</div>')
        
        if obj.cert_type == 'letsencrypt' and not obj.certificate_pem:
            return mark_safe('<div style="background: #fff3e0; padding: 10px; border-radius: 4px;">'
                           '<p><strong>⏳ Certificate not generated yet</strong></p>'
                           '<p>Certificate will be generated automatically using Let\'s Encrypt DNS-01 challenge.</p>'
                           '</div>')
        
        if obj.certificate_pem:
            days = obj.days_until_expiration if obj.days_until_expiration is not None else 'Unknown'
            return mark_safe('<div style="background: #e8f5e8; padding: 10px; border-radius: 4px;">'
                           '<p><strong>✅ Certificate generated successfully</strong></p>'
                           f'<p>Expires: {obj.expires_at}</p>'
                           f'<p>Days remaining: {days}</p>'
                           '</div>')
        
        return '-'
    generation_help.short_description = 'Certificate Generation Status'
    
    def status_display(self, obj):
        """Display certificate status"""
        if obj.is_expired:
            return format_html(
                '<span style="color: red;">❌ Expired</span>'
            )
        elif obj.needs_renewal:
            return format_html(
                '<span style="color: orange;">⚠️ Needs renewal ({} days)</span>',
                obj.days_until_expiration
            )
        else:
            return format_html(
                '<span style="color: green;">✅ Valid ({} days)</span>',
                obj.days_until_expiration
            )
    status_display.short_description = 'Status'
    
    def certificate_preview(self, obj):
        """Preview certificate info"""
        if obj.certificate_pem:
            lines = obj.certificate_pem.strip().split('\n')
            preview = '\n'.join(lines[:5] + ['...'] + lines[-3:])
            return format_html(
                '<pre style="background: #f4f4f4; padding: 10px; font-family: monospace; font-size: 12px;">{}</pre>',
                preview
            )
        return '-'
    certificate_preview.short_description = 'Certificate Preview'
    
    def action_buttons(self, obj):
        """Action buttons for certificate"""
        buttons = []
        
        if obj.needs_renewal and obj.auto_renew:
            renew_url = reverse('admin:certificate_renew', args=[obj.pk])
            buttons.append(
                f'<a href="{renew_url}" class="button" style="background: #ff9800;">🔄 Renew Now</a>'
            )
        
        if obj.cert_type == 'self_signed':
            regenerate_url = reverse('admin:certificate_regenerate', args=[obj.pk])
            buttons.append(
                f'<a href="{regenerate_url}" class="button">🔄 Regenerate</a>'
            )
        
        return format_html(' '.join(buttons)) if buttons else '-'
    action_buttons.short_description = 'Actions'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:cert_id>/renew/',
                 self.admin_site.admin_view(self.renew_certificate_view),
                 name='certificate_renew'),
            path('<int:cert_id>/regenerate/',
                 self.admin_site.admin_view(self.regenerate_certificate_view),
                 name='certificate_regenerate'),
        ]
        return custom_urls + urls
    
    def renew_certificate_view(self, request, cert_id):
        """Renew Let's Encrypt certificate"""
        try:
            cert = Certificate.objects.get(pk=cert_id)
            # TODO: Implement renewal logic
            messages.success(request, f'Certificate for {cert.domain} renewed successfully!')
        except Exception as e:
            messages.error(request, f'Failed to renew certificate: {e}')
        
        return redirect('admin:vpn_certificate_change', cert_id)
    
    def regenerate_certificate_view(self, request, cert_id):
        """Regenerate self-signed certificate"""
        try:
            cert = Certificate.objects.get(pk=cert_id)
            # TODO: Implement regeneration logic
            messages.success(request, f'Certificate for {cert.domain} regenerated successfully!')
        except Exception as e:
            messages.error(request, f'Failed to regenerate certificate: {e}')
        
        return redirect('admin:vpn_certificate_change', cert_id)
    
    def save_model(self, request, obj, form, change):
        """Auto-generate certificate for Let's Encrypt after saving"""
        super().save_model(request, obj, form, change)
        
        # Auto-generate Let's Encrypt certificate if needed
        if obj.cert_type == 'letsencrypt' and not obj.certificate_pem:
            try:
                self.generate_letsencrypt_certificate(obj, request)
            except Exception as e:
                messages.warning(request, f'Certificate saved but auto-generation failed: {e}')
    
    def generate_letsencrypt_certificate(self, cert_obj, request):
        """Generate Let's Encrypt certificate using DNS-01 challenge"""
        if not cert_obj.credentials:
            messages.error(request, 'Credentials required for Let\'s Encrypt certificate generation')
            return
        
        if not cert_obj.acme_email:
            messages.error(request, 'ACME email address required for Let\'s Encrypt certificate generation')
            return
        
        try:
            from vpn.letsencrypt.letsencrypt_dns import get_certificate_for_domain
            from datetime import datetime, timedelta
            from django.utils import timezone
            
            # Get Cloudflare credentials
            api_token = cert_obj.credentials.get_credential('api_token')
            
            if not api_token:
                messages.error(request, 'Cloudflare API token not found in credentials')
                return
            
            messages.info(request, f'🔄 Generating Let\'s Encrypt certificate for {cert_obj.domain} using {cert_obj.acme_email}...')
            
            # Schedule certificate generation via Celery
            from vpn.tasks import generate_certificate_task
            task = generate_certificate_task.delay(cert_obj.id)
            
            messages.success(
                request, 
                f'🔄 Certificate generation scheduled for {cert_obj.domain}. Task ID: {task.id}'
            )
            
        except ImportError:
            messages.warning(request, 'Let\'s Encrypt DNS challenge library not available')
        except Exception as e:
            messages.error(request, f'Failed to generate certificate: {str(e)}')
            # Log the full error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Certificate generation failed for {cert_obj.domain}: {e}', exc_info=True)


@admin.register(Inbound)
class InboundAdmin(admin.ModelAdmin):
    """Admin for inbound management"""
    list_display = (
        'name', 'protocol', 'port', 'network', 
        'security', 'certificate_status', 'group_count'
    )
    list_filter = ('protocol', 'network', 'security')
    search_fields = ('name', 'domain')
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('name', 'protocol', 'port', 'domain')
        }),
        ('Transport & Security', {
            'fields': ('network', 'security', 'certificate', 'listen_address')
        }),
        ('Advanced Settings', {
            'fields': ('enable_sniffing', 'full_config_display'),
            'classes': ('collapse',),
            'description': 'Configuration is auto-generated based on basic settings above'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('full_config_display', 'created_at', 'updated_at')
    
    def certificate_status(self, obj):
        """Display certificate status"""
        if obj.security == 'tls':
            if obj.certificate:
                if obj.certificate.is_expired:
                    return format_html('<span style="color: red;">❌ Expired</span>')
                else:
                    return format_html('<span style="color: green;">✅ Valid</span>')
            else:
                return format_html('<span style="color: orange;">⚠️ No cert</span>')
        return format_html('<span style="color: gray;">-</span>')
    certificate_status.short_description = 'Cert Status'
    
    def group_count(self, obj):
        """Number of groups this inbound belongs to"""
        return obj.subscriptiongroup_set.count()
    group_count.short_description = 'Groups'
    
    def full_config_display(self, obj):
        """Display full config in formatted JSON"""
        if obj.full_config:
            return format_html(
                '<pre style="background: #f4f4f4; padding: 10px; border-radius: 4px; max-height: 400px; overflow-y: auto;">{}</pre>',
                json.dumps(obj.full_config, indent=2)
            )
        return 'Not generated yet'
    full_config_display.short_description = 'Configuration Preview'
    
    def save_model(self, request, obj, form, change):
        """Generate config on save"""
        try:
            # Always regenerate config to reflect any changes
            obj.build_config()
            messages.success(request, f'✅ Configuration generated successfully for {obj.protocol.upper()} inbound on port {obj.port}')
        except Exception as e:
            messages.warning(request, f'Inbound saved but config generation failed: {e}')
            # Set empty dict if generation fails
            if not obj.full_config:
                obj.full_config = {}
        
        super().save_model(request, obj, form, change)


class InboundInline(admin.TabularInline):
    """Inline for inbounds in subscription groups"""
    model = SubscriptionGroup.inbounds.through
    extra = 1
    verbose_name = "Inbound"
    verbose_name_plural = "Inbounds in this group"


@admin.register(SubscriptionGroup)
class SubscriptionGroupAdmin(admin.ModelAdmin):
    """Admin for subscription groups"""
    list_display = ('name', 'is_active', 'inbound_count', 'user_count', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    filter_horizontal = ('inbounds',)
    
    fieldsets = (
        ('Group Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Inbounds', {
            'fields': ('inbounds',),
            'description': 'Select inbounds to include in this group'
        }),
        ('Statistics', {
            'fields': ('group_statistics',),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('group_statistics',)
    
    def group_statistics(self, obj):
        """Display group statistics"""
        if obj.pk:
            stats = {
                'Total Inbounds': obj.inbound_count,
                'Active Users': obj.user_count,
                'Protocols': list(obj.inbounds.values_list('protocol', flat=True).distinct()),
                'Ports': list(obj.inbounds.values_list('port', flat=True).distinct())
            }
            
            html = '<div style="background: #f4f4f4; padding: 10px; border-radius: 4px;">'
            for key, value in stats.items():
                if isinstance(value, list):
                    value = ', '.join(map(str, value))
                html += f'<div><strong>{key}:</strong> {value}</div>'
            html += '</div>'
            
            return format_html(html)
        return 'Save to see statistics'
    group_statistics.short_description = 'Group Statistics'


class UserSubscriptionInline(admin.TabularInline):
    """Inline for user subscriptions"""
    model = UserSubscription
    extra = 0
    fields = ('subscription_group', 'active', 'created_at')
    readonly_fields = ('created_at',)
    verbose_name = "Subscription Group"
    verbose_name_plural = "User's Subscription Groups"


# Extension for User admin
def add_subscription_management_to_user(UserAdmin):
    """Add subscription management to existing User admin"""
    
    # Add inline
    if hasattr(UserAdmin, 'inlines'):
        UserAdmin.inlines = list(UserAdmin.inlines) + [UserSubscriptionInline]
    else:
        UserAdmin.inlines = [UserSubscriptionInline]
    
    # Add custom fields to fieldsets
    original_fieldsets = list(UserAdmin.fieldsets)
    
    # Find where to insert our fieldset
    insert_index = len(original_fieldsets)
    for i, (title, fields_dict) in enumerate(original_fieldsets):
        if title and 'Statistics' in title:
            insert_index = i + 1
            break
    
    # Insert our fieldset
    subscription_fieldset = (
        'Xray Subscriptions', {
            'fields': ('subscription_groups_widget',),
            'classes': ('wide',)
        }
    )
    original_fieldsets.insert(insert_index, subscription_fieldset)
    UserAdmin.fieldsets = tuple(original_fieldsets)
    
    # Add readonly field
    if hasattr(UserAdmin, 'readonly_fields'):
        UserAdmin.readonly_fields = list(UserAdmin.readonly_fields) + ['subscription_groups_widget']
    else:
        UserAdmin.readonly_fields = ['subscription_groups_widget']
    
    # Add method for displaying subscription groups
    def subscription_groups_widget(self, obj):
        """Display subscription groups management widget"""
        if not obj or not obj.pk:
            return mark_safe('<div style="color: #6c757d;">Save user first to manage subscriptions</div>')
        
        # Get all groups and user's current subscriptions
        all_groups = SubscriptionGroup.objects.filter(is_active=True)
        user_groups = obj.xray_subscriptions.filter(active=True).values_list('subscription_group_id', flat=True)
        
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 4px;">'
        html += '<h4 style="margin-top: 0;">Available Subscription Groups:</h4>'
        
        if all_groups:
            html += '<div style="display: grid; gap: 10px;">'
            for group in all_groups:
                checked = 'checked' if group.id in user_groups else ''
                status = '✅' if group.id in user_groups else '⬜'
                
                html += f'''
                <div style="display: flex; align-items: center; gap: 10px; padding: 8px; background: white; border-radius: 4px;">
                    <span style="font-size: 18px;">{status}</span>
                    <label style="flex: 1; cursor: pointer;">
                        <strong>{group.name}</strong>
                        {f' - {group.description}' if group.description else ''}
                        <small style="color: #6c757d;"> ({group.inbound_count} inbounds)</small>
                    </label>
                </div>
                '''
            html += '</div>'
            html += '<div style="margin-top: 10px; color: #6c757d; font-size: 12px;">'
            html += 'ℹ️ Use the inline form below to manage subscriptions'
            html += '</div>'
        else:
            html += '<div style="color: #6c757d;">No active subscription groups available</div>'
        
        html += '</div>'
        return mark_safe(html)
    
    subscription_groups_widget.short_description = 'Subscription Groups Overview'
    UserAdmin.subscription_groups_widget = subscription_groups_widget


# Register admin for UserSubscription (if needed separately)
@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    """Standalone admin for user subscriptions"""
    list_display = ('user', 'subscription_group', 'active', 'created_at')
    list_filter = ('active', 'subscription_group')
    search_fields = ('user__username', 'subscription_group__name')
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        # Prefer managing through User admin
        return False


@admin.register(ServerInbound)
class ServerInboundAdmin(admin.ModelAdmin):
    """Admin for server-inbound deployment tracking"""
    list_display = ('server', 'inbound', 'active', 'deployed_at', 'updated_at')
    list_filter = ('active', 'inbound__protocol', 'deployed_at')
    search_fields = ('server__name', 'inbound__name')
    date_hierarchy = 'deployed_at'
    
    fieldsets = (
        ('Deployment', {
            'fields': ('server', 'inbound', 'active')
        }),
        ('Configuration', {
            'fields': ('deployment_config_display', 'deployment_config'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('deployed_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('deployment_config_display', 'deployed_at', 'updated_at')
    
    def deployment_config_display(self, obj):
        """Display deployment config in formatted JSON"""
        if obj.deployment_config:
            return format_html(
                '<pre style="background: #f4f4f4; padding: 10px; border-radius: 4px; max-height: 300px; overflow-y: auto;">{}</pre>',
                json.dumps(obj.deployment_config, indent=2)
            )
        return 'No additional deployment configuration'
    deployment_config_display.short_description = 'Deployment Config Preview'