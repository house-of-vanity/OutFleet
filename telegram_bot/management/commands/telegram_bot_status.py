import logging
import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from telegram_bot.models import BotSettings, BotStatus
from telegram_bot.bot import TelegramBotManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check Telegram bot status and optionally start it'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--auto-start',
            action='store_true',
            help='Automatically start bot if enabled in settings',
        )
        parser.add_argument(
            '--sync-status',
            action='store_true',
            help='Sync database status with real bot state',
        )
    
    def handle(self, *args, **options):
        """Check bot status"""
        try:
            manager = TelegramBotManager()
            settings = BotSettings.get_settings()
            status = BotStatus.get_status()
            
            # Show current configuration
            self.stdout.write(f"Bot Configuration:")
            self.stdout.write(f"  Enabled: {settings.enabled}")
            self.stdout.write(f"  Token configured: {'Yes' if settings.bot_token else 'No'}")
            
            # Show status
            real_running = manager.is_running
            db_running = status.is_running
            
            self.stdout.write(f"\nBot Status:")
            self.stdout.write(f"  Database status: {'Running' if db_running else 'Stopped'}")
            self.stdout.write(f"  Real status: {'Running' if real_running else 'Stopped'}")
            
            # Check lock file status
            from django.conf import settings as django_settings
            lock_dir = os.path.join(getattr(django_settings, 'BASE_DIR', '/tmp'), 'telegram_bot_locks')
            lock_path = os.path.join(lock_dir, 'telegram_bot.lock')
            
            if os.path.exists(lock_path):
                try:
                    with open(lock_path, 'r') as f:
                        lock_pid = f.read().strip()
                    self.stdout.write(f"  Lock file: exists (PID: {lock_pid})")
                except:
                    self.stdout.write(f"  Lock file: exists (unreadable)")
            else:
                self.stdout.write(f"  Lock file: not found")
            
            if db_running != real_running:
                self.stdout.write(
                    self.style.WARNING("⚠️ Status mismatch detected!")
                )
                
                if options['sync_status']:
                    status.is_running = real_running
                    if not real_running:
                        status.last_stopped = timezone.now()
                    status.save()
                    self.stdout.write(
                        self.style.SUCCESS("✅ Status synchronized")
                    )
            
            # Show timestamps
            if status.last_started:
                self.stdout.write(f"  Last started: {status.last_started}")
            if status.last_stopped:
                self.stdout.write(f"  Last stopped: {status.last_stopped}")
            if status.last_error:
                self.stdout.write(f"  Last error: {status.last_error}")
            
            # Auto-start if requested
            if options['auto_start']:
                if not real_running and settings.enabled and settings.bot_token:
                    self.stdout.write("\nAttempting to start bot...")
                    try:
                        manager.start()
                        self.stdout.write(
                            self.style.SUCCESS("✅ Bot started successfully")
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"❌ Failed to start bot: {e}")
                        )
                elif real_running:
                    self.stdout.write(
                        self.style.SUCCESS("✅ Bot is already running")
                    )
                elif not settings.enabled:
                    self.stdout.write(
                        self.style.WARNING("⚠️ Bot is disabled in settings")
                    )
                elif not settings.bot_token:
                    self.stdout.write(
                        self.style.ERROR("❌ Bot token not configured")
                    )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error checking bot status: {e}")
            )