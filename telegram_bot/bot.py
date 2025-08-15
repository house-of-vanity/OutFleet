import logging
import threading
import time
import asyncio
import os
import fcntl
from typing import Optional
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
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
    
    async def _is_telegram_admin(self, telegram_user):
        """Check if user is a Telegram admin"""
        try:
            from django.db.models import Q
            bot_settings = await sync_to_async(BotSettings.get_settings)()
            
            # Check by telegram_user_id first
            if hasattr(telegram_user, 'id'):
                telegram_user_id = telegram_user.id
                telegram_username = telegram_user.username if hasattr(telegram_user, 'username') else None
            else:
                # If just an ID was passed
                telegram_user_id = telegram_user
                telegram_username = None
            
            # Check if admin by telegram_user_id
            admin_by_id = await sync_to_async(
                bot_settings.telegram_admins.filter(telegram_user_id=telegram_user_id).exists
            )()
            
            if admin_by_id:
                return True
            
            # Also check by telegram_username if available
            if telegram_username:
                admin_by_username = await sync_to_async(
                    bot_settings.telegram_admins.filter(telegram_username=telegram_username).exists
                )()
                
                if admin_by_username:
                    # Update the user's telegram_user_id for future checks
                    admin_user = await sync_to_async(
                        bot_settings.telegram_admins.filter(telegram_username=telegram_username).first
                    )()
                    if admin_user and not admin_user.telegram_user_id:
                        admin_user.telegram_user_id = telegram_user_id
                        await sync_to_async(admin_user.save)()
                        logger.info(f"Linked telegram_user_id {telegram_user_id} to admin {admin_user.username}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False
    
    async def _notify_admins_new_request(self, access_request):
        """Notify all Telegram admins about new access request"""
        try:
            bot_settings = await sync_to_async(BotSettings.get_settings)()
            admins = await sync_to_async(list)(bot_settings.telegram_admins.all())
            
            if not admins:
                logger.info("No Telegram admins configured, skipping notification")
                return
            
            # Prepare user info
            user_info = access_request.display_name
            telegram_info = f"@{access_request.telegram_username}" if access_request.telegram_username else f"ID: {access_request.telegram_user_id}"
            date = access_request.created_at.strftime("%Y-%m-%d %H:%M")
            message = access_request.message_text[:200] + "..." if len(access_request.message_text) > 200 else access_request.message_text
            
            # Send notification to each admin
            for admin in admins:
                try:
                    if admin.telegram_user_id:
                        # Get admin language (default to English if not set)
                        admin_language = 'ru' if hasattr(admin, 'telegram_user_language') else 'en'
                        
                        notification_text = MessageLocalizer.get_message(
                            'admin_new_request_notification', 
                            admin_language,
                            user_info=user_info,
                            telegram_info=telegram_info,
                            date=date,
                            message=message
                        )
                        
                        await self._send_notification_to_admin(admin.telegram_user_id, notification_text)
                        logger.info(f"Sent new request notification to admin {admin.username}")
                        
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin.username}: {e}")
                    
        except Exception as e:
            logger.error(f"Error notifying admins about new request: {e}")
    
    async def _send_notification_to_admin(self, telegram_user_id, message_text):
        """Send notification message to specific admin"""
        try:
            bot_settings = await sync_to_async(BotSettings.get_settings)()
            if not bot_settings.enabled or not bot_settings.bot_token:
                logger.warning("Bot not configured, skipping admin notification")
                return
            
            # Create a simple Bot instance for sending notification
            from telegram import Bot
            from telegram.request import HTTPXRequest
            
            request_kwargs = {
                'connection_pool_size': 1,
                'read_timeout': bot_settings.connection_timeout,
                'write_timeout': bot_settings.connection_timeout,
                'connect_timeout': bot_settings.connection_timeout,
            }
            
            if bot_settings.use_proxy and bot_settings.proxy_url:
                request_kwargs['proxy'] = bot_settings.proxy_url
            
            request = HTTPXRequest(**request_kwargs)
            bot = Bot(token=bot_settings.bot_token, request=request)
            
            await bot.send_message(
                chat_id=telegram_user_id,
                text=message_text,
                parse_mode='Markdown'
            )
            
            # Clean up bot connection
            try:
                await request.shutdown()
            except:
                pass
                
        except Exception as e:
            logger.error(f"Failed to send notification to admin {telegram_user_id}: {e}")
    
    async def _create_main_keyboard(self, telegram_user):
        """Create main keyboard for existing users, with admin buttons if user is admin"""
        from telegram import ReplyKeyboardMarkup, KeyboardButton
        
        # Get basic buttons
        access_button = get_localized_button(telegram_user, 'access')
        guide_button = get_localized_button(telegram_user, 'guide')
        
        # Check if user is admin
        is_admin = await self._is_telegram_admin(telegram_user)
        
        if is_admin:
            # Admin keyboard with additional admin button
            access_requests_button = get_localized_button(telegram_user, 'access_requests')
            keyboard = [
                [KeyboardButton(access_button), KeyboardButton(guide_button)],
                [KeyboardButton(access_requests_button)]
            ]
        else:
            # Regular user keyboard
            keyboard = [
                [KeyboardButton(access_button), KeyboardButton(guide_button)]
            ]
        
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )
    
    async def _handle_access_requests_command(self, update: Update):
        """Handle access requests button - show pending requests to admin"""
        try:
            # Get pending access requests
            pending_requests = await sync_to_async(list)(
                AccessRequest.objects.filter(approved=False).order_by('-created_at')
            )
            
            if not pending_requests:
                # No pending requests
                no_requests_msg = get_localized_message(update.message.from_user, 'admin_no_pending_requests')
                reply_markup = await self._create_main_keyboard(update.message.from_user)
                
                sent_message = await update.message.reply_text(
                    no_requests_msg,
                    reply_markup=reply_markup
                )
                
                await self._save_outgoing_message(sent_message, update.message.from_user)
                return
            
            # Show pending requests with inline keyboards for approve/reject
            title_msg = get_localized_message(update.message.from_user, 'admin_access_requests_title')
            
            # Send title message with main keyboard 
            reply_markup = await self._create_main_keyboard(update.message.from_user)
            title_sent = await update.message.reply_text(
                title_msg,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            await self._save_outgoing_message(title_sent, update.message.from_user)
            
            # Send each request with inline keyboard for actions
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            
            for request in pending_requests[:5]:  # Show max 5 requests
                # Format request info
                user_info = request.display_name
                date = request.created_at.strftime("%Y-%m-%d %H:%M")
                message_preview = request.message_text[:100] + "..." if len(request.message_text) > 100 else request.message_text
                
                request_text = get_localized_message(
                    update.message.from_user, 
                    'admin_request_item',
                    user_info=user_info,
                    date=date,
                    message_preview=message_preview
                )
                
                # Create inline keyboard for this request
                approve_btn_text = get_localized_button(update.message.from_user, 'approve')
                reject_btn_text = get_localized_button(update.message.from_user, 'reject')
                details_btn_text = get_localized_button(update.message.from_user, 'details')
                
                inline_keyboard = [
                    [
                        InlineKeyboardButton(approve_btn_text, callback_data=f"approve_{request.id}"),
                        InlineKeyboardButton(reject_btn_text, callback_data=f"reject_{request.id}")
                    ],
                    [InlineKeyboardButton(details_btn_text, callback_data=f"details_{request.id}")]
                ]
                inline_markup = InlineKeyboardMarkup(inline_keyboard)
                
                request_sent = await update.message.reply_text(
                    request_text,
                    reply_markup=inline_markup,
                    parse_mode='Markdown'
                )
                await self._save_outgoing_message(request_sent, update.message.from_user)
            
            if len(pending_requests) > 5:
                remaining_msg = f"... и еще {len(pending_requests) - 5} заявок" if get_user_language(update.message.from_user) == 'ru' else f"... and {len(pending_requests) - 5} more requests"
                await update.message.reply_text(remaining_msg)
            
            logger.info(f"Showed {len(pending_requests)} pending requests to admin {update.message.from_user.username}")
            
        except Exception as e:
            logger.error(f"Error handling access requests command: {e}")
            error_msg = get_localized_message(update.message.from_user, 'admin_error_processing', error=str(e))
            await update.message.reply_text(error_msg)
    
    async def _handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses (callback queries)"""
        try:
            query = update.callback_query
            await query.answer()  # Acknowledge the callback
            
            # Check if user is admin
            if not await self._is_telegram_admin(query.from_user):
                await query.edit_message_text("❌ Access denied. Admin rights required.")
                return
            
            # Parse callback data
            callback_data = query.data
            action, request_id = callback_data.split('_', 1)
            
            if action == "approve":
                await self._handle_approve_callback(query, request_id)
            elif action == "reject":
                await self._handle_reject_callback(query, request_id)
            elif action == "details":
                await self._handle_details_callback(query, request_id)
            elif action == "sg":  # Subscription group selection
                await self._handle_subscription_group_callback(query, callback_data)
            elif action == "confirm":  # Confirm approval with selected groups
                await self._handle_confirm_approval_callback(query, request_id)
            elif action == "cancel":  # Cancel approval process
                await self._handle_cancel_callback(query, request_id)
            else:
                await query.edit_message_text("❌ Unknown action")
                
        except Exception as e:
            logger.error(f"Error handling callback query: {e}")
            try:
                await query.edit_message_text(f"❌ Error: {str(e)}")
            except:
                pass
    
    async def _handle_approve_callback(self, query, request_id):
        """Handle approve button press - show subscription groups selection"""
        try:
            # Get the request
            request = await sync_to_async(AccessRequest.objects.get)(id=request_id)
            
            # Check if already processed
            if request.approved:
                already_processed_msg = get_localized_message(query.from_user, 'admin_request_already_processed')
                await query.edit_message_text(already_processed_msg)
                return
            
            # Get available subscription groups
            from vpn.models_xray import SubscriptionGroup
            groups = await sync_to_async(list)(
                SubscriptionGroup.objects.filter(is_active=True).order_by('name')
            )
            
            if not groups:
                await query.edit_message_text("❌ No subscription groups available")
                return
            
            # Create inline keyboard with subscription groups
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            
            user_info = request.display_name
            choose_groups_msg = get_localized_message(
                query.from_user, 
                'admin_choose_subscription_groups',
                user_info=user_info
            )
            
            # Create buttons for each group (max 2 per row)
            keyboard = []
            for i in range(0, len(groups), 2):
                row = []
                for j in range(2):
                    if i + j < len(groups):
                        group = groups[i + j]
                        button_text = f"⚪ {group.name}"
                        callback_data = f"sg_toggle_{group.id}_{request_id}"
                        row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
                keyboard.append(row)
            
            # Add confirm and cancel buttons
            confirm_btn_text = get_localized_button(query.from_user, 'confirm_approval')
            cancel_btn_text = get_localized_button(query.from_user, 'cancel')
            
            keyboard.append([
                InlineKeyboardButton(confirm_btn_text, callback_data=f"confirm_{request_id}"),
                InlineKeyboardButton(cancel_btn_text, callback_data=f"cancel_{request_id}")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(choose_groups_msg, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error handling approve callback: {e}")
            error_msg = get_localized_message(query.from_user, 'admin_error_processing', error=str(e))
            await query.edit_message_text(error_msg)
    
    async def _handle_subscription_group_callback(self, query, callback_data):
        """Handle subscription group toggle button"""
        try:
            # Parse callback data: sg_toggle_{group_id}_{request_id}
            parts = callback_data.split('_')
            group_id = parts[2]
            request_id = parts[3]
            
            # Get current message text and keyboard
            current_text = query.message.text
            current_keyboard = query.message.reply_markup.inline_keyboard
            
            # Toggle the group selection
            updated_keyboard = []
            for row in current_keyboard:
                updated_row = []
                for button in row:
                    if button.callback_data and button.callback_data.startswith(f"sg_toggle_{group_id}_"):
                        # Toggle this button
                        if button.text.startswith("⚪"):
                            # Select it
                            new_text = button.text.replace("⚪", "✅")
                        else:
                            # Deselect it
                            new_text = button.text.replace("✅", "⚪")
                        from telegram import InlineKeyboardButton
                        updated_row.append(InlineKeyboardButton(new_text, callback_data=button.callback_data))
                    else:
                        updated_row.append(button)
                updated_keyboard.append(updated_row)
            
            from telegram import InlineKeyboardMarkup
            updated_markup = InlineKeyboardMarkup(updated_keyboard)
            await query.edit_message_reply_markup(reply_markup=updated_markup)
            
        except Exception as e:
            logger.error(f"Error handling subscription group callback: {e}")
    
    async def _handle_confirm_approval_callback(self, query, request_id):
        """Handle confirm approval button - create user and assign groups"""
        try:
            # Get the request
            request = await sync_to_async(AccessRequest.objects.get)(id=request_id)
            
            # Check if already processed
            if request.approved:
                already_processed_msg = get_localized_message(query.from_user, 'admin_request_already_processed')
                await query.edit_message_text(already_processed_msg)
                return
            
            # Get selected groups from the keyboard
            selected_groups = []
            from vpn.models_xray import SubscriptionGroup
            
            logger.info(f"Processing approval for request {request_id}")
            
            for row in query.message.reply_markup.inline_keyboard:
                for button in row:
                    if button.callback_data and button.callback_data.startswith("sg_toggle_"):
                        if button.text.startswith("✅"):
                            # Extract group_id from callback_data
                            group_id = button.callback_data.split('_')[2]
                            logger.info(f"Found selected group with ID {group_id}")
                            try:
                                group = await sync_to_async(SubscriptionGroup.objects.get)(id=group_id)
                                selected_groups.append(group)
                                logger.info(f"Added group '{group.name}' to selected groups")
                            except Exception as e:
                                logger.error(f"Failed to get subscription group {group_id}: {e}")
            
            logger.info(f"Total selected groups: {len(selected_groups)}")
            
            if not selected_groups:
                await query.edit_message_text("❌ Please select at least one subscription group")
                return
            
            # Save selected groups to the request
            await sync_to_async(request.selected_subscription_groups.set)(selected_groups)
            
            try:
                # Create or get user
                from vpn.models import User
                from vpn.models_xray import UserSubscription
                import secrets
                import string
                
                # Check if user already exists
                existing_user = await sync_to_async(
                    User.objects.filter(telegram_user_id=request.telegram_user_id).first
                )()
                
                if existing_user:
                    user = existing_user
                    logger.info(f"Using existing user {user.username} for telegram_user_id {request.telegram_user_id}")
                else:
                    # Check if selected_existing_user is set
                    if request.selected_existing_user:
                        # Link telegram to existing user
                        user = request.selected_existing_user
                        user.telegram_user_id = request.telegram_user_id
                        user.telegram_username = request.telegram_username
                        await sync_to_async(user.save)()
                        logger.info(f"Linked telegram account to existing user {user.username}")
                    else:
                        # Create new user
                        username = request.desired_username or request.telegram_username or f"tg_{request.telegram_user_id}"
                        
                        # Ensure unique username
                        base_username = username
                        counter = 1
                        while await sync_to_async(User.objects.filter(username=username).exists)():
                            username = f"{base_username}_{counter}"
                            counter += 1
                        
                        # Generate random password
                        alphabet = string.ascii_letters + string.digits
                        password = ''.join(secrets.choice(alphabet) for _ in range(16))
                        
                        # Create user
                        user = await sync_to_async(User.objects.create_user)(
                            username=username,
                            password=password,
                            telegram_user_id=request.telegram_user_id,
                            telegram_username=request.telegram_username,
                            first_name=request.telegram_first_name or '',
                            last_name=request.telegram_last_name or '',
                            comment=f"Created from Telegram request #{request.id}"
                        )
                        logger.info(f"Created new user {user.username} from Telegram request")
                
                # Link user to request
                request.user = user
                await sync_to_async(request.save)()
                logger.info(f"Linked user {user.username} (ID: {user.id}) to request {request.id}")
                
                # Assign subscription groups to user
                logger.info(f"Assigning {len(selected_groups)} subscription groups to user {user.username}")
                for subscription_group in selected_groups:
                    try:
                        # Use a more explicit approach for async operations
                        existing_sub = await sync_to_async(
                            UserSubscription.objects.filter(
                                user=user,
                                subscription_group=subscription_group
                            ).first
                        )()
                        
                        if existing_sub:
                            # Update existing subscription
                            if not existing_sub.active:
                                existing_sub.active = True
                                await sync_to_async(existing_sub.save)()
                                logger.info(f"Re-activated subscription group '{subscription_group.name}' for user {user.username}")
                            else:
                                logger.info(f"Subscription group '{subscription_group.name}' already active for user {user.username}")
                        else:
                            # Create new subscription
                            new_sub = await sync_to_async(UserSubscription.objects.create)(
                                user=user,
                                subscription_group=subscription_group,
                                active=True
                            )
                            logger.info(f"Created new subscription for group '{subscription_group.name}' for user {user.username}")
                            
                    except Exception as e:
                        logger.error(f"Error assigning subscription group '{subscription_group.name}' to user {user.username}: {e}")
                
                # Mark as approved
                request.approved = True
                await sync_to_async(request.save)()
                
                # Send success message to admin
                groups_list = ", ".join([group.name for group in selected_groups])
                success_msg = get_localized_message(
                    query.from_user,
                    'admin_approval_success',
                    user_info=request.display_name,
                    groups=groups_list
                )
                await query.edit_message_text(success_msg, parse_mode='Markdown')
                
                # Send approval notification to user
                # Create a dummy user object for localization
                class DummyUser:
                    def __init__(self, lang):
                        self.language_code = lang
                
                user_lang = DummyUser(request.user_language if hasattr(request, 'user_language') else 'en')
                approval_msg = get_localized_message(user_lang, 'approval_notification')
                await self._send_notification_to_admin(request.telegram_user_id, approval_msg)
                
                logger.info(f"Admin {query.from_user.username} approved request {request_id} with {len(selected_groups)} groups")
                
            except Exception as e:
                logger.error(f"Error in approval process: {e}")
                error_msg = get_localized_message(query.from_user, 'admin_error_processing', error=str(e))
                await query.edit_message_text(error_msg)
                
        except Exception as e:
            logger.error(f"Error handling confirm approval callback: {e}")
            error_msg = get_localized_message(query.from_user, 'admin_error_processing', error=str(e))
            await query.edit_message_text(error_msg)
    
    async def _handle_reject_callback(self, query, request_id):
        """Handle reject button press"""
        try:
            # Get the request
            request = await sync_to_async(AccessRequest.objects.get)(id=request_id)
            
            # Check if already processed
            if request.approved:
                already_processed_msg = get_localized_message(query.from_user, 'admin_request_already_processed')
                await query.edit_message_text(already_processed_msg)
                return
            
            # Mark as rejected (we can add a rejected field or just delete)
            await sync_to_async(request.delete)()
            
            # Send success message to admin
            success_msg = get_localized_message(
                query.from_user,
                'admin_rejection_success',
                user_info=request.display_name
            )
            await query.edit_message_text(success_msg, parse_mode='Markdown')
            
            logger.info(f"Admin {query.from_user.username} rejected request {request_id}")
            
        except Exception as e:
            logger.error(f"Error handling reject callback: {e}")
            error_msg = get_localized_message(query.from_user, 'admin_error_processing', error=str(e))
            await query.edit_message_text(error_msg)
    
    async def _handle_details_callback(self, query, request_id):
        """Handle details button press - show full request info"""
        try:
            # Get the request
            request = await sync_to_async(AccessRequest.objects.get)(id=request_id)
            
            # Format detailed information
            details = f"**📋 Request Details**\n\n"
            details += f"**👤 User:** {request.display_name}\n"
            details += f"**📱 Telegram:** @{request.telegram_username}" if request.telegram_username else f"**📱 Telegram ID:** {request.telegram_user_id}\n"
            details += f"**📅 Date:** {request.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            details += f"**🆔 Request ID:** {request.id}\n"
            details += f"**👤 Desired Username:** {request.desired_username}\n\n"
            details += f"**💬 Full Message:**\n{request.message_text}"
            
            # Create back button
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            back_keyboard = [[
                InlineKeyboardButton("⬅️ Back", callback_data=f"approve_{request_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{request_id}")
            ]]
            reply_markup = InlineKeyboardMarkup(back_keyboard)
            
            await query.edit_message_text(details, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error handling details callback: {e}")
            error_msg = get_localized_message(query.from_user, 'admin_error_processing', error=str(e))
            await query.edit_message_text(error_msg)
    
    async def _handle_cancel_callback(self, query, request_id):
        """Handle cancel button press - return to original request view"""
        try:
            # Get the request
            request = await sync_to_async(AccessRequest.objects.get)(id=request_id)
            
            # Recreate original request display
            user_info = request.display_name
            date = request.created_at.strftime("%Y-%m-%d %H:%M")
            message_preview = request.message_text[:100] + "..." if len(request.message_text) > 100 else request.message_text
            
            request_text = get_localized_message(
                query.from_user, 
                'admin_request_item',
                user_info=user_info,
                date=date,
                message_preview=message_preview
            )
            
            # Create original inline keyboard
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            approve_btn_text = get_localized_button(query.from_user, 'approve')
            reject_btn_text = get_localized_button(query.from_user, 'reject')
            details_btn_text = get_localized_button(query.from_user, 'details')
            
            inline_keyboard = [
                [
                    InlineKeyboardButton(approve_btn_text, callback_data=f"approve_{request.id}"),
                    InlineKeyboardButton(reject_btn_text, callback_data=f"reject_{request.id}")
                ],
                [InlineKeyboardButton(details_btn_text, callback_data=f"details_{request.id}")]
            ]
            inline_markup = InlineKeyboardMarkup(inline_keyboard)
            
            await query.edit_message_text(request_text, reply_markup=inline_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error handling cancel callback: {e}")
            error_msg = get_localized_message(query.from_user, 'admin_error_processing', error=str(e))
            await query.edit_message_text(error_msg)

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
            self._application.add_handler(CallbackQueryHandler(self._handle_callback_query))
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
                reply_markup = await self._create_main_keyboard(update.message.from_user)
                
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
                guide_btn = get_localized_button(update.message.from_user, 'guide')
                access_requests_btn = get_localized_button(update.message.from_user, 'access_requests')
                all_in_one_btn = get_localized_button(update.message.from_user, 'all_in_one')
                back_btn = get_localized_button(update.message.from_user, 'back')
                group_prefix = get_localized_button(update.message.from_user, 'group_prefix')
                
                # Check if this is a keyboard command
                if update.message.text == access_btn:
                    await self._handle_access_command(update, user_response['user'])
                elif update.message.text == guide_btn:
                    await self._handle_guide_command(update)
                elif update.message.text == access_requests_btn:
                    # Admin command - check permissions and handle
                    if await self._is_telegram_admin(update.message.from_user):
                        await self._handle_access_requests_command(update)
                    else:
                        await self._send_help_message(update)
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
                elif update.message.text == get_localized_button(update.message.from_user, 'android'):
                    # Handle Android guide
                    await self._handle_android_guide(update)
                elif update.message.text == get_localized_button(update.message.from_user, 'ios'):
                    # Handle iOS guide
                    await self._handle_ios_guide(update)
                elif update.message.text == get_localized_button(update.message.from_user, 'web_portal'):
                    # Handle web portal
                    await self._handle_web_portal(update, user_response['user'])
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
                reply_markup = await self._create_main_keyboard(update.message.from_user)
                
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
            
            # Notify admins about new request
            await self._notify_admins_new_request(request)
            
            return request
            
        except Exception as e:
            logger.error(f"Error creating access request: {e}")
            return None
    
    async def _send_help_message(self, update: Update):
        """Send help message for unrecognized commands"""
        try:
            # Create main keyboard for existing users with localized buttons
            reply_markup = await self._create_main_keyboard(update.message.from_user)
            
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
            
            # Get server information for this group
            from vpn.models_xray import SubscriptionGroup, ServerInbound
            group_servers_info = ""
            try:
                # Find the subscription group by name
                subscription_group = await sync_to_async(
                    SubscriptionGroup.objects.filter(
                        name=group_name,
                        is_active=True
                    ).prefetch_related('inbounds').first
                )()
                
                if subscription_group:
                    # Get servers where this group's inbounds are deployed
                    deployed_servers = await sync_to_async(
                        lambda: list(
                            ServerInbound.objects.filter(
                                inbound__in=subscription_group.inbounds.all(),
                                active=True
                            ).select_related('server', 'inbound').values_list(
                                'server__name', 'inbound__protocol'
                            ).distinct()
                        )
                    )()
                    
                    if deployed_servers:
                        # Group by server
                        servers_data = {}
                        for server_name, protocol in deployed_servers:
                            if server_name not in servers_data:
                                servers_data[server_name] = []
                            if protocol.upper() not in servers_data[server_name]:
                                servers_data[server_name].append(protocol.upper())
                        
                        # Build server info text
                        if servers_data:
                            servers_header = get_localized_message(update.message.from_user, 'servers_in_group')
                            group_servers_info = f"\n{servers_header}\n"
                            for server_name, protocols in servers_data.items():
                                protocols_str = ", ".join(protocols)
                                group_servers_info += f"   • {server_name} ({protocols_str})\n"
                            group_servers_info += "\n"
                            
            except Exception as e:
                logger.warning(f"Could not get server info for group {group_name}: {e}")
            
            # Build localized message
            group_title = get_localized_message(update.message.from_user, 'group_subscription', group_name=group_name)
            sub_link_label = get_localized_message(update.message.from_user, 'subscription_link')
            portal_label = get_localized_message(update.message.from_user, 'web_portal')
            tap_note = get_localized_message(update.message.from_user, 'tap_to_copy')
            
            message_text = f"{group_title}\n"
            message_text += group_servers_info  # Add server info
            message_text += f"{sub_link_label}\n"
            message_text += f"`{subscription_link}`\n\n"
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
            # Create main keyboard with localized buttons
            reply_markup = await self._create_main_keyboard(update.message.from_user)
            
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
    
    async def _handle_guide_command(self, update: Update):
        """Handle guide button - show platform selection"""
        try:
            from telegram import ReplyKeyboardMarkup, KeyboardButton
            
            # Get localized buttons
            android_btn = get_localized_button(update.message.from_user, 'android')
            ios_btn = get_localized_button(update.message.from_user, 'ios')
            web_portal_btn = get_localized_button(update.message.from_user, 'web_portal')
            back_btn = get_localized_button(update.message.from_user, 'back')
            
            # Create platform selection keyboard
            keyboard = [
                [KeyboardButton(android_btn), KeyboardButton(ios_btn)],
                [KeyboardButton(web_portal_btn)],
                [KeyboardButton(back_btn)]
            ]
            reply_markup = ReplyKeyboardMarkup(
                keyboard, 
                resize_keyboard=True,
                one_time_keyboard=False
            )
            
            # Get localized messages
            guide_title = get_localized_message(update.message.from_user, 'guide_title')
            choose_platform = get_localized_message(update.message.from_user, 'guide_choose_platform')
            
            message_text = f"{guide_title}\n\n{choose_platform}"
            
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
            
            logger.info(f"Showed guide platform selection to user")
            
        except Exception as e:
            logger.error(f"Error handling guide command: {e}")
    
    async def _handle_android_guide(self, update: Update):
        """Handle Android guide selection"""
        try:
            from telegram import ReplyKeyboardMarkup, KeyboardButton
            
            # Create back navigation keyboard
            back_btn = get_localized_button(update.message.from_user, 'back')
            keyboard = [
                [KeyboardButton(back_btn)]
            ]
            reply_markup = ReplyKeyboardMarkup(
                keyboard, 
                resize_keyboard=True,
                one_time_keyboard=False
            )
            
            # Get Android guide text
            android_guide = get_localized_message(update.message.from_user, 'android_guide')
            
            sent_message = await update.message.reply_text(
                android_guide,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            # Save outgoing message
            await self._save_outgoing_message(
                sent_message,
                update.message.from_user
            )
            
            logger.info(f"Sent Android guide to user")
            
        except Exception as e:
            logger.error(f"Error handling Android guide: {e}")
    
    async def _handle_ios_guide(self, update: Update):
        """Handle iOS guide selection"""
        try:
            from telegram import ReplyKeyboardMarkup, KeyboardButton
            
            # Create back navigation keyboard
            back_btn = get_localized_button(update.message.from_user, 'back')
            keyboard = [
                [KeyboardButton(back_btn)]
            ]
            reply_markup = ReplyKeyboardMarkup(
                keyboard, 
                resize_keyboard=True,
                one_time_keyboard=False
            )
            
            # Get iOS guide text
            ios_guide = get_localized_message(update.message.from_user, 'ios_guide')
            
            sent_message = await update.message.reply_text(
                ios_guide,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            # Save outgoing message
            await self._save_outgoing_message(
                sent_message,
                update.message.from_user
            )
            
            logger.info(f"Sent iOS guide to user")
            
        except Exception as e:
            logger.error(f"Error handling iOS guide: {e}")
    
    async def _handle_web_portal(self, update: Update, user):
        """Handle web portal button - send portal link"""
        try:
            from django.conf import settings
            from telegram import ReplyKeyboardMarkup, KeyboardButton
            
            # Get the base URL for portal links from settings
            base_url = getattr(settings, 'EXTERNAL_ADDRESS', 'https://your-server.com')
            
            # Parse base_url to ensure it has https:// scheme
            if not base_url.startswith(('http://', 'https://')):
                base_url = f"https://{base_url}"
            
            # Generate user portal link
            portal_link = f"{base_url}/u/{user.hash}"
            
            # Create back navigation keyboard
            back_btn = get_localized_button(update.message.from_user, 'back')
            keyboard = [
                [KeyboardButton(back_btn)]
            ]
            reply_markup = ReplyKeyboardMarkup(
                keyboard, 
                resize_keyboard=True,
                one_time_keyboard=False
            )
            
            # Get localized messages
            portal_label = get_localized_message(update.message.from_user, 'web_portal')
            portal_description = get_localized_message(update.message.from_user, 'web_portal_description')
            
            message_text = f"{portal_label}\n{portal_link}\n\n{portal_description}"
            
            sent_message = await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            # Save outgoing message
            await self._save_outgoing_message(
                sent_message,
                update.message.from_user
            )
            
            logger.info(f"Sent web portal link to user {user.username}")
            
        except Exception as e:
            logger.error(f"Error handling web portal: {e}")
    
    @property
    def is_running(self):
        """Check if bot is running"""
        return self._running and self._bot_thread and self._bot_thread.is_alive()
