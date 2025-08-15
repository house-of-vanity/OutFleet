"""
Test admin file to check if code execution works
"""

import logging
logger = logging.getLogger(__name__)
logger.info("🧪 TEST ADMIN FILE EXECUTING!")

from django.contrib import admin
from .models import User

@admin.register(User)
class TestUserAdmin(admin.ModelAdmin):
    list_display = ('username',)

logger.info("🧪 TEST ADMIN FILE COMPLETED!")