import ipaddress
from urllib.parse import urlencode, urljoin, urlsplit

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.models import SiteConfiguration
from core.share_meta import build_share_meta

from .models import ChannelQRCode, TrackedLink
from .qr import render_qr_png


def is_local_or_private_netloc(netloc):
    host = netloc.rsplit("@", 1)[-1].split(":", 1)[0].strip("[]").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local


def build_public_base_url(request, configured_base_url):
    request_base_url = request.build_absolute_uri("/")
    request_netloc = urlsplit(request_base_url).netloc
    if not configured_base_url:
        return request_base_url

    configured_netloc = urlsplit(configured_base_url).netloc
    if is_local_or_private_netloc(configured_netloc) and not is_local_or_private_netloc(
        request_netloc
    ):
        return request_base_url
    return f"{configured_base_url.rstrip('/')}/"


def build_scan_url(request, qr_code):
    configuration = SiteConfiguration.load()
    public_base_url = build_public_base_url(request, configuration.public_base_url)
    return urljoin(public_base_url, qr_code.get_scan_path().lstrip("/"))


@require_GET
def scan_redirect(request, token):
    qr_code = get_object_or_404(
        ChannelQRCode.objects.select_related(
            "variety",
            "demo_site__variety",
            "published_observation__observation__site__variety",
        ),
        token=token,
    )
    if not qr_code.is_active:
        messages.warning(request, "该二维码已停用，已为您返回平台首页。")
        return redirect("core:home")
    if not qr_code.target_is_available():
        messages.warning(request, "该内容暂不可用，已为您返回平台首页。")
        return redirect(f"/?source={qr_code.source_code}")

    ChannelQRCode.objects.filter(pk=qr_code.pk).update(
        scan_count=F("scan_count") + 1,
        last_scanned_at=timezone.now(),
    )
    return redirect(qr_code.get_target_url())


@require_GET
def tracked_link_redirect(request, token):
    tracked_link = get_object_or_404(
        TrackedLink.objects.select_related(
            "marketing_package__published_observation__observation__site__variety",
            "promoter",
        ),
        token=token,
    )
    package = tracked_link.marketing_package
    if not tracked_link.is_active or not package.is_publicly_available():
        messages.warning(request, "该传播内容暂不可用，已为您返回平台首页。")
        return redirect("core:home")
    TrackedLink.objects.filter(pk=tracked_link.pk).update(
        click_count=F("click_count") + 1,
        last_clicked_at=timezone.now(),
    )
    request.session["campaign_source"] = tracked_link.source_code
    request.session["campaign_landing_path"] = package.get_absolute_url()
    request.session["campaign_package_id"] = package.pk
    request.session["campaign_promoter_id"] = tracked_link.promoter_id
    request.session["campaign_tracked_link_id"] = tracked_link.pk
    redirect_url = f"{package.get_absolute_url()}?{urlencode({'share': str(tracked_link.token)})}"
    snapshot = package.published_observation
    observation = snapshot.observation
    image_url = package.video_cover.url if package.video_cover else ""
    if not image_url:
        first_photo = observation.photos.order_by("uploaded_at", "id").first()
        if first_photo:
            image_url = first_photo.image.url
    return render(
        request,
        "campaigns/tracked_link_landing.html",
        {
            "package": package,
            "redirect_url": redirect_url,
            "share_meta": build_share_meta(
                request,
                title=package.headline,
                description=snapshot.public_summary or observation.site.main_performance,
                image_url=image_url,
                url=tracked_link.get_share_path(),
            ),
        },
    )


@staff_member_required
@require_GET
def qr_png(request, pk):
    qr_code = get_object_or_404(ChannelQRCode, pk=pk)
    scan_url = build_scan_url(request, qr_code)
    response = HttpResponse(render_qr_png(scan_url), content_type="image/png")
    disposition = "attachment" if request.GET.get("download") == "1" else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="{qr_code.source_code}-qr.png"'
    response["Cache-Control"] = "private, no-store"
    return response
