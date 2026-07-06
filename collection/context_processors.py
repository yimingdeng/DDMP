from .models import CollectionReviewer


def collection_role(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"can_review_collection": False}
    return {
        "can_review_collection": user.is_superuser
        or CollectionReviewer.objects.filter(user=user, is_active=True).exists()
    }
