from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render

from core.share_meta import build_share_meta
from media_assets.selectors import decorate_with_media, public_media_prefetch
from sites.models import DemoSite

from .models import SellingPoint, Variety


def variety_detail(request, slug):
    selling_point_queryset = SellingPoint.published.order_by("sort_order").prefetch_related(
        public_media_prefetch()
    )
    demo_site_queryset = DemoSite.published.order_by("sort_order", "name").prefetch_related(
        public_media_prefetch()
    )
    variety = get_object_or_404(
        Variety.published.prefetch_related(
            public_media_prefetch(),
            Prefetch("selling_points", queryset=selling_point_queryset, to_attr="public_points"),
            Prefetch("demo_sites", queryset=demo_site_queryset, to_attr="public_sites"),
        ),
        slug=slug,
    )
    decorate_with_media(variety)
    selling_points = variety.public_points
    demo_sites = variety.public_sites
    for point in selling_points:
        decorate_with_media(point)
    for site in demo_sites:
        decorate_with_media(site)
    cover_media_id = (
        variety.cover_media.pk if variety.cover_media and variety.cover_media.is_cover else None
    )
    gallery_images = [media for media in variety.gallery_images if media.pk != cover_media_id]
    video_links = [media for media in variety.video_links if media.pk != cover_media_id]
    return render(
        request,
        "varieties/detail.html",
        {
            "variety": variety,
            "selling_points": selling_points,
            "demo_sites": demo_sites,
            # The cover is already the first, largest visual and should not be repeated below.
            "gallery_images": gallery_images,
            "video_links": video_links,
            "share_meta": build_share_meta(
                request,
                title=variety.name,
                description=variety.positioning or variety.summary,
                image_url=(
                    variety.cover_media.display_image.url
                    if variety.cover_media and variety.cover_media.display_image
                    else ""
                ),
            ),
        },
    )


def selling_point_detail(request, variety_slug, slug):
    selling_point = get_object_or_404(
        SellingPoint.published.select_related("variety").prefetch_related(public_media_prefetch()),
        variety__slug=variety_slug,
        variety__status="published",
        slug=slug,
    )
    decorate_with_media(selling_point)
    return render(
        request,
        "varieties/selling_point_detail.html",
        {
            "point": selling_point,
            "gallery_images": selling_point.gallery_images,
            "video_links": selling_point.video_links,
            "share_meta": build_share_meta(
                request,
                title=f"{selling_point.title}｜{selling_point.variety.name}",
                description=selling_point.short_description,
                image_url=(
                    selling_point.cover_media.display_image.url
                    if selling_point.cover_media and selling_point.cover_media.display_image
                    else ""
                ),
            ),
        },
    )
