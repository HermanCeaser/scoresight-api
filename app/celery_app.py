from celery import Celery
import os
import logging

from .deps import get_settings

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger.info("=== INITIALIZING CELERY APP ===")

settings = get_settings()
logger.info(f"Settings loaded: {list(settings.dict().keys())}")
logger.info(f"Celery broker URL: {settings.CELERY_BROKER_URL}")
logger.info(f"Celery result backend: {settings.CELERY_RESULT_BACKEND}")

celery_app = Celery(
    "scoresight",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['app.tasks']  # Include tasks module
)

logger.info("Celery app created successfully")

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

logger.info("Celery configuration updated")
logger.info("=== CELERY APP INITIALIZATION COMPLETE ===")