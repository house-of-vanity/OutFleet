"""
Base utilities and common imports for VPN admin interfaces
"""
import json
import shortuuid
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.db.models import Count
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import path, reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.utils.timezone import localtime
from django.db.models import Max, Subquery, OuterRef, Q

from mysite.settings import EXTERNAL_ADDRESS


def format_bytes(bytes_val):
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f}PB"


class BaseVPNAdmin(admin.ModelAdmin):
    """Base admin class with common functionality"""
    
    class Media:
        css = {
            'all': ('admin/css/vpn_admin.css',)
        }
    
    def get_external_address(self):
        """Get external address for links"""
        return EXTERNAL_ADDRESS
    
    def format_hash_link(self, obj, hash_value):
        """Format hash as clickable link"""
        if not hash_value:
            return mark_safe('<span style="color: #dc3545;">No hash</span>')
        
        portal_url = f"https://{EXTERNAL_ADDRESS}/u/{hash_value}"
        return mark_safe(
            f'<div style="display: flex; align-items: center; gap: 10px;">'
            f'<code style="background: #f8f9fa; padding: 4px 8px; border-radius: 3px; font-size: 12px;">{hash_value[:12]}...</code>'
            f'<a href="{portal_url}" target="_blank" style="color: #007cba; text-decoration: none;">🔗 Portal</a>'
            f'</div>'
        )


class BaseListFilter(admin.SimpleListFilter):
    """Base filter class with common functionality"""
    pass