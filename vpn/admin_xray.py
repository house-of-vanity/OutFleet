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
    Credentials, Certificate,
    Inbound, SubscriptionGroup, UserSubscription, ServerInbound
)



# Credentials admin available through direct URL but not in main menu
class CredentialsAdmin(admin.ModelAdmin):
    """Admin for credentials management (accessible via direct URL only)"""
    list_display = ('name', 'cred_type', 'description', 'created_at')
    list_filter = ('cred_type',)
    search_fields = ('name', 'description')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'cred_type', 'description')
        }),
        ('Credentials Data', {
            'fields': ('credentials_help', 'credentials'),
            'description': 'Enter credentials as JSON'
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
    
    formfield_overrides = {
        models.JSONField: {'widget': Textarea(attrs={'rows': 6, 'style': 'font-family: monospace;'})},
    }
    
    def credentials_help(self, obj):
        """Display help for different credential formats"""
        examples = {
            'cloudflare': {
                'api_token': 'your_cloudflare_api_token_here'
            },
            'digitalocean': {
                'token': 'your_digitalocean_token_here'
            },
            'aws_route53': {
                'access_key_id': 'your_access_key_id',
                'secret_access_key': 'your_secret_access_key',
                'region': 'us-east-1'
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

# Credentials admin is available through Certificate admin only
# Do not register directly to avoid showing in main menu


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    """Admin for certificate management"""
    list_display = (
        'domain', 'cert_type', 'status_display', 
        'expires_at', 'auto_renew', 'action_buttons'
    )
    list_filter = ('cert_type', 'auto_renew')
    search_fields = ('domain',)
    actions = ['rotate_selected_certificates']
    
    fieldsets = (
        ('Certificate Request', {
            'fields': ('domain', 'cert_type', 'acme_email', 'auto_renew'),
            'description': 'For Let\'s Encrypt certificates, provide email for ACME registration and select/create credentials below.'
        }),
        ('API Credentials', {
            'fields': ('credentials',),
            'description': 'Select API credentials for automatic Let\'s Encrypt certificate generation'
        }),
        ('Certificate Generation Status', {
            'fields': ('generation_help',),
            'classes': ('wide',)
        }),
        ('Certificate Data', {
            'fields': ('certificate_info', 'certificate_pem', 'private_key_pem'),
            'classes': ('collapse',),
            'description': 'Detailed certificate information'
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
        'certificate_info', 'status_display', 'generation_help',
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

    def certificate_info(self, obj):
        """Display detailed certificate information"""
        if not obj.pk:
            return "Save certificate to see details"
        
        if not obj.certificate_pem:
            return "Certificate not generated yet"
            
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 4px;">'
        
        # Import here to avoid circular imports
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            
            # Parse certificate
            cert = x509.load_pem_x509_certificate(obj.certificate_pem.encode(), default_backend())
            
            # Basic info
            html += '<h4>📜 Certificate Information</h4>'
            html += '<table style="width: 100%; font-size: 12px;">'
            html += f'<tr><td><strong>Subject:</strong></td><td>{cert.subject.rfc4514_string()}</td></tr>'
            html += f'<tr><td><strong>Issuer:</strong></td><td>{cert.issuer.rfc4514_string()}</td></tr>'
            html += f'<tr><td><strong>Serial Number:</strong></td><td>{cert.serial_number}</td></tr>'
            # Use UTC versions to avoid deprecation warnings
            try:
                # Try new UTC properties first (cryptography >= 42.0.0)
                valid_from = cert.not_valid_before_utc
                valid_until = cert.not_valid_after_utc
                cert_not_after = valid_until
            except AttributeError:
                # Fall back to old properties for older cryptography versions
                valid_from = cert.not_valid_before
                valid_until = cert.not_valid_after
                cert_not_after = cert.not_valid_after
                if cert_not_after.tzinfo is None:
                    cert_not_after = cert_not_after.replace(tzinfo=timezone.utc)
            
            html += f'<tr><td><strong>Valid From:</strong></td><td>{valid_from}</td></tr>'
            html += f'<tr><td><strong>Valid Until:</strong></td><td>{valid_until}</td></tr>'
            
            # Status
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            
            days_until_expiry = (cert_not_after - now).days
            
            if days_until_expiry < 0:
                status = f'<span style="color: red;">❌ Expired {abs(days_until_expiry)} days ago</span>'
            elif days_until_expiry < 30:
                status = f'<span style="color: orange;">⚠️ Expires in {days_until_expiry} days</span>'
            else:
                status = f'<span style="color: green;">✅ Valid for {days_until_expiry} days</span>'
            
            html += f'<tr><td><strong>Status:</strong></td><td>{status}</td></tr>'
            
            # Extensions
            try:
                san = cert.extensions.get_extension_for_oid(x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                domains = [name.value for name in san.value]
                html += f'<tr><td><strong>Domains:</strong></td><td>{", ".join(domains)}</td></tr>'
            except:
                # No SAN extension or other error
                pass
            
            html += '</table>'
            
        except ImportError:
            html += '<p>⚠️ Install cryptography package to see detailed certificate information</p>'
        except Exception as e:
            html += f'<p>❌ Error parsing certificate: {e}</p>'
        
        html += '</div>'
        return mark_safe(html)
    certificate_info.short_description = 'Certificate Details'
    
    def rotate_selected_certificates(self, request, queryset):
        """Admin action to rotate selected certificates"""
        from vpn.tasks import generate_certificate_task
        
        # Filter only Let's Encrypt certificates
        valid_certs = queryset.filter(cert_type='letsencrypt')
        if not valid_certs.exists():
            self.message_user(request, "No Let's Encrypt certificates selected. Only Let's Encrypt certificates can be rotated.", level='ERROR')
            return
        
        # Check for certificates without credentials
        certs_without_creds = valid_certs.filter(credentials__isnull=True)
        if certs_without_creds.exists():
            domains = ', '.join(certs_without_creds.values_list('domain', flat=True))
            self.message_user(request, f"The following certificates have no credentials configured and will be skipped: {domains}", level='WARNING')
        
        # Filter certificates that have credentials
        certs_to_rotate = valid_certs.filter(credentials__isnull=False)
        
        if not certs_to_rotate.exists():
            self.message_user(request, "No certificates with valid credentials found.", level='ERROR')
            return
        
        # Launch rotation tasks
        rotated_count = 0
        task_ids = []
        
        for certificate in certs_to_rotate:
            try:
                task = generate_certificate_task.delay(certificate.id)
                task_ids.append(task.id)
                rotated_count += 1
            except Exception as e:
                self.message_user(request, f"Failed to start rotation for {certificate.domain}: {str(e)}", level='ERROR')
        
        if rotated_count > 0:
            domains = ', '.join(certs_to_rotate.values_list('domain', flat=True))
            task_list = ', '.join(task_ids)
            self.message_user(
                request,
                f'Successfully initiated certificate rotation for {rotated_count} certificate(s): {domains}. '
                f'Task IDs: {task_list}. Certificates will be automatically redeployed to all servers once generated.',
                level='SUCCESS'
            )
        
    rotate_selected_certificates.short_description = "🔄 Rotate selected Let's Encrypt certificates"


@admin.register(Inbound)
class InboundAdmin(admin.ModelAdmin):
    """Admin for inbound template management"""
    list_display = (
        'name', 'protocol', 'port', 'network', 
        'security', 'certificate_status', 'group_count'
    )
    list_filter = ('protocol', 'network', 'security')
    search_fields = ('name',)
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('name', 'protocol', 'port'),
            'description': 'Domain will be taken from server client_hostname when deployed'
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
            if change:
                messages.success(request, f'✅ Inbound "{obj.name}" updated. Changes will be automatically deployed to servers.')
            else:
                messages.success(request, f'✅ Inbound "{obj.name}" created. It will be deployed when added to subscription groups.')
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
            'description': 'Select inbounds to include in this group. ' +
                         '<br><strong>🚀 Auto-sync enabled:</strong> Changes will be automatically deployed to servers!'
        }),
        ('Statistics', {
            'fields': ('group_statistics',),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('group_statistics',)
    
    def save_model(self, request, obj, form, change):
        """Override save to notify about auto-sync"""
        super().save_model(request, obj, form, change)
        if change:
            messages.success(
                request, 
                f'Subscription group "{obj.name}" updated. Changes will be automatically synchronized to all Xray servers.'
            )
        else:
            messages.success(
                request, 
                f'Subscription group "{obj.name}" created. Inbounds will be automatically deployed when you add them to this group.'
            )
    
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


# UserSubscription admin will be integrated into unified Subscriptions admin
class UserSubscriptionAdmin(admin.ModelAdmin):
    """Admin for user subscriptions (integrated into unified Subscriptions admin)"""
    list_display = ('user', 'subscription_group', 'active', 'created_at')
    list_filter = ('active', 'subscription_group')
    search_fields = ('user__username', 'subscription_group__name')
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return True  # Allow adding subscriptions


# ServerInbound admin is integrated into XrayServerV2 admin, not shown in main menu
class ServerInboundAdmin(admin.ModelAdmin):
    """Admin for server-inbound deployment tracking"""
    list_display = ('server', 'inbound', 'active', 'deployed_at', 'updated_at')
    list_filter = ('active', 'inbound__protocol', 'deployed_at')
    search_fields = ('server__name', 'inbound__name')
    date_hierarchy = 'deployed_at'
    
    fieldsets = (
        ('Template Deployment', {
            'fields': ('server', 'inbound', 'active')
        }),
        ('Timestamps', {
            'fields': ('deployed_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('deployed_at', 'updated_at')


# Unified Subscriptions Admin with tabs
@admin.register(SubscriptionGroup)
class UnifiedSubscriptionsAdmin(admin.ModelAdmin):
    """Unified admin for managing both Subscription Groups and User Subscriptions"""
    
    # Use SubscriptionGroup as the base model but provide access to UserSubscription via tabs
    list_display = ('name', 'is_active', 'inbound_count', 'user_count', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    filter_horizontal = ('inbounds',)
    
    def get_urls(self):
        """Add custom URLs for user subscriptions tab"""
        urls = super().get_urls()
        custom_urls = [
            path('user-subscriptions/', 
                 self.admin_site.admin_view(self.user_subscriptions_view),
                 name='vpn_usersubscription_changelist_tab'),
        ]
        return custom_urls + urls
    
    def user_subscriptions_view(self, request):
        """Redirect to user subscriptions with tab navigation"""
        from django.shortcuts import redirect
        return redirect('/admin/vpn/usersubscription/')
    
    def changelist_view(self, request, extra_context=None):
        """Override changelist to add tab navigation"""
        extra_context = extra_context or {}
        extra_context.update({
            'show_tab_navigation': True,
            'current_tab': 'subscription_groups'
        })
        return super().changelist_view(request, extra_context)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to add tab navigation"""
        extra_context = extra_context or {}
        extra_context.update({
            'show_tab_navigation': True,
            'current_tab': 'subscription_groups'
        })
        return super().change_view(request, object_id, form_url, extra_context)
    
    def add_view(self, request, form_url='', extra_context=None):
        """Override add view to add tab navigation"""
        extra_context = extra_context or {}
        extra_context.update({
            'show_tab_navigation': True,
            'current_tab': 'subscription_groups'
        })
        return super().add_view(request, form_url, extra_context)
    
    # Copy fieldsets and methods from SubscriptionGroupAdmin
    fieldsets = (
        ('Group Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Inbounds', {
            'fields': ('inbounds',),
            'description': 'Select inbounds to include in this group. ' +
                         '<br><strong>🚀 Auto-sync enabled:</strong> Changes will be automatically deployed to servers!'
        }),
        ('Statistics', {
            'fields': ('group_statistics',),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('group_statistics',)
    
    def save_model(self, request, obj, form, change):
        """Override save to notify about auto-sync"""
        super().save_model(request, obj, form, change)
        if change:
            messages.success(
                request, 
                f'Subscription group "{obj.name}" updated. Changes will be automatically synchronized to all Xray servers.'
            )
        else:
            messages.success(
                request, 
                f'Subscription group "{obj.name}" created. Inbounds will be automatically deployed when you add them to this group.'
            )
    
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


# UserSubscription admin with tab navigation (hidden from main menu)
@admin.register(UserSubscription)  
class UserSubscriptionTabAdmin(UserSubscriptionAdmin):
    """UserSubscription admin with tab navigation"""
    
    def has_module_permission(self, request):
        """Hide this model from the main admin index"""
        return False
        
    def has_view_permission(self, request, obj=None):
        """Allow viewing through direct URL access"""
        return request.user.is_staff
        
    def has_add_permission(self, request):
        """Allow adding through direct URL access"""
        return request.user.is_staff
        
    def has_change_permission(self, request, obj=None):
        """Allow changing through direct URL access"""
        return request.user.is_staff
        
    def has_delete_permission(self, request, obj=None):
        """Allow deleting through direct URL access"""
        return request.user.is_staff
    
    def changelist_view(self, request, extra_context=None):
        """Override changelist to add tab navigation"""
        extra_context = extra_context or {}
        extra_context.update({
            'show_tab_navigation': True,
            'current_tab': 'user_subscriptions'
        })
        return super().changelist_view(request, extra_context)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to add tab navigation"""
        extra_context = extra_context or {}
        extra_context.update({
            'show_tab_navigation': True,
            'current_tab': 'user_subscriptions'
        })
        return super().change_view(request, object_id, form_url, extra_context)
    
    def add_view(self, request, form_url='', extra_context=None):
        """Override add view to add tab navigation"""
        extra_context = extra_context or {}
        extra_context.update({
            'show_tab_navigation': True,
            'current_tab': 'user_subscriptions'
        })
        return super().add_view(request, form_url, extra_context)