import os
from celery import Celery


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

app = Celery('app')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

# Celery Beat schedule - periodic tasks
app.conf.beat_schedule = {
    'process-pending-batches-every-5-minutes': {
        'task': 'core.tasks.process_pending_batches',
        'schedule': 300.0,
        'options': {
            'expires': 290.0,
        }
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')