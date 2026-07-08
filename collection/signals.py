from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PublishedObservation
from .services import advance_site_current_stage


@receiver(post_save, sender=PublishedObservation)
def advance_site_stage_after_publication(sender, instance, **kwargs):
    del sender, kwargs
    advance_site_current_stage(instance.observation.site_id, instance.observation.stage)
