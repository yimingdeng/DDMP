from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import MediaAsset


@receiver(post_delete, sender=MediaAsset)
def delete_media_files(sender, instance, **kwargs):
    del sender, kwargs
    for field in (instance.image, instance.video_file, instance.video_cover, instance.thumbnail):
        if field and field.name:
            field.storage.delete(field.name)
