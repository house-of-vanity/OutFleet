from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()


class BotSettings(models.Model):
    """Singleton model for bot settings"""
    bot_token = models.CharField(
        max_length=255, 
        help_text="Telegram Bot Token from @BotFather"
    )
    enabled = models.BooleanField(
        default=False,
        help_text="Enable/Disable the bot"
    )
    use_proxy = models.BooleanField(
        default=False,
        help_text="Enable proxy for Telegram API connections"
    )
    proxy_url = models.URLField(
        blank=True,
        help_text="Proxy URL (e.g., http://proxy:8080 or socks5://proxy:1080)"
    )
    api_base_url = models.URLField(
        blank=True,
        default="https://api.telegram.org",
        help_text="Telegram API base URL (change for local bot API server)"
    )
    connection_timeout = models.IntegerField(
        default=30,
        help_text="Connection timeout in seconds"
    )
    telegram_admins = models.ManyToManyField(
        User,
        blank=True,
        related_name='bot_admin_settings',
        help_text="Users with linked Telegram accounts who will have admin access in the bot"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Bot Settings"
        verbose_name_plural = "Bot Settings"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.pk = 1
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Prevent deletion
        pass
    
    @classmethod
    def get_settings(cls):
        """Get or create singleton settings"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    
    def __str__(self):
        return f"Bot Settings ({'Enabled' if self.enabled else 'Disabled'})"


class TelegramMessage(models.Model):
    """Store all telegram messages"""
    DIRECTION_CHOICES = [
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
    ]
    
    direction = models.CharField(
        max_length=10, 
        choices=DIRECTION_CHOICES,
        db_index=True
    )
    
    # Telegram user info
    telegram_user_id = models.BigIntegerField(db_index=True)
    telegram_username = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        db_index=True
    )
    telegram_first_name = models.CharField(
        max_length=255, 
        blank=True, 
        null=True
    )
    telegram_last_name = models.CharField(
        max_length=255, 
        blank=True, 
        null=True
    )
    user_language = models.CharField(
        max_length=10,
        default='en',
        help_text="User's preferred language (en/ru)"
    )
    
    # Message info
    chat_id = models.BigIntegerField(db_index=True)
    message_id = models.BigIntegerField(null=True, blank=True)
    message_text = models.TextField(blank=True)
    
    # Additional data
    raw_data = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Full message data from Telegram"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Optional link to VPN user if identified
    linked_user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='telegram_messages'
    )
    
    class Meta:
        verbose_name = "Telegram Message"
        verbose_name_plural = "Telegram Messages"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'direction']),
            models.Index(fields=['telegram_user_id', '-created_at']),
        ]
    
    def __str__(self):
        username = self.telegram_username or f"ID:{self.telegram_user_id}"
        direction_icon = "⬇️" if self.direction == 'incoming' else "⬆️"
        text_preview = self.message_text[:50] + "..." if len(self.message_text) > 50 else self.message_text
        return f"{direction_icon} {username}: {text_preview}"
    
    @property
    def full_name(self):
        """Get full name of telegram user"""
        parts = []
        if self.telegram_first_name:
            parts.append(self.telegram_first_name)
        if self.telegram_last_name:
            parts.append(self.telegram_last_name)
        return " ".join(parts) if parts else f"User {self.telegram_user_id}"
    
    @property
    def display_name(self):
        """Get best available display name"""
        if self.telegram_username:
            return f"`@{self.telegram_username}`"
        return self.full_name




class AccessRequest(models.Model):
    """Access requests from Telegram users"""
    
    # Telegram user information
    telegram_user_id = models.BigIntegerField(
        db_index=True,
        help_text="Telegram user ID who made the request"
    )
    telegram_username = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Telegram username (without @)"
    )
    telegram_first_name = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="First name from Telegram"
    )
    telegram_last_name = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Last name from Telegram"
    )
    
    # Request details
    message_text = models.TextField(
        help_text="The message sent by user when requesting access"
    )
    chat_id = models.BigIntegerField(
        help_text="Telegram chat ID for sending notifications"
    )
    
    # Username for VPN user creation
    desired_username = models.CharField(
        max_length=150,
        blank=True,
        help_text="Desired username for VPN user (defaults to Telegram username)"
    )
    
    # User language
    user_language = models.CharField(
        max_length=10,
        default='en',
        help_text="User's preferred language (en/ru)"
    )
    
    # Status and processing
    approved = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Request approved by administrator"
    )
    admin_comment = models.TextField(
        blank=True,
        help_text="Admin comment for approval"
    )
    
    # Related objects
    selected_existing_user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='selected_for_requests',
        help_text="Existing user selected to link with this Telegram account"
    )
    created_user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="User created from this request (when approved)"
    )
    processed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='processed_requests',
        help_text="Admin who processed this request"
    )
    first_message = models.ForeignKey(
        TelegramMessage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="First message from this user"
    )
    
    # Inbound templates and subscription groups
    selected_inbounds = models.ManyToManyField(
        'vpn.Inbound',
        blank=True,
        help_text="Inbound templates to assign to the user"
    )
    selected_subscription_groups = models.ManyToManyField(
        'vpn.SubscriptionGroup',
        blank=True,
        help_text="Subscription groups to assign to the user"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Access Request"
        verbose_name_plural = "Access Requests"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['telegram_user_id']),
            models.Index(fields=['approved', '-created_at']),
            models.Index(fields=['-created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['telegram_user_id'], 
                name='unique_telegram_user_request'
            )
        ]
    
    def __str__(self):
        username = self.telegram_username or f"ID:{self.telegram_user_id}"
        status = "Approved" if self.approved else "Pending"
        return f"Request from @{username} ({status})"
    
    @property
    def display_name(self):
        """Get best available display name"""
        if self.telegram_username:
            return f"`@{self.telegram_username}`"
        
        name_parts = []
        if self.telegram_first_name:
            name_parts.append(self.telegram_first_name)
        if self.telegram_last_name:
            name_parts.append(self.telegram_last_name)
        
        if name_parts:
            return " ".join(name_parts)
        
        return f"User {self.telegram_user_id}"
    
    @property
    def full_name(self):
        """Get full name of telegram user"""
        parts = []
        if self.telegram_first_name:
            parts.append(self.telegram_first_name)
        if self.telegram_last_name:
            parts.append(self.telegram_last_name)
        return " ".join(parts) if parts else None
