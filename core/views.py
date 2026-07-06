import logging

from django.db import connection
from django.db.models import Prefetch
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from media_assets.selectors import decorate_with_media, public_media_prefetch

from .share_meta import build_share_meta
from .wechat import WeChatConfigurationError, build_js_sdk_config, validate_wechat_share_url

logger = logging.getLogger(__name__)


@require_GET
def home(request):
    from sites.models import DemoSite
    from varieties.models import SellingPoint, Variety

    selling_points = SellingPoint.published.order_by("sort_order").prefetch_related(
        public_media_prefetch()
    )
    demo_sites = (
        DemoSite.published.filter(is_featured=True)
        .order_by("sort_order")
        .prefetch_related(public_media_prefetch())
    )
    featured_variety = (
        Variety.published.filter(is_featured=True)
        .prefetch_related(
            public_media_prefetch(),
            Prefetch(
                "selling_points",
                queryset=selling_points,
                to_attr="public_selling_points",
            ),
            Prefetch(
                "demo_sites",
                queryset=demo_sites,
                to_attr="featured_demo_sites",
            ),
        )
        .first()
    )
    hero_media = None
    if featured_variety:
        decorate_with_media(featured_variety)
        hero_media = featured_variety.cover_media
        for point in featured_variety.public_selling_points:
            decorate_with_media(point)
        for site in featured_variety.featured_demo_sites:
            decorate_with_media(site)
    share_meta = build_share_meta(
        request,
        title=featured_variety.name if featured_variety else "",
        description=featured_variety.positioning if featured_variety else "",
        image_url=hero_media.display_image.url if hero_media and hero_media.display_image else "",
    )
    return render(
        request,
        "core/home.html",
        {
            "featured_variety": featured_variety,
            "hero_media": hero_media,
            "share_meta": share_meta,
        },
    )


@never_cache
@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("Health check failed")
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@require_GET
def privacy(request):
    return render(request, "core/privacy.html")


@never_cache
@require_GET
def wechat_js_config(request):
    target_url = request.GET.get("url", "").strip()
    if not target_url:
        return HttpResponseBadRequest("Missing url.")
    if not validate_wechat_share_url(request, target_url):
        return HttpResponseBadRequest("Invalid url.")
    try:
        config = build_js_sdk_config(target_url)
    except WeChatConfigurationError as exc:
        return JsonResponse({"enabled": False, "reason": str(exc)}, status=200)
    return JsonResponse(config)
