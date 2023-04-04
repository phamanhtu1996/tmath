import logging
import socket
import os

from celery import Celery
from celery.signals import task_failure

app = Celery('dmoj')

# from django.conf import settings  # noqa: E402, I202, django must be imported here
# app.config_from_object(settings, namespace='CELERY')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dmoj.settings')

# settings.configure()

app.conf.broker_url = 'redis://localhost:6379'
app.conf.result_backend = 'redis://localhost:6379'

# if hasattr(settings, 'CELERY_BROKER_URL_SECRET'):
#     app.conf.broker_url = settings.CELERY_BROKER_URL_SECRET
# if hasattr(settings, 'CELERY_RESULT_BACKEND_SECRET'):
#     app.conf.result_backend = settings.CELERY_RESULT_BACKEND_SECRET

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Logger to enable errors be reported.
logger = logging.getLogger('judge.celery')


@task_failure.connect()
def celery_failure_log(sender, task_id, exception, traceback, *args, **kwargs):
    logger.error('Celery Task %s: %s on %s', sender.name, task_id, socket.gethostname(),  # noqa: G201
                 exc_info=(type(exception), exception, traceback))
