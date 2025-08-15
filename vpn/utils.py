"""
Utility functions for VPN application
"""
import json
from django.utils.safestring import mark_safe


def format_object(data):
    """
    Format various data types for display in Django admin interface
    """
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