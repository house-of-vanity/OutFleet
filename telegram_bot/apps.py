from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class TelegramBotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'telegram_bot'
    
    def ready(self):
        """Called when Django starts - attempt to auto-start bot if enabled"""
        import sys
        import os
        
        # Skip auto-start in various scenarios
        skip_conditions = [
            # Management commands
            'migrate' in sys.argv,
            'makemigrations' in sys.argv,
            'collectstatic' in sys.argv,
            'shell' in sys.argv,
            'test' in sys.argv,
            # Celery processes
            'celery' in sys.argv,
            'worker' in sys.argv,
            'beat' in sys.argv,
            # Environment variables that indicate worker/beat processes
            os.environ.get('CELERY_WORKER_NAME'),
            os.environ.get('CELERY_BEAT'),
            # Process name detection
            any('celery' in arg.lower() for arg in sys.argv),
            any('worker' in arg.lower() for arg in sys.argv),
            any('beat' in arg.lower() for arg in sys.argv),
        ]
        
        if any(skip_conditions):
            logger.info(f"Skipping Telegram bot auto-start in process: {' '.join(sys.argv)}")
            return
            
        # Additional process detection by checking if we're in main process
        try:
            # Check if this is the main Django process (not a worker)
            current_process = os.environ.get('DJANGO_SETTINGS_MODULE')
            if not current_process:
                logger.info("Skipping bot auto-start: not in main Django process")
                return
        except:
            pass
            
        # Delay import to avoid circular imports
        try:
            from .bot import TelegramBotManager
            import threading
            import time
            
            def delayed_autostart():
                # Wait a bit for Django to fully initialize
                time.sleep(2)
                try:
                    manager = TelegramBotManager()
                    if manager.auto_start_if_enabled():
                        logger.info("Telegram bot auto-started successfully")
                    else:
                        logger.info("Telegram bot auto-start skipped (disabled or already running)")
                except Exception as e:
                    logger.error(f"Failed to auto-start Telegram bot: {e}")
            
            logger.info("Starting Telegram bot auto-start thread")
            # Start in background thread to not block Django startup
            thread = threading.Thread(target=delayed_autostart, daemon=True)
            thread.start()
            
        except Exception as e:
            logger.error(f"Error setting up Telegram bot auto-start: {e}")
