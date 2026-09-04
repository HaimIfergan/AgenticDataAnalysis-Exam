import os
from celery import Celery

# Récupération de l'URL Redis depuis l'environnement ou valeur par défaut
redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "worker",
    broker=redis_url,
    backend=redis_url
)

celery_app.conf.update(
    task_track_started=True,
    result_backend=redis_url,
)
