from math import asin, cos, radians, sin, sqrt
from uuid import UUID

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from core.models import SiteConfiguration
from core.share_meta import build_share_meta
from media_assets.selectors import decorate_with_media, public_media_prefetch

from .models import DemoSite, GrowthStage, Region


def _decorate_public_snapshot(snapshot):
    from collection.forms import ObservationForm

    form = ObservationForm(stage=snapshot.observation.stage, initial=snapshot.public_data)
    snapshot.display_rows = form.display_rows()
    snapshot.key_display_rows = form.key_display_rows()
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
    return snapshot


def _distance_km(latitude, longitude, site):
    if site.latitude is None or site.longitude is None:
        return None
    start_latitude = radians(latitude)
    end_latitude = radians(float(site.latitude))
    latitude_delta = radians(float(site.latitude) - latitude)
    longitude_delta = radians(float(site.longitude) - longitude)
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(start_latitude) * cos(end_latitude) * sin(longitude_delta / 2) ** 2
    )
    return 6371 * 2 * asin(sqrt(haversine))


def _decorate_site_stage_previews(sites):
    from collection.models import PublishedObservation

    stage_rank = {stage: index for index, (stage, _label) in enumerate(GrowthStage.choices)}
    snapshots = (
        PublishedObservation.objects.filter(observation__site__in=sites)
        .select_related("observation", "observation__site")
        .prefetch_related("observation__photos")
        .order_by("-version")
    )
    latest_by_site = {}
    for snapshot in snapshots:
        current = latest_by_site.get(snapshot.observation.site_id)
        if current is None or stage_rank.get(snapshot.observation.stage, -1) > stage_rank.get(
            current.observation.stage, -1
        ):
            latest_by_site[snapshot.observation.site_id] = snapshot
    for site in sites:
        snapshot = latest_by_site.get(site.pk)
        site.stage_preview_snapshot = snapshot
        site.stage_preview_photo = None
        if snapshot:
            for photo in snapshot.observation.photos.all():
                if photo.uploaded_at <= snapshot.published_at:
                    site.stage_preview_photo = photo
                    break
        site.heat_score = getattr(site, "published_stage_count", 0) * 10 + getattr(
            site, "inquiry_count", 0
        )
    return sites


def site_list(request):
    from varieties.models import Variety

    configuration = SiteConfiguration.load()
    sites = (
        DemoSite.published.select_related("variety")
        .filter(variety__status="published")
        .annotate(
            published_stage_count=Count("observations__published_versions", distinct=True),
            inquiry_count=Count("inquiries", distinct=True),
        )
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
    selected_sort = "distance"
    sites = sites.order_by("sort_order", "name")

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
    user_latitude = request.GET.get("lat")
    user_longitude = request.GET.get("lng")
    has_distance_location = False
    if user_latitude and user_longitude:
        try:
            latitude = float(user_latitude)
            longitude = float(user_longitude)
        except ValueError:
            pass
        else:
            has_distance_location = True
            for site in sites:
                site.distance_km = _distance_km(latitude, longitude, site)
            sites.sort(
                key=lambda item: (
                    item.distance_km is None,
                    item.distance_km if item.distance_km is not None else 10**9,
                    item.sort_order,
                    item.name,
                )
            )
    _decorate_site_stage_previews(sites)
    for site in sites:
        decorate_with_media(site)
        site.primary_card_image_url = ""
        site.primary_card_image_alt = f"{site.name}阶段照片"
        if site.stage_preview_photo:
            site.primary_card_image_url = site.stage_preview_photo.image.url
            site.primary_card_image_alt = site.stage_preview_photo.caption or f"{site.name}阶段照片"
        elif site.cover_media and site.cover_media.display_image:
            site.primary_card_image_url = site.cover_media.display_image.url
            site.primary_card_image_alt = site.cover_media.alt_text
    map_sites = [
        {
            "name": site.name,
            "latitude": float(site.latitude),
            "longitude": float(site.longitude),
            "url": site.get_absolute_url(),
            "stage": site.get_current_stage_display() or "",
            "image": site.primary_card_image_url,
            "heat": site.heat_score,
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
            "selected_sort": selected_sort,
            "has_distance_location": has_distance_location,
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
        _decorate_public_snapshot(snapshot)
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


def stage_detail(request, slug, stage, content_token=None):
    from campaigns.models import (
        ExternalPublicationStatus,
        MarketingPackage,
        MarketingPackageStatus,
        TrackedLink,
    )
    from collection.models import PublishedObservation

    valid_stages = {value for value, _label in GrowthStage.choices}
    if stage not in valid_stages:
        from django.http import Http404

        raise Http404("阶段不存在")
    site = get_object_or_404(
        DemoSite.published.select_related("variety"),
        slug=slug,
        variety__status="published",
    )
    snapshots = (
        PublishedObservation.objects.filter(observation__site=site, observation__stage=stage)
        .select_related("observation", "observation__site", "observation__site__variety")
        .prefetch_related("observation__photos", "observation__videos")
    )
    package = None
    if content_token:
        package = get_object_or_404(
            MarketingPackage.objects.select_related(
                "published_observation__observation__site__variety"
            ),
            public_token=content_token,
            status__in=(MarketingPackageStatus.READY, MarketingPackageStatus.PUBLISHED),
            published_observation__observation__site=site,
            published_observation__observation__stage=stage,
        )
        snapshot = get_object_or_404(snapshots, pk=package.published_observation_id)
    else:
        snapshot = get_object_or_404(snapshots.order_by("-version"))
        try:
            package = snapshot.marketing_package
        except MarketingPackage.DoesNotExist:
            package = None
    _decorate_public_snapshot(snapshot)
    image_url = ""
    if package and package.video_cover:
        image_url = package.video_cover.url
    elif snapshot.public_photos:
        image_url = snapshot.public_photos[0].image.url
    stage_label = snapshot.observation.get_stage_display()
    external_publications = []
    if package:
        external_publications = package.external_publications.filter(
            status=ExternalPublicationStatus.PUBLISHED,
            external_url__gt="",
        )
    share_url = ""
    share_token = request.GET.get("share")
    if package and share_token:
        try:
            UUID(str(share_token))
        except (TypeError, ValueError):
            share_token = ""
        if share_token:
            tracked_link = TrackedLink.objects.filter(
                token=share_token,
                marketing_package=package,
                is_active=True,
            ).first()
            if tracked_link:
                share_url = tracked_link.get_share_path()
    return render(
        request,
        "sites/stage_detail.html",
        {
            "site": site,
            "snapshot": snapshot,
            "marketing_package": package,
            "external_publications": external_publications,
            "share_meta": build_share_meta(
                request,
                title=(
                    package.headline
                    if package
                    else f"{site.variety.name}{site.name}{stage_label}表现"
                ),
                description=snapshot.public_summary or site.main_performance,
                image_url=image_url,
                url=share_url,
            ),
        },
    )
