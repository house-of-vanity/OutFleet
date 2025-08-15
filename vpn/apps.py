from django.apps import AppConfig
from django.contrib.auth import get_user_model

class VPN(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vpn'
    
    def ready(self):
        """Import signals when Django starts"""
        import sys
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"VPN App ready() called in process: {' '.join(sys.argv)}")
        
        try:
            import vpn.signals  # noqa
        except ImportError:
            pass
        
        # Only load admin interfaces in web processes, not in worker/beat
        skip_admin_load = any([
            'worker' in sys.argv,
            'beat' in sys.argv,
            'makemigrations' in sys.argv,
            'migrate' in sys.argv,
            'shell' in sys.argv,
            'test' in sys.argv,
        ])
        
        if not skip_admin_load:
            logger.info("VPN App: Loading admin interfaces in web process")
            # Force load admin interfaces first
            self._load_admin_interfaces()
            
            # Clean up unwanted admin interfaces
            self._cleanup_admin_interfaces()
        else:
            logger.info("VPN App: Skipping admin loading in non-web process")
    
    def _cleanup_admin_interfaces(self):
        """Remove unwanted admin interfaces after all apps are loaded"""
        from django.contrib import admin
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("VPN App: Starting admin cleanup...")
        
        try:
            from django_celery_results.models import GroupResult
            from django_celery_beat.models import (
                PeriodicTask, 
                ClockedSchedule, 
                CrontabSchedule, 
                IntervalSchedule, 
                SolarSchedule
            )
            from django.contrib.auth.models import Group
            
            # Unregister celery models that we don't want in admin
            models_to_unregister = [
                GroupResult, PeriodicTask, ClockedSchedule, 
                CrontabSchedule, IntervalSchedule, SolarSchedule
            ]
            
            for model in models_to_unregister:
                try:
                    admin.site.unregister(model)
                    logger.info(f"VPN App: Unregistered {model.__name__}")
                except admin.sites.NotRegistered:
                    logger.debug(f"VPN App: {model.__name__} was not registered, skipping")
            
            # Unregister Django's default Group model
            try:
                admin.site.unregister(Group)
                logger.info("VPN App: Unregistered Django Group model")
            except admin.sites.NotRegistered:
                logger.debug("VPN App: Django Group was not registered, skipping")
                
        except ImportError as e:
            # Celery packages not installed
            logger.warning(f"VPN App: Celery packages not available: {e}")
        
        logger.info("VPN App: Admin cleanup completed")
    
    def _load_admin_interfaces(self):
        """Force load admin interfaces to ensure they are registered"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("VPN App: Force loading admin interfaces...")
        
        try:
            # Import admin module to trigger registration
            import sys
            if 'vpn.admin_minimal' in sys.modules:
                # Module already imported, remove it to force fresh import
                del sys.modules['vpn.admin_minimal']
                logger.info("VPN App: Removed vpn.admin_minimal from cache")
            
            import vpn.admin_minimal
            logger.info("VPN App: Successfully loaded vpn.admin_minimal")
            
        except Exception as e:
            logger.error(f"VPN App: Failed to load vpn.admin: {e}")
            import traceback
            logger.error(f"VPN App: Traceback: {traceback.format_exc()}")
        
        logger.info("VPN App: Admin loading completed")
