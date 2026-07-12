from urllib.parse import urlsplit

from django.contrib import messages
from django.core.cache import cache
from django.core.signing import salted_hmac
from django.db import IntegrityError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.models import SiteConfiguration
from sites.models import DemoSite, VisitingStatus
from varieties.models import Variety

from .forms import InquiryForm
from .models import Inquiry, InquiryIntent


def _rate_limited(request):
    window = 10 * 60
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key
    ip_hash = salted_hmac("inquiry-ip", request.META.get("REMOTE_ADDR", "unknown")).hexdigest()[:24]
    keys = ((f"inquiry:session:{session_key}", 5), (f"inquiry:ip:{ip_hash}", 20))
    limited = False
    for key, limit in keys:
        value = cache.get(key, 0)
        if value >= limit:
            limited = True
        elif value == 0:
            cache.set(key, 1, window)
        else:
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, value + 1, window)
    return limited


def _remember_safe_values(request):
    allowed = (
        "name",
        "phone",
        "area_name",
        "organization",
        "message",
        "customer_identity",
        "intent_type",
    )
    request.session["inquiry_form_values"] = {
        key: request.POST.get(key, "")[:500] for key in allowed
    }


def _safe_return_path(request):
    candidate = request.POST.get("next", "")
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        parsed = urlsplit(candidate)
        return parsed.path or reverse("core:home")
    return reverse("core:home")


@require_POST
def submit_inquiry(request):
    return_path = _safe_return_path(request)
    if _rate_limited(request):
        _remember_safe_values(request)
        messages.error(request, "提交过于频繁，请十分钟后再试；已填写内容已为您保留。")
        return redirect(f"{return_path}#contact")
    form = InquiryForm(request.POST)
    if form.is_valid():
        from campaigns.models import MarketingPackage, PromotionIdentity, TrackedLink

        submission_key = str(form.cleaned_data["submission_key"])
        if Inquiry.objects.filter(submission_key=submission_key).exists():
            messages.info(request, "该咨询已经提交，无需重复操作。")
            return redirect(f"{return_path}#contact")

        inquiry = form.save(commit=False)
        variety_id = form.cleaned_data.get("variety_id")
        site_id = form.cleaned_data.get("site_id")
        variety = Variety.published.filter(pk=variety_id).first() if variety_id else None
        demo_site = (
            DemoSite.published.filter(pk=site_id, variety__status="published")
            .select_related("variety")
            .first()
            if site_id
            else None
        )
        if demo_site:
            variety = demo_site.variety
        if (
            inquiry.intent_type == InquiryIntent.SITE_VISIT
            and demo_site
            and demo_site.visiting_status != VisitingStatus.OPEN
        ):
            _remember_safe_values(request)
            messages.error(request, "该示范点当前未开放看田预约，请选择其他咨询类型。")
            return redirect(f"{return_path}#contact")

        configuration = SiteConfiguration.load()
        inquiry.variety = variety
        inquiry.demo_site = demo_site
        inquiry.source_code = getattr(request, "campaign_source", "direct")
        inquiry.source_path = (getattr(request, "campaign_landing_path", "") or return_path)[:300]
        inquiry.marketing_package = (
            MarketingPackage.objects.select_related(
                "published_observation__observation__site__variety"
            )
            .filter(
                pk=getattr(request, "campaign_package_id", None),
                status__in=("ready", "published"),
            )
            .first()
        )
        if inquiry.marketing_package and not inquiry.marketing_package.is_publicly_available():
            inquiry.marketing_package = None
        inquiry.promotion_identity = PromotionIdentity.objects.filter(
            pk=getattr(request, "campaign_promoter_id", None), is_active=True
        ).first()
        inquiry.tracked_link = TrackedLink.objects.filter(
            pk=getattr(request, "campaign_tracked_link_id", None), is_active=True
        ).first()
        inquiry.submission_key = submission_key
        inquiry.privacy_version = configuration.privacy_version
        inquiry.consent_at = timezone.now()
        inquiry.full_clean()
        try:
            inquiry.save()
        except IntegrityError:
            messages.info(request, "该咨询已经提交，无需重复操作。")
        else:
            messages.success(request, "咨询信息已提交，区域负责人会尽快与您联系。")
    else:
        _remember_safe_values(request)
        messages.error(request, "提交失败，请检查姓名、联系电话、所在区域和同意选项。")
    return redirect(f"{return_path}#contact")
