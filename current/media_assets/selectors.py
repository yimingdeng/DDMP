from django.db.models import Prefetch

from .models import MediaAsset, MediaType


def public_media_prefetch(to_attr="public_media"):
    return Prefetch(
        "media_assets",
        queryset=MediaAsset.published.order_by("sort_order", "created_at"),
        to_attr=to_attr,
    )


def decorate_with_media(target):
    assets = list(getattr(target, "public_media", []))
    target.cover_media = next(
        (asset for asset in assets if asset.is_cover and asset.display_image),
        next((asset for asset in assets if asset.display_image), None),
    )
    target.gallery_images = [asset for asset in assets if asset.media_type == MediaType.IMAGE]
    target.video_links = [
        asset
        for asset in assets
        if asset.media_type in {MediaType.VIDEO_LINK, MediaType.LOCAL_VIDEO}
    ]
    return target
