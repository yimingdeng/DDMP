from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from core.models import SiteConfiguration
from core.share_meta import build_share_meta
from media_assets.selectors import decorate_with_media, public_media_prefetch

from .models import DemoSite, GrowthStage, Region


def site_list(request):
    from varieties.models import Variety

    configuration = SiteConfiguration.load()
    sites = (
        DemoSite.published.select_related("variety")
        .filter(variety__status="published")
        .prefetch_related(public_media_prefetch())
    )
    selected_region = request.GET.get("region", Region.HUANG_HUAI_HAI)
    selected_province = request.GET.get("province", "").strip()[:50]

    valid_regions = {value for value, _ in Region.choices}
    if selected_region in valid_regions:
        sites = sites.filter(region=selected_region)
    elif "region" in request.GET and selected_region == "":
        selected_region = ""
    else:
        selected_region = Region.HUANG_HUAI_HAI
        sites = sites.filter(region=selected_region)
    if selected_province:
        sites = sites.filter(province=selected_province)

    province_sites = DemoSite.published.filter(variety__status="published")
    if selected_region:
        province_sites = province_sites.filter(region=selected_region)
    provinces = (
        province_sites.exclude(province="")
        .order_by("province")
        .values_list("province", flat=True)
        .distinct()
    )
    sites = list(sites)
    for site in sites:
        decorate_with_media(site)
    map_sites = [
        {
            "name": site.name,
            "latitude": float(site.latitude),
            "longitude": float(site.longitude),
            "url": site.get_absolute_url(),
        }
        for site in sites
        if site.latitude is not None and site.longitude is not None
    ]
    return render(
        request,
        "sites/list.html",
        {
            "sites": sites,
            "regions": Region.choices,
            "provinces": provinces,
            "selected_region": selected_region,
            "selected_province": selected_province,
            "filters_active": (selected_region != Region.HUANG_HUAI_HAI or bool(selected_province)),
            "map_sites": map_sites,
            "missing_coordinate_count": len(sites) - len(map_sites),
            "amap_config": {
                "key": configuration.amap_js_api_key,
                "securityCode": configuration.amap_security_code,
            },
            "featured_variety": Variety.published.filter(is_featured=True).first(),
        },
    )


def site_detail(request, slug):
    from collection.forms import ObservationForm
    from collection.models import PublishedObservation

    site = get_object_or_404(
        DemoSite.published.select_related("variety").prefetch_related(
            "contacts", public_media_prefetch()
        ),
        slug=slug,
        variety__status="published",
    )
    public_contacts = site.contacts.filter(is_active=True).filter(
        Q(show_name=True) | Q(show_phone=True)
    )
    decorate_with_media(site)
    snapshots = (
        PublishedObservation.objects.filter(observation__site=site)
        .select_related("observation")
        .prefetch_related("observation__photos", "observation__videos")
    )
    latest_by_stage = {}
    for snapshot in snapshots.order_by("-version"):
        if snapshot.observation.stage not in latest_by_stage:
            form = ObservationForm(stage=snapshot.observation.stage, initial=snapshot.public_data)
            snapshot.display_rows = form.display_rows()
            latest_by_stage[snapshot.observation.stage] = snapshot
    stage_rank = {stage: index for index, (stage, _label) in enumerate(GrowthStage.choices)}
    published_observations = sorted(
        latest_by_stage.values(),
        key=lambda snapshot: stage_rank.get(snapshot.observation.stage, -1),
        reverse=True,
    )
    for snapshot in published_observations:
        snapshot.public_photos = [
            photo
            for photo in snapshot.observation.photos.all()
            if photo.uploaded_at <= snapshot.published_at
        ]
        snapshot.public_videos = [
            video
            for video in snapshot.observation.videos.all()
            if video.uploaded_at <= snapshot.published_at
        ]
    return render(
        request,
        "sites/detail.html",
        {
            "site": site,
            "public_contacts": public_contacts,
            "gallery_images": site.gallery_images,
            "video_links": site.video_links,
            "published_observations": published_observations,
            "share_meta": build_share_meta(
                request,
                title=f"{site.name}｜{site.variety.name}",
                description=site.main_performance,
                image_url=(
                    site.cover_media.display_image.url
                    if site.cover_media and site.cover_media.display_image
                    else ""
                ),
            ),
        },
    )
