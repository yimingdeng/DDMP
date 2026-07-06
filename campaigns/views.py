import ipaddress
from urllib.parse import urljoin, urlsplit

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.models import SiteConfiguration

from .models import ChannelQRCode
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
        ChannelQRCode.objects.select_related("variety", "demo_site__variety"),
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
