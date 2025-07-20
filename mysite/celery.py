import logging
import os

from celery import Celery
from celery import shared_task
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
logger = logging.getLogger(__name__)
app = Celery('mysite')

app.conf.beat_schedule = {
    'periodical_servers_sync': {
        'task': 'sync_all_servers',
        'schedule': crontab(minute='*'),
    },
    'cleanup_old_task_logs': {
        'task': 'cleanup_task_logs',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}


app.config_from_object('django.conf:settings', namespace='CELERY')

# Additional celery settings for better logging and performance
app.conf.update(
    # Keep detailed results for debugging
    result_expires=3600,  # 1 hour
    task_always_eager=False,
    task_eager_propagates=True,
    # Improve task tracking
    task_track_started=True,
    task_send_sent_event=True,
    # Clean up settings
    result_backend_cleanup_interval=300,  # Clean up every 5 minutes
)

app.autodiscover_tasks()

