from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile, generated_user_phone


@receiver(post_save, sender=get_user_model())
def ensure_user_profile(sender, instance, created, **kwargs):
    if not created:
        return
    UserProfile.objects.get_or_create(
        user=instance,
        defaults={"phone": generated_user_phone(instance.pk)},
    )
