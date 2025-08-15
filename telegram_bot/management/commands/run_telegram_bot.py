import logging
import signal
import sys
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from telegram_bot.models import BotSettings, BotStatus
from telegram_bot.bot import TelegramBotManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run the Telegram bot'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot_manager = None
        self.running = False
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force start even if bot is disabled in settings',
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Check settings
        settings = BotSettings.get_settings()
        
        if not settings.bot_token:
            self.stdout.write(
                self.style.ERROR('Bot token is not configured. Please configure it in the admin panel.')
            )
            return
        
        if not settings.enabled and not options['force']:
            self.stdout.write(
                self.style.WARNING('Bot is disabled in settings. Use --force to override.')
            )
            return
        
        # Initialize bot manager
        self.bot_manager = TelegramBotManager()
        
        try:
            # Start the bot
            self.stdout.write(self.style.SUCCESS('Starting Telegram bot...'))
            self.bot_manager.start()
            self.running = True
            
            self.stdout.write(
                self.style.SUCCESS(f'Bot is running. Press Ctrl+C to stop.')
            )
            
            # Keep the main thread alive
            while self.running:
                time.sleep(1)
                
                # Check if bot is still running
                if not self.bot_manager.is_running:
                    self.stdout.write(
                        self.style.ERROR('Bot stopped unexpectedly. Check logs for errors.')
                    )
                    break
        
        except KeyboardInterrupt:
            self.stdout.write('\nReceived interrupt signal...')
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error running bot: {e}')
            )
            logger.error(f'Error running bot: {e}', exc_info=True)
            
            # Update status
            status = BotStatus.get_status()
            status.is_running = False
            status.last_error = str(e)
            status.last_stopped = timezone.now()
            status.save()
        
        finally:
            # Stop the bot
            if self.bot_manager:
                self.stdout.write('Stopping bot...')
                self.bot_manager.stop()
                self.stdout.write(self.style.SUCCESS('Bot stopped.'))
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.stdout.write('\nShutting down gracefully...')
        self.running = False