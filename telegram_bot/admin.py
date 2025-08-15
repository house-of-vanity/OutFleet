from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from .models import BotSettings, TelegramMessage, AccessRequest
from .localization import MessageLocalizer
import logging

logger = logging.getLogger(__name__)


@admin.register(BotSettings)
class BotSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'enabled', 'bot_token_display', 'updated_at')
    fieldsets = (
        ('Bot Configuration', {
            'fields': ('bot_token', 'enabled', 'bot_status_display'),
            'description': 'Configure bot settings and view current status'
        }),
        ('Connection Settings', {
            'fields': ('api_base_url', 'connection_timeout', 'use_proxy', 'proxy_url'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at', 'bot_status_display')
    
    def bot_token_display(self, obj):
        """Mask bot token for security"""
        if obj.bot_token:
            token = obj.bot_token
            if len(token) > 10:
                return f"{token[:6]}...{token[-4:]}"
            return "Token set"
        return "No token set"
    bot_token_display.short_description = "Bot Token"
    
    def bot_status_display(self, obj):
        """Display bot status with control buttons"""
        from .bot import TelegramBotManager
        import os
        from django.conf import settings as django_settings
        
        manager = TelegramBotManager()
        
        # Check if lock file exists - only reliable indicator
        lock_dir = os.path.join(getattr(django_settings, 'BASE_DIR', '/tmp'), 'telegram_bot_locks')
        lock_path = os.path.join(lock_dir, 'telegram_bot.lock')
        is_running = os.path.exists(lock_path)
        
        if is_running:
            status_html = '<span style="color: green; font-weight: bold;">🟢 Bot is RUNNING</span>'
        else:
            status_html = '<span style="color: red; font-weight: bold;">🔴 Bot is STOPPED</span>'
        
        # Add control buttons
        status_html += '<br><br>'
        if is_running:
            status_html += f'<a class="button" href="{reverse("admin:telegram_bot_stop_bot")}">Stop Bot</a> '
            status_html += f'<a class="button" href="{reverse("admin:telegram_bot_restart_bot")}">Restart Bot</a>'
        else:
            if obj.enabled and obj.bot_token:
                status_html += f'<a class="button" href="{reverse("admin:telegram_bot_start_bot")}">Start Bot</a>'
            else:
                status_html += '<span style="color: gray;">Configure bot token and enable bot to start</span>'
        
        return format_html(status_html)
    bot_status_display.short_description = "Bot Status"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('start-bot/', self.start_bot, name='telegram_bot_start_bot'),
            path('stop-bot/', self.stop_bot, name='telegram_bot_stop_bot'),
            path('restart-bot/', self.restart_bot, name='telegram_bot_restart_bot'),
        ]
        return custom_urls + urls
    
    def start_bot(self, request):
        """Start the telegram bot"""
        try:
            from .bot import TelegramBotManager
            manager = TelegramBotManager()
            manager.start()
            messages.success(request, "Bot started successfully!")
        except Exception as e:
            messages.error(request, f"Failed to start bot: {e}")
            logger.error(f"Failed to start bot: {e}")
        
        return redirect('admin:telegram_bot_botsettings_change', object_id=1)
    
    def stop_bot(self, request):
        """Stop the telegram bot"""
        try:
            from .bot import TelegramBotManager
            manager = TelegramBotManager()
            manager.stop()
            messages.success(request, "Bot stopped successfully!")
        except Exception as e:
            messages.error(request, f"Failed to stop bot: {e}")
            logger.error(f"Failed to stop bot: {e}")
        
        return redirect('admin:telegram_bot_botsettings_change', object_id=1)
    
    def restart_bot(self, request):
        """Restart the telegram bot"""
        try:
            from .bot import TelegramBotManager
            manager = TelegramBotManager()
            manager.restart()
            messages.success(request, "Bot restarted successfully!")
        except Exception as e:
            messages.error(request, f"Failed to restart bot: {e}")
            logger.error(f"Failed to restart bot: {e}")
        
        return redirect('admin:telegram_bot_botsettings_change', object_id=1)
    
    def has_add_permission(self, request):
        # Prevent creating multiple instances
        return not BotSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion
        return False


@admin.register(TelegramMessage)
class TelegramMessageAdmin(admin.ModelAdmin):
    list_display = (
        'created_at', 
        'direction_display', 
        'user_display', 
        'language_display',
        'message_preview',
        'linked_user'
    )
    list_filter = (
        'direction', 
        'created_at',
        ('linked_user', admin.EmptyFieldListFilter),
    )
    search_fields = (
        'telegram_username', 
        'telegram_first_name', 
        'telegram_last_name',
        'message_text',
        'telegram_user_id'
    )
    readonly_fields = (
        'direction',
        'telegram_user_id',
        'telegram_username',
        'telegram_first_name',
        'telegram_last_name',
        'chat_id',
        'message_id',
        'message_text',
        'raw_data_display',
        'created_at',
        'linked_user',
        'user_language'
    )
    
    fieldsets = (
        ('Message Info', {
            'fields': (
                'direction',
                'message_text',
                'created_at'
            )
        }),
        ('Telegram User', {
            'fields': (
                'telegram_user_id',
                'telegram_username',
                'telegram_first_name',
                'telegram_last_name',
            )
        }),
        ('Technical Details', {
            'fields': (
                'chat_id',
                'message_id',
                'linked_user',
                'raw_data_display'
            ),
            'classes': ('collapse',)
        })
    )
    
    ordering = ['-created_at']
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    def direction_display(self, obj):
        """Display direction with icon"""
        if obj.direction == 'incoming':
            return format_html('<span style="color: blue;">⬇️ Incoming</span>')
        else:
            return format_html('<span style="color: green;">⬆️ Outgoing</span>')
    direction_display.short_description = "Direction"
    
    def user_display(self, obj):
        """Display user info"""
        display = obj.display_name
        if obj.telegram_user_id:
            display += f" (ID: {obj.telegram_user_id})"
        return display
    user_display.short_description = "Telegram User"
    
    def language_display(self, obj):
        """Display user language"""
        lang_map = {'ru': '🇷🇺 RU', 'en': '🇺🇸 EN'}
        return lang_map.get(obj.user_language, obj.user_language or 'Unknown')
    language_display.short_description = "Language"
    
    def message_preview(self, obj):
        """Show message preview"""
        if len(obj.message_text) > 100:
            return obj.message_text[:100] + "..."
        return obj.message_text
    message_preview.short_description = "Message"
    
    def raw_data_display(self, obj):
        """Display raw data as formatted JSON"""
        import json
        if obj.raw_data:
            formatted = json.dumps(obj.raw_data, indent=2, ensure_ascii=False)
            return format_html('<pre style="max-width: 800px; overflow: auto;">{}</pre>', formatted)
        return "No raw data"
    raw_data_display.short_description = "Raw Data"
    
    def has_add_permission(self, request):
        # Messages are created automatically by bot
        return False
    
    def has_change_permission(self, request, obj=None):
        # Messages are read-only
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Allow deletion for cleanup
        return request.user.is_superuser
    
    def get_actions(self, request):
        """Add custom actions"""
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            # Remove delete action for non-superusers
            if 'delete_selected' in actions:
                del actions['delete_selected']
        return actions


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'user_display', 
        'approved_display',
        'language_display',
        'desired_username_display',
        'message_preview',
        'created_user',
        'processed_by'
    )
    list_filter = (
        'approved',
        'created_at',
        'processed_at',
        ('processed_by', admin.EmptyFieldListFilter),
    )
    search_fields = (
        'telegram_username',
        'telegram_first_name', 
        'telegram_last_name',
        'telegram_user_id',
        'message_text'
    )
    readonly_fields = (
        'telegram_user_id',
        'telegram_username', 
        'telegram_first_name',
        'telegram_last_name',
        'message_text',
        'chat_id',
        'created_at',
        'first_message',
        'processed_at',
        'processed_by',
        'created_user',
        'user_language'
    )
    
    fieldsets = (
        ('Request Info', {
            'fields': (
                'approved',
                'admin_comment',
                'created_at',
                'processed_at',
                'processed_by'
            )
        }),
        ('User Creation', {
            'fields': (
                'desired_username',
            ),
            'description': 'Edit username before approving the request'
        }),
        ('Telegram User', {
            'fields': (
                'telegram_user_id',
                'telegram_username',
                'telegram_first_name',
                'telegram_last_name',
            )
        }),
        ('Message Details', {
            'fields': (
                'message_text',
                'chat_id',
                'first_message'
            ),
            'classes': ('collapse',)
        }),
        ('Processing Results', {
            'fields': (
                'created_user',
            )
        })
    )
    
    ordering = ['-created_at']
    list_per_page = 50
    date_hierarchy = 'created_at'
    actions = ['approve_requests']
    
    def user_display(self, obj):
        """Display user info"""
        return obj.display_name
    user_display.short_description = "Telegram User"
    
    def approved_display(self, obj):
        """Display approved status with colors"""
        if obj.approved:
            return format_html('<span style="color: green; font-weight: bold;">✅ Approved</span>')
        else:
            return format_html('<span style="color: orange; font-weight: bold;">🔄 Pending</span>')
    approved_display.short_description = "Status"
    
    def message_preview(self, obj):
        """Show message preview"""
        if len(obj.message_text) > 100:
            return obj.message_text[:100] + "..."
        return obj.message_text
    message_preview.short_description = "Message"
    
    def desired_username_display(self, obj):
        """Display desired username"""
        if obj.desired_username:
            return obj.desired_username
        else:
            fallback = obj.telegram_username or obj.telegram_first_name or f"tg_{obj.telegram_user_id}"
            return format_html('<span style="color: gray; font-style: italic;">{}</span>', fallback)
    desired_username_display.short_description = "Desired Username"
    
    def language_display(self, obj):
        """Display user language with flag"""
        lang_map = {'ru': '🇷🇺 RU', 'en': '🇺🇸 EN'}
        return lang_map.get(obj.user_language, obj.user_language or 'Unknown')
    language_display.short_description = "Language"
    
    def approve_requests(self, request, queryset):
        """Approve selected access requests"""
        pending_requests = queryset.filter(approved=False)
        count = 0
        errors = []
        
        for access_request in pending_requests:
            try:
                logger.info(f"Approving request {access_request.id} from user {access_request.telegram_user_id}")
                user = self._create_user_from_request(access_request, request.user)
                
                if user:
                    access_request.approved = True
                    access_request.processed_by = request.user
                    access_request.processed_at = timezone.now()
                    access_request.created_user = user
                    access_request.save()
                    
                    logger.info(f"Successfully approved request {access_request.id}, created user {user.username}")
                    
                    # Send notification to user
                    self._send_approval_notification(access_request)
                    count += 1
                else:
                    errors.append(f"Failed to create user for {access_request.display_name}")
                
            except Exception as e:
                error_msg = f"Failed to approve request from {access_request.display_name}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        if count:
            messages.success(request, f"Successfully approved {count} request(s)")
        
        if errors:
            for error in errors:
                messages.error(request, error)
    
    approve_requests.short_description = "✅ Approve selected requests"
    
    
    def _create_user_from_request(self, access_request, admin_user):
        """Create User from AccessRequest or link to existing user"""
        from vpn.models import User
        import secrets
        import string
        
        try:
            # Check if user already exists by telegram_user_id
            existing_user = User.objects.filter(telegram_user_id=access_request.telegram_user_id).first()
            if existing_user:
                logger.info(f"User already exists: {existing_user.username}")
                return existing_user
            
            # Check if we can link to existing user by telegram_username
            if access_request.telegram_username:
                existing_user_by_username = User.objects.filter(
                    telegram_username__iexact=access_request.telegram_username,
                    telegram_user_id__isnull=True  # Not yet linked to Telegram
                ).first()
                
                if existing_user_by_username:
                    # Link telegram data to existing user
                    logger.info(f"Linking Telegram @{access_request.telegram_username} to existing user {existing_user_by_username.username}")
                    existing_user_by_username.telegram_user_id = access_request.telegram_user_id
                    existing_user_by_username.telegram_username = access_request.telegram_username
                    existing_user_by_username.telegram_first_name = access_request.telegram_first_name or ""
                    existing_user_by_username.telegram_last_name = access_request.telegram_last_name or ""
                    existing_user_by_username.save()
                    return existing_user_by_username
            
            # Use desired_username if provided, otherwise fallback to Telegram data
            username = access_request.desired_username
            if not username:
                # Fallback to telegram_username, first_name or user_id
                username = access_request.telegram_username or access_request.telegram_first_name or f"tg_{access_request.telegram_user_id}"
            
            # Clean username (remove special characters)
            username = ''.join(c for c in username if c.isalnum() or c in '_-').lower()
            if not username:
                username = f"tg_{access_request.telegram_user_id}"
            
            # Make sure username is unique
            original_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{original_username}_{counter}"
                counter += 1
            
            # Create new user since no existing user found to link
            # Generate random password
            password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            
            logger.info(f"Creating new user with username: {username}")
            
            # Create user
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=access_request.telegram_first_name or "",
                last_name=access_request.telegram_last_name or "",
                telegram_user_id=access_request.telegram_user_id,
                telegram_username=access_request.telegram_username or "",
                telegram_first_name=access_request.telegram_first_name or "",
                telegram_last_name=access_request.telegram_last_name or "",
                is_active=True
            )
            
            logger.info(f"Successfully created user {user.username} (ID: {user.id}) from Telegram request {access_request.id}")
            return user
            
        except Exception as e:
            logger.error(f"Error creating user from request {access_request.id}: {e}")
            raise
    
    def _send_approval_notification(self, access_request):
        """Send approval notification via Telegram"""
        try:
            from .models import BotSettings
            from telegram import Bot
            import asyncio
            
            settings = BotSettings.get_settings()
            if not settings.enabled or not settings.bot_token:
                logger.warning("Bot not configured, skipping notification")
                return
            
            # Create a simple Bot instance for sending notification
            # This bypasses the need for the running bot manager
            async def send_notification():
                try:
                    # Create bot with custom request settings
                    from telegram.request import HTTPXRequest
                    
                    request_kwargs = {
                        'connection_pool_size': 1,
                        'read_timeout': settings.connection_timeout,
                        'write_timeout': settings.connection_timeout,
                        'connect_timeout': settings.connection_timeout,
                    }
                    
                    if settings.use_proxy and settings.proxy_url:
                        request_kwargs['proxy'] = settings.proxy_url
                    
                    request = HTTPXRequest(**request_kwargs)
                    bot = Bot(token=settings.bot_token, request=request)
                    
                    # Send localized approval message with new keyboard
                    from telegram import ReplyKeyboardMarkup, KeyboardButton
                    language = access_request.user_language or 'en'
                    
                    # Get localized texts
                    message = MessageLocalizer.get_message('approval_notification', language)
                    access_btn_text = MessageLocalizer.get_button_text('access', language)
                    
                    # Create keyboard with Access button
                    keyboard = [[KeyboardButton(access_btn_text)]]
                    reply_markup = ReplyKeyboardMarkup(
                        keyboard, 
                        resize_keyboard=True,
                        one_time_keyboard=False
                    )
                    
                    await bot.send_message(
                        chat_id=access_request.telegram_user_id,
                        text=message,
                        reply_markup=reply_markup
                    )
                    
                    logger.info(f"Sent approval notification to {access_request.telegram_user_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to send Telegram message: {e}")
                finally:
                    try:
                        # Clean up bot connection
                        await request.shutdown()
                    except:
                        pass
            
            # Run in thread to avoid blocking admin interface
            import threading
            
            def run_async_notification():
                try:
                    asyncio.run(send_notification())
                except Exception as e:
                    logger.error(f"Error in notification thread: {e}")
            
            thread = threading.Thread(target=run_async_notification, daemon=True)
            thread.start()
                
        except Exception as e:
            logger.error(f"Failed to send approval notification: {e}")
    
    
    def has_add_permission(self, request):
        # Requests are created by bot
        return False
    
    def has_change_permission(self, request, obj=None):
        # Allow changing only status and comment
        return True
    
    def save_model(self, request, obj, form, change):
        """Automatically handle approval and user creation"""
        # Check if this is a change to approved
        was_approved = False
        
        # If desired_username was changed and is empty, set default from Telegram data
        if change and 'desired_username' in form.changed_data and not obj.desired_username:
            obj.desired_username = obj.telegram_username or obj.telegram_first_name or f"tg_{obj.telegram_user_id}"
        
        if change and 'approved' in form.changed_data and obj.approved:
            # Set processed_by and processed_at
            if not obj.processed_by:
                obj.processed_by = request.user
            if not obj.processed_at:
                obj.processed_at = timezone.now()
            was_approved = True
        
        # If approved and no user created yet, create user
        if was_approved and not obj.created_user:
            try:
                logger.info(f"Auto-creating user for approved request {obj.id}")
                user = self._create_user_from_request(obj, request.user)
                if user:
                    obj.created_user = user
                    messages.success(request, f"User '{user.username}' created successfully!")
                    logger.info(f"Auto-created user {user.username} for request {obj.id}")
                    
                    # Send approval notification
                    self._send_approval_notification(obj)
                else:
                    messages.error(request, f"Failed to create user for approved request {obj.id}")
            except Exception as e:
                messages.error(request, f"Error creating user: {e}")
                logger.error(f"Error auto-creating user for request {obj.id}: {e}")
        
        # Save the object
        super().save_model(request, obj, form, change)


