import logging
import threading
import time
import asyncio
import os
import fcntl
from typing import Optional
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from django.utils import timezone
from django.conf import settings
from asgiref.sync import sync_to_async
from .models import BotSettings, TelegramMessage, AccessRequest
from .localization import get_localized_message, get_localized_button, get_user_language, MessageLocalizer

logger = logging.getLogger(__name__)


class TelegramBotManager:
    """Singleton manager for Telegram bot with file locking"""
    _instance = None
    _lock = threading.Lock()
    _bot_thread: Optional[threading.Thread] = None
    _application: Optional[Application] = None
    _stop_event = threading.Event()
    _lockfile = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Initialize only once
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._running = False
            self._lockfile = None
            # Sync status on startup
            self._sync_status_on_startup()
    
    def _acquire_lock(self):
        """Acquire file lock to prevent multiple bot instances"""
        try:
            # Create lock file path
            lock_dir = os.path.join(getattr(settings, 'BASE_DIR', '/tmp'), 'telegram_bot_locks')
            os.makedirs(lock_dir, exist_ok=True)
            lock_path = os.path.join(lock_dir, 'telegram_bot.lock')
            
            # Open lock file
            self._lockfile = open(lock_path, 'w')
            
            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(self._lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Write PID to lock file
            self._lockfile.write(f"{os.getpid()}\n")
            self._lockfile.flush()
            
            logger.info(f"Acquired bot lock: {lock_path}")
            return True
            
        except (OSError, IOError) as e:
            if self._lockfile:
                try:
                    self._lockfile.close()
                except:
                    pass
                self._lockfile = None
            
            logger.warning(f"Could not acquire bot lock: {e}")
            return False
    
    def _release_lock(self):
        """Release file lock"""
        if self._lockfile:
            try:
                fcntl.flock(self._lockfile.fileno(), fcntl.LOCK_UN)
                self._lockfile.close()
                logger.info("Released bot lock")
            except:
                pass
            finally:
                self._lockfile = None
    
    def start(self):
        """Start the bot in a background thread"""
        if self._running:
            logger.warning("Bot is already running")
            return
        
        # Try to acquire lock first
        if not self._acquire_lock():
            raise Exception("Another bot instance is already running (could not acquire lock)")
        
        # No database status to reset - only lock file matters
        
        bot_settings = BotSettings.get_settings()
        if not bot_settings.enabled:
            self._release_lock()
            raise Exception("Bot is disabled in settings")
        
        if not bot_settings.bot_token:
            self._release_lock()
            raise Exception("Bot token is not configured")
        
        try:
            self._stop_event.clear()
            self._bot_thread = threading.Thread(target=self._run_bot, daemon=True)
            self._bot_thread.start()
            
            # Wait a moment to see if thread starts successfully
            time.sleep(0.5)
            
            # Check if thread started successfully
            if self._bot_thread.is_alive():
                logger.info("Bot started successfully")
            else:
                self._release_lock()
                raise Exception("Bot thread failed to start")
                
        except Exception as e:
            self._release_lock()
            raise e
    
    def stop(self):
        """Stop the bot"""
        if not self._running:
            logger.warning("Bot is not running")
            return
        
        logger.info("Stopping bot...")
        self._stop_event.set()
        
        if self._application:
            # Stop the application
            try:
                self._application.stop_running()
            except Exception as e:
                logger.error(f"Error stopping application: {e}")
        
        # Wait for thread to finish
        if self._bot_thread and self._bot_thread.is_alive():
            self._bot_thread.join(timeout=10)
        
        self._running = False
        
        # Release file lock
        self._release_lock()
        
        logger.info("Bot stopped")
    
    def restart(self):
        """Restart the bot"""
        logger.info("Restarting bot...")
        self.stop()
        time.sleep(2)  # Wait a bit before restarting
        self.start()
    
    def _run_bot(self):
        """Run the bot (in background thread with asyncio loop)"""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the async bot
            loop.run_until_complete(self._async_run_bot())
            
        except Exception as e:
            logger.error(f"Bot error: {e}")
            self._running = False
            # Release lock on error
            self._release_lock()
        finally:
            try:
                loop.close()
            except:
                pass
    
    async def _async_run_bot(self):
        """Async bot runner"""
        try:
            self._running = True
            settings = await sync_to_async(BotSettings.get_settings)()
            
            # Create application with custom request settings
            from telegram.request import HTTPXRequest
            
            # Prepare request settings
            request_kwargs = {
                'connection_pool_size': 8,
                'read_timeout': settings.connection_timeout,
                'write_timeout': settings.connection_timeout,
                'connect_timeout': settings.connection_timeout,
                'pool_timeout': settings.connection_timeout
            }
            
            # Add proxy if configured
            if settings.use_proxy and settings.proxy_url:
                logger.info(f"Using proxy: {settings.proxy_url}")
                request_kwargs['proxy'] = settings.proxy_url
            
            request = HTTPXRequest(**request_kwargs)
            
            # Create application builder
            app_builder = Application.builder().token(settings.bot_token).request(request)
            
            # Use custom API base URL if provided
            if settings.api_base_url and settings.api_base_url != "https://api.telegram.org":
                logger.info(f"Using custom API base URL: {settings.api_base_url}")
                app_builder = app_builder.base_url(settings.api_base_url)
            
            self._application = app_builder.build()
            
            # Add handlers
            self._application.add_handler(CommandHandler("start", self._handle_start))
            self._application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
            self._application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, self._handle_other))
            
            # Initialize application
            await self._application.initialize()
            await self._application.start()
            await self._application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
            logger.info("Bot polling started successfully")
            
            # Test connection
            try:
                logger.info("Testing bot connection...")
                bot = self._application.bot
                me = await bot.get_me()
                logger.info(f"Bot connected successfully. Bot info: @{me.username} ({me.first_name})")
            except Exception as test_e:
                logger.error(f"Bot connection test failed: {test_e}")
                logger.error(f"Connection settings - API URL: {settings.api_base_url}, Timeout: {settings.connection_timeout}s")
                if settings.use_proxy:
                    logger.error(f"Proxy settings - URL: {settings.proxy_url}")
                raise
            
            # Keep running until stop event is set
            while not self._stop_event.is_set():
                await asyncio.sleep(1)
            
            logger.info("Stop event received, shutting down...")
            
        except Exception as e:
            logger.error(f"Async bot error: {e}")
            raise
        finally:
            # Clean shutdown
            if self._application:
                try:
                    await self._application.updater.stop()
                    await self._application.stop()
                    await self._application.shutdown()
                except Exception as e:
                    logger.error(f"Error during shutdown: {e}")
            self._running = False
            # Release lock on shutdown
            self._release_lock()
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            # Save incoming message
            saved_message = await self._save_message(update.message, 'incoming')
            
            # Check if user exists by telegram_user_id
            user_response = await self._check_user_access(update.message.from_user)
            
            if user_response['action'] == 'existing_user':
                # User already exists - show keyboard with options
                from telegram import ReplyKeyboardMarkup, KeyboardButton
                
                # Create keyboard for registered users with localized buttons
                access_button = get_localized_button(update.message.from_user, 'access')
                keyboard = [
                    [KeyboardButton(access_button)],
                ]
                reply_markup = ReplyKeyboardMarkup(
                    keyboard, 
                    resize_keyboard=True,
                    one_time_keyboard=False
                )
                
                help_text = get_localized_message(update.message.from_user, 'help_text')
                sent_message = await update.message.reply_text(
                    help_text,
                    reply_markup=reply_markup
                )
                logger.info(f"Handled /start from existing user {user_response['user'].username}")
            
            elif user_response['action'] == 'show_new_user_keyboard':
                # Show keyboard with request access button for new users
                await self._show_new_user_keyboard(update)
                
            elif user_response['action'] == 'pending_request':
                # Show pending request message
                await self._show_pending_request_message(update)
            else:
                # Fallback case - show new user keyboard
                await self._show_new_user_keyboard(update)
            
            # Save outgoing message (if sent_message was created)
            if 'sent_message' in locals():
                await self._save_outgoing_message(
                    sent_message,
                    update.message.from_user
                )
            
        except Exception as e:
            logger.error(f"Error handling /start: {e}")
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        try:
            # Save incoming message
            saved_message = await self._save_message(update.message, 'incoming')
            
            # Check if user exists by telegram_user_id
            user_response = await self._check_user_access(update.message.from_user)
            
            if user_response['action'] == 'existing_user':
                # Get localized button texts for comparison
                access_btn = get_localized_button(update.message.from_user, 'access')
                all_in_one_btn = get_localized_button(update.message.from_user, 'all_in_one')
                back_btn = get_localized_button(update.message.from_user, 'back')
                group_prefix = get_localized_button(update.message.from_user, 'group_prefix')
                
                # Check if this is a keyboard command
                if update.message.text == access_btn:
                    await self._handle_access_command(update, user_response['user'])
                elif update.message.text.startswith(group_prefix):
                    # Handle specific group selection
                    group_name = update.message.text.replace(group_prefix, "")
                    await self._handle_group_selection(update, user_response['user'], group_name)
                elif update.message.text == all_in_one_btn:
                    # Handle All-in-one selection
                    await self._handle_all_in_one(update, user_response['user'])
                elif update.message.text == back_btn:
                    # Handle back button
                    await self._handle_back_to_main(update, user_response['user'])
                else:
                    # Unrecognized command - send help message
                    await self._send_help_message(update)
                return
            
            elif user_response['action'] == 'show_new_user_keyboard':
                # Check if user clicked "Request Access" button
                request_access_btn = get_localized_button(update.message.from_user, 'request_access')
                
                if update.message.text == request_access_btn:
                    # User clicked request access - create request
                    await self._create_access_request(update.message.from_user, update.message, saved_message)
                    request_created_msg = get_localized_message(update.message.from_user, 'access_request_created')
                    sent_message = await update.message.reply_text(request_created_msg)
                    
                    # Save outgoing message
                    await self._save_outgoing_message(sent_message, update.message.from_user)
                    logger.info(f"Created access request for user {update.message.from_user.username or update.message.from_user.id}")
                else:
                    # User sent other text - show keyboard again
                    await self._show_new_user_keyboard(update)
                return
            
            elif user_response['action'] == 'pending_request':
                # Show pending request message
                await self._show_pending_request_message(update)
                return
            
            elif user_response['action'] == 'create_request':
                # Create new access request with this message
                await self._create_access_request(update.message.from_user, update.message, saved_message)
                request_created_msg = get_localized_message(update.message.from_user, 'access_request_created')
                sent_message = await update.message.reply_text(
                    request_created_msg
                )
                logger.info(f"Created access request for new user {update.message.from_user.username or update.message.from_user.id}")
                
                # Save outgoing message
                await self._save_outgoing_message(
                    sent_message,
                    update.message.from_user
                )
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _handle_other(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle non-text messages (photos, documents, etc.)"""
        try:
            # Save incoming message
            await self._save_message(update.message, 'incoming')
            
            # Auto-reply with localized message
            message_type = "content"
            if update.message.photo:
                message_type = "photo"
            elif update.message.document:
                message_type = "document"
            elif update.message.voice:
                message_type = "voice"
            elif update.message.video:
                message_type = "video"
            
            # Get localized content type name
            language = get_user_language(update.message.from_user)
            localized_type = MessageLocalizer.get_content_type_name(message_type, language)
            
            reply_text = get_localized_message(
                update.message.from_user, 
                'received_content', 
                message_type=localized_type
            )
            sent_message = await update.message.reply_text(reply_text)
            
            # Save outgoing message
            await self._save_outgoing_message(
                sent_message,
                update.message.from_user
            )
            
            logger.info(f"Handled {message_type} from {update.message.from_user.username or update.message.from_user.id}")
            
        except Exception as e:
            logger.error(f"Error handling non-text message: {e}")
    
    async def _save_message(self, message, direction='incoming'):
        """Save message to database"""
        try:
            # Prepare message text
            message_text = message.text or message.caption or ""
            
            # Handle different message types
            if message.photo:
                message_text = f"[Photo] {message_text}"
            elif message.document:
                message_text = f"[Document: {message.document.file_name}] {message_text}"
            elif message.voice:
                message_text = f"[Voice message] {message_text}"
            elif message.video:
                message_text = f"[Video] {message_text}"
            elif message.sticker:
                message_text = f"[Sticker: {message.sticker.emoji or 'no emoji'}]"
            
            # Convert message to dict for raw_data
            raw_data = message.to_dict() if hasattr(message, 'to_dict') else {}
            
            # Get user language and create database record
            user_language = get_user_language(message.from_user)
            telegram_message = await sync_to_async(TelegramMessage.objects.create)(
                direction=direction,
                telegram_user_id=message.from_user.id,
                telegram_username=message.from_user.username or "",
                telegram_first_name=message.from_user.first_name or "",
                telegram_last_name=message.from_user.last_name or "",
                chat_id=message.chat_id,
                message_id=message.message_id,
                message_text=message_text,
                raw_data=raw_data,
                user_language=user_language
            )
            
            logger.debug(f"Saved {direction} message from {message.from_user.id}")
            return telegram_message
            
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            return None
    
    async def _save_outgoing_message(self, message, to_user):
        """Save outgoing message to database"""
        try:
            raw_data = message.to_dict() if hasattr(message, 'to_dict') else {}
            user_language = get_user_language(to_user)
            
            await sync_to_async(TelegramMessage.objects.create)(
                direction='outgoing',
                telegram_user_id=to_user.id,
                telegram_username=to_user.username or "",
                telegram_first_name=to_user.first_name or "",
                telegram_last_name=to_user.last_name or "",
                chat_id=message.chat_id,
                message_id=message.message_id,
                message_text=message.text,
                raw_data=raw_data,
                user_language=user_language
            )
            
            logger.debug(f"Saved outgoing message to {to_user.id}")
            
        except Exception as e:
            logger.error(f"Error saving outgoing message: {e}")
    
    async def _check_user_access(self, telegram_user):
        """Check if user exists or has pending request, or can be linked by username"""
        from vpn.models import User
        
        try:
            # Check if user already exists by telegram_user_id
            user = await sync_to_async(User.objects.filter(telegram_user_id=telegram_user.id).first)()
            if user:
                return {'action': 'existing_user', 'user': user}
            
            # Check if user can be linked by telegram username
            if telegram_user.username:
                # Look for existing user with matching telegram_username (case-insensitive)
                existing_user_by_username = await sync_to_async(
                    User.objects.filter(
                        telegram_username__iexact=telegram_user.username,
                        telegram_user_id__isnull=True  # Not yet linked to Telegram
                    ).first
                )()
                
                if existing_user_by_username:
                    # Link this telegram account to existing user
                    await self._link_telegram_to_user(existing_user_by_username, telegram_user)
                    return {'action': 'existing_user', 'user': existing_user_by_username}
            
            # Check if this telegram_user_id was previously linked to a user but is now unlinked
            # This handles the case where an admin "untied" the user from Telegram
            unlinked_user = await sync_to_async(
                User.objects.filter(
                    telegram_username__iexact=telegram_user.username if telegram_user.username else '',
                    telegram_user_id__isnull=True
                ).first
            )() if telegram_user.username else None
            
            # Check if user has pending access request
            existing_request = await sync_to_async(
                AccessRequest.objects.filter(telegram_user_id=telegram_user.id).first
            )()
            
            if existing_request:
                if existing_request.approved:
                    # Check if there was an approved request but user was unlinked
                    # In this case, allow creating a new request (treat as new user)
                    if unlinked_user:
                        # Delete old request since user was unlinked
                        await sync_to_async(existing_request.delete)()
                        logger.info(f"Deleted old approved request for unlinked user @{telegram_user.username}")
                        return {'action': 'show_new_user_keyboard'}
                    else:
                        # Request approved but user not created yet (shouldn't happen but handle gracefully)
                        return {'action': 'show_new_user_keyboard'}
                else:
                    # Check if user was unlinked after making the request
                    if unlinked_user:
                        # Delete old pending request and allow new one
                        await sync_to_async(existing_request.delete)()
                        logger.info(f"Deleted old pending request for unlinked user @{telegram_user.username}")
                        return {'action': 'show_new_user_keyboard'}
                    else:
                        # Request pending
                        return {'action': 'pending_request'}
            
            # No user and no request - new user
            return {'action': 'show_new_user_keyboard'}
            
        except Exception as e:
            logger.error(f"Error checking user access: {e}")
            # Default to new user keyboard if check fails
            return {'action': 'show_new_user_keyboard'}
    
    async def _handle_access_command(self, update: Update, user):
        """Handle Access button - show subscription groups keyboard"""
        try:
            # Import Xray models
            from vpn.models_xray import UserSubscription
            from telegram import ReplyKeyboardMarkup, KeyboardButton
            
            # Get user's active subscription groups
            subscriptions = await sync_to_async(
                lambda: list(
                    UserSubscription.objects.filter(
                        user=user, 
                        active=True,
                        subscription_group__is_active=True
                    ).select_related('subscription_group')
                )
            )()
            
            if subscriptions:
                # Create keyboard with subscription groups using localized buttons
                keyboard = []
                
                # Get localized button texts
                all_in_one_btn = get_localized_button(update.message.from_user, 'all_in_one')
                group_prefix = get_localized_button(update.message.from_user, 'group_prefix')
                back_btn = get_localized_button(update.message.from_user, 'back')
                
                # Add All-in-one button first
                keyboard.append([KeyboardButton(all_in_one_btn)])
                
                # Add individual group buttons in 2 columns
                group_buttons = []
                for sub in subscriptions:
                    group_name = sub.subscription_group.name
                    group_buttons.append(KeyboardButton(f"{group_prefix}{group_name}"))
                
                # Arrange buttons in 2 columns
                for i in range(0, len(group_buttons), 2):
                    if i + 1 < len(group_buttons):
                        # Two buttons in a row
                        keyboard.append([group_buttons[i], group_buttons[i + 1]])
                    else:
                        # One button in the last row
                        keyboard.append([group_buttons[i]])
                
                # Add back button
                keyboard.append([KeyboardButton(back_btn)])
                
                reply_markup = ReplyKeyboardMarkup(
                    keyboard, 
                    resize_keyboard=True,
                    one_time_keyboard=False
                )
                
                # Send message with keyboard using localized text
                choose_text = get_localized_message(update.message.from_user, 'choose_subscription')
                all_in_one_desc = get_localized_message(update.message.from_user, 'all_in_one_desc')
                group_desc = get_localized_message(update.message.from_user, 'group_desc')
                select_option = get_localized_message(update.message.from_user, 'select_option')
                
                message_text = f"{choose_text}\n\n"
                message_text += f"{all_in_one_desc}\n"
                message_text += f"{group_desc}\n\n"
                message_text += select_option
                
                sent_message = await update.message.reply_text(
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                # No active subscriptions - show main keyboard
                access_button = get_localized_button(update.message.from_user, 'access')
                keyboard = [
                    [KeyboardButton(access_button)],
                ]
                reply_markup = ReplyKeyboardMarkup(
                    keyboard, 
                    resize_keyboard=True,
                    one_time_keyboard=False
                )
                
                no_subs_msg = get_localized_message(update.message.from_user, 'no_subscriptions')
                sent_message = await update.message.reply_text(
                    no_subs_msg,
                    reply_markup=reply_markup
                )
            
            # Save outgoing message
            await self._save_outgoing_message(
                sent_message,
                update.message.from_user
            )
            
            logger.info(f"Showed subscription groups keyboard to user {user.username}")
            
        except Exception as e:
            logger.error(f"Error handling Access command: {e}")
            error_msg = get_localized_message(update.message.from_user, 'error_loading_subscriptions')
            await update.message.reply_text(error_msg)
    
    async def _create_access_request(self, telegram_user, message, saved_message=None):
        """Create new access request"""
        try:
            # Check if request already exists (safety check)
            existing = await sync_to_async(
                AccessRequest.objects.filter(telegram_user_id=telegram_user.id).first
            )()
            
            if existing and not existing.approved:
                logger.warning(f"Access request already exists for user {telegram_user.id}")
                return existing
            
            # Create new request with default username from Telegram and user language
            default_username = telegram_user.username or ""
            user_language = get_user_language(telegram_user)
            request = await sync_to_async(AccessRequest.objects.create)(
                telegram_user_id=telegram_user.id,
                telegram_username=telegram_user.username or "",
                telegram_first_name=telegram_user.first_name or "",
                telegram_last_name=telegram_user.last_name or "",
                message_text=message.text or message.caption or "[Non-text message]",
                chat_id=message.chat_id,
                first_message=saved_message,
                desired_username=default_username,
                user_language=user_language
            )
            
            logger.info(f"Created access request for user {telegram_user.username or telegram_user.id}")
            return request
            
        except Exception as e:
            logger.error(f"Error creating access request: {e}")
            return None
    
    async def _send_help_message(self, update: Update):
        """Send help message for unrecognized commands"""
        try:
            # Create main keyboard for existing users with localized buttons
            from telegram import ReplyKeyboardMarkup, KeyboardButton
            access_button = get_localized_button(update.message.from_user, 'access')
            keyboard = [
                [KeyboardButton(access_button)],
            ]
            reply_markup = ReplyKeyboardMarkup(
                keyboard, 
                resize_keyboard=True,
                one_time_keyboard=False
            )
            
            help_text = get_localized_message(update.message.from_user, 'help_text')
            sent_message = await update.message.reply_text(
                help_text,
                reply_markup=reply_markup
            )
            
            # Save outgoing message
            await self._save_outgoing_message(
                sent_message,
                update.message.from_user
            )
            
        except Exception as e:
            logger.error(f"Error sending help message: {e}")
    
    async def _handle_group_selection(self, update: Update, user, group_name):
        """Handle specific group selection"""
        try:
            from django.conf import settings
            
            # Get the base URL for subscription links from settings
            base_url = getattr(settings, 'EXTERNAL_ADDRESS', 'https://your-server.com')
            
            # Parse base_url to ensure it has https:// scheme
            if not base_url.startswith(('http://', 'https://')):
                base_url = f"https://{base_url}"
            
            # Generate group-specific subscription link
            subscription_link = f"{base_url}/xray/{user.hash}?group={group_name}"
            
            # Also generate user portal link
            portal_link = f"{base_url}/u/{user.hash}"
            
            # Build localized message
            group_title = get_localized_message(update.message.from_user, 'group_subscription', group_name=group_name)
            sub_link_label = get_localized_message(update.message.from_user, 'subscription_link')
            portal_label = get_localized_message(update.message.from_user, 'web_portal')
            tap_note = get_localized_message(update.message.from_user, 'tap_to_copy')
            
            message_text = f"{group_title}\n\n"
            message_text += f"{sub_link_label}\n"
            message_text += f"`{subscription_link}`\n\n"
            message_text += f"{portal_label}\n"
            message_text += f"{portal_link}\n\n"
            message_text += tap_note
            
            # Create back navigation keyboard with only back button
            from telegram import ReplyKeyboardMarkup, KeyboardButton
            back_btn = get_localized_button(update.message.from_user, 'back')
            keyboard = [
                [KeyboardButton(back_btn)],
            ]
            reply_markup = ReplyKeyboardMarkup(
                keyboard, 
                resize_keyboard=True,
                one_time_keyboard=False
            )
            
            sent_message = await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            # Save outgoing message
            await self._save_outgoing_message(
                sent_message,
                update.message.from_user
            )
            
            logger.info(f"Sent group {group_name} subscription to user {user.username}")
            
        except Exception as e:
            logger.error(f"Error handling group selection: {e}")
            error_msg = get_localized_message(update.message.from_user, 'error_loading_group')
            await update.message.reply_text(error_msg)
    
    async def _handle_all_in_one(self, update: Update, user):
        """Handle All-in-one selection"""
        try:
            # Import Xray models
            from vpn.models_xray import UserSubscription, ServerInbound
            from django.conf import settings
            
            # Get user's active subscription groups
            subscriptions = await sync_to_async(
                lambda: list(
                    UserSubscription.objects.filter(
                        user=user, 
                        active=True,
                        subscription_group__is_active=True
                    ).select_related('subscription_group').prefetch_related('subscription_group__inbounds')
                )
            )()
            
            if subscriptions:
                # Get the base URL for subscription links from settings
                base_url = getattr(settings, 'EXTERNAL_ADDRESS', 'https://your-server.com')
                
                # Parse base_url to ensure it has https:// scheme
                if not base_url.startswith(('http://', 'https://')):
                    base_url = f"https://{base_url}"
                
                # Generate universal subscription link
                subscription_link = f"{base_url}/xray/{user.hash}"
                
                # Also generate user portal link
                portal_link = f"{base_url}/u/{user.hash}"
                
                # Build message with detailed server/subscription list using localized text
                all_in_one_title = get_localized_message(update.message.from_user, 'all_in_one_subscription')
                access_includes = get_localized_message(update.message.from_user, 'your_access_includes')
                message_text = f"{all_in_one_title}\n\n"
                message_text += f"{access_includes}\n\n"
                
                # Collect all servers and their subscriptions
                servers_data = {}
                
                for sub in subscriptions:
                    group = sub.subscription_group
                    group_name = group.name
                    
                    # Get servers where this group's inbounds are deployed
                    deployed_servers = await sync_to_async(
                        lambda: list(
                            ServerInbound.objects.filter(
                                inbound__in=group.inbounds.all(),
                                active=True
                            ).select_related('server', 'inbound').values_list(
                                'server__name', 'inbound__name', 'inbound__protocol'
                            ).distinct()
                        )
                    )()
                    
                    # Group by server
                    for server_name, inbound_name, protocol in deployed_servers:
                        if server_name not in servers_data:
                            servers_data[server_name] = []
                        servers_data[server_name].append({
                            'group_name': group_name,
                            'inbound_name': inbound_name,
                            'protocol': protocol.upper()
                        })
                
                # Display servers and their subscriptions
                for server_name, server_subscriptions in servers_data.items():
                    message_text += f"🔒 **{server_name}**\n"
                    
                    for sub_data in server_subscriptions:
                        message_text += f"   • {sub_data['group_name']} ({sub_data['protocol']})\n"
                    
                    message_text += "\n"
                
                # Add subscription link with localized labels
                universal_link_label = get_localized_message(update.message.from_user, 'universal_subscription_link')
                portal_label = get_localized_message(update.message.from_user, 'web_portal')
                all_subs_note = get_localized_message(update.message.from_user, 'all_subscriptions_note')
                
                message_text += f"{universal_link_label}\n"
                message_text += f"`{subscription_link}`\n\n"
                
                # Add portal link
                message_text += f"{portal_label}\n"
                message_text += f"{portal_link}\n\n"
                
                message_text += all_subs_note
                
                # Create back navigation keyboard with only back button
                from telegram import ReplyKeyboardMarkup, KeyboardButton
                back_btn = get_localized_button(update.message.from_user, 'back')
                keyboard = [
                    [KeyboardButton(back_btn)],
                ]
                reply_markup = ReplyKeyboardMarkup(
                    keyboard, 
                    resize_keyboard=True,
                    one_time_keyboard=False
                )
                
                sent_message = await update.message.reply_text(
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                # No active subscriptions
                no_subs_msg = get_localized_message(update.message.from_user, 'no_subscriptions')
                sent_message = await update.message.reply_text(no_subs_msg)
            
            # Save outgoing message
            await self._save_outgoing_message(
                sent_message,
                update.message.from_user
            )
            
            logger.info(f"Sent all-in-one subscription to user {user.username}")
            
        except Exception as e:
            logger.error(f"Error handling all-in-one selection: {e}")
            error_msg = get_localized_message(update.message.from_user, 'error_loading_subscriptions')
            await update.message.reply_text(error_msg)
    
    async def _handle_back_to_main(self, update: Update, user):
        """Handle back button - return to main menu"""
        try:
            from telegram import ReplyKeyboardMarkup, KeyboardButton
            
            # Create main keyboard with localized buttons
            access_btn = get_localized_button(update.message.from_user, 'access')
            keyboard = [
                [KeyboardButton(access_btn)],
            ]
            reply_markup = ReplyKeyboardMarkup(
                keyboard, 
                resize_keyboard=True,
                one_time_keyboard=False
            )
            
            help_text = get_localized_message(update.message.from_user, 'help_text')
            sent_message = await update.message.reply_text(
                help_text,
                reply_markup=reply_markup
            )
            
            # Save outgoing message
            await self._save_outgoing_message(
                sent_message,
                update.message.from_user
            )
            
            logger.info(f"Returned user {user.username} to main menu")
            
        except Exception as e:
            logger.error(f"Error handling back button: {e}")
            await self._send_help_message(update)
    
    async def _show_new_user_keyboard(self, update: Update):
        """Show keyboard with request access button for new users"""
        try:
            from telegram import ReplyKeyboardMarkup, KeyboardButton
            
            # Get localized button and message
            request_access_btn = get_localized_button(update.message.from_user, 'request_access')
            welcome_msg = get_localized_message(update.message.from_user, 'new_user_welcome')
            
            # Create keyboard with request access button
            keyboard = [
                [KeyboardButton(request_access_btn)],
            ]
            reply_markup = ReplyKeyboardMarkup(
                keyboard, 
                resize_keyboard=True,
                one_time_keyboard=False
            )
            
            sent_message = await update.message.reply_text(
                welcome_msg,
                reply_markup=reply_markup
            )
            
            # Save outgoing message
            await self._save_outgoing_message(
                sent_message,
                update.message.from_user
            )
            
            logger.info(f"Showed new user keyboard to {update.message.from_user.username or update.message.from_user.id}")
            
        except Exception as e:
            logger.error(f"Error showing new user keyboard: {e}")
    
    async def _show_pending_request_message(self, update: Update, custom_message: str = None):
        """Show pending request message to users with pending access requests"""
        try:
            # Use custom message or default pending message
            if custom_message:
                message_text = custom_message
            else:
                message_text = get_localized_message(update.message.from_user, 'pending_request_msg')
            
            sent_message = await update.message.reply_text(message_text)
            
            # Save outgoing message
            await self._save_outgoing_message(
                sent_message,
                update.message.from_user
            )
            
            logger.info(f"Showed pending request message to {update.message.from_user.username or update.message.from_user.id}")
            
        except Exception as e:
            logger.error(f"Error showing pending request message: {e}")
    
    async def _link_telegram_to_user(self, user, telegram_user):
        """Link Telegram account to existing VPN user"""
        try:
            user.telegram_user_id = telegram_user.id
            user.telegram_username = telegram_user.username or ""
            user.telegram_first_name = telegram_user.first_name or ""
            user.telegram_last_name = telegram_user.last_name or ""
            
            await sync_to_async(user.save)()
            
            logger.info(f"Linked Telegram user @{telegram_user.username} (ID: {telegram_user.id}) to existing VPN user {user.username}")
            
        except Exception as e:
            logger.error(f"Error linking Telegram to user: {e}")
            raise
    
    def _sync_status_on_startup(self):
        """No database status to sync - only lock file matters"""
        pass
    
    def auto_start_if_enabled(self):
        """Auto-start bot if enabled in settings"""
        try:
            bot_settings = BotSettings.get_settings()
            if bot_settings.enabled and bot_settings.bot_token and not self._running:
                logger.info("Auto-starting bot (enabled in settings)")
                self.start()
                return True
            else:
                if not bot_settings.enabled:
                    logger.info("Bot auto-start skipped: disabled in settings")
                elif not bot_settings.bot_token:
                    logger.info("Bot auto-start skipped: no token configured")
                elif self._running:
                    logger.info("Bot auto-start skipped: already running")
        except Exception as e:
            # Don't log as error if it's just a lock conflict
            if "could not acquire lock" in str(e).lower():
                logger.info(f"Bot auto-start skipped: {e}")
            else:
                logger.error(f"Failed to auto-start bot: {e}")
        return False
    
    @property
    def is_running(self):
        """Check if bot is running"""
        return self._running and self._bot_thread and self._bot_thread.is_alive()
