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
}


app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

