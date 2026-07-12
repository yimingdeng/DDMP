import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from collection.models import PublishedObservation

from .services import ensure_marketing_package, generate_marketing_images

logger = logging.getLogger(__name__)


@receiver(post_save, sender=PublishedObservation)
def create_marketing_package(sender, instance, created, **kwargs):
    if not created:
        return

    def generate():
        try:
            package = ensure_marketing_package(instance)
            generate_marketing_images(package)
        except Exception:
            logger.exception("Failed to generate marketing package for snapshot %s", instance.pk)

    transaction.on_commit(generate)
