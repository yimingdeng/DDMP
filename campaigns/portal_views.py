import uuid
from datetime import timedelta
from io import BytesIO
from urllib.parse import urlencode, urljoin
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Count
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models import PublicationStatus, SiteConfiguration
from sites.models import GrowthStage, Region

from .forms import ExternalPublicationForm, MarketingAuthenticationForm, ShareLinkForm
from .models import (
    ExternalPublication,
    ExternalPublicationStatus,
    MarketingPackage,
    MarketingPackageStatus,
    PosterVariantType,
    PromotionIdentity,
    TrackedLink,
    get_distribution_channel_label,
    get_distribution_channel_label_map,
)
from .qr import render_qr_png
from .services import (
    build_marketing_kpis,
    ensure_base_poster_variants,
    ensure_short_video_topics,
    generate_poster_variant,
    get_or_create_weekly_report,
)
from .views import build_public_base_url

MARKETING_LOGOUT_REDIRECT_KEY = "marketing_logout_redirect_url"


def _is_home_entry(request):
    next_url = request.GET.get("next", "")
    return request.GET.get("entry") == "home" or "entry=home" in next_url


class MarketingLoginView(LoginView):
    template_name = "campaigns/login.html"
    authentication_form = MarketingAuthenticationForm

    def dispatch(self, request, *args, **kwargs):
        if request.method == "GET":
            request.session[MARKETING_LOGOUT_REDIRECT_KEY] = (
                reverse("core:home") if _is_home_entry(request) else reverse("marketing:login")
            )
        return super().dispatch(request, *args, **kwargs)


@require_POST
def marketing_logout(request):
    redirect_url = request.session.get(MARKETING_LOGOUT_REDIRECT_KEY) or reverse("marketing:login")
    logout(request)
    return redirect(redirect_url)


def _user_identity(user):
    return PromotionIdentity.objects.filter(user=user, is_active=True).first()


def _can_access(user):
    return bool(
        user.is_superuser
        or user.has_perm("campaigns.view_marketingpackage")
        or _user_identity(user)
    )


def _package_queryset(user):
    queryset = MarketingPackage.objects.select_related(
        "published_observation__observation__site__variety"
    ).filter(
        published_observation__observation__site__status=PublicationStatus.PUBLISHED,
        published_observation__observation__site__variety__status=PublicationStatus.PUBLISHED,
    )
    if user.is_superuser or user.has_perm("campaigns.change_marketingpackage"):
        return queryset
    return queryset.filter(
        status__in=(MarketingPackageStatus.READY, MarketingPackageStatus.PUBLISHED)
    )


def _admin_marketing_user(user):
    return bool(user.is_superuser or user.has_perm("campaigns.change_marketingpackage"))


def _authorized_link(user, package, token):
    try:
        token = uuid.UUID(str(token))
    except (ValueError, TypeError, AttributeError):
        return None
    link = (
        TrackedLink.objects.select_related("promoter")
        .filter(token=token, marketing_package=package)
        .first()
    )
    if not link:
        return None
    if user.is_superuser or user.has_perm("campaigns.change_trackedlink"):
        return link
    identity = _user_identity(user)
    if not identity or link.promoter_id != identity.pk:
        return None
    return link


def _absolute_tracked_url(request, link):
    configuration = SiteConfiguration.load()
    base_url = build_public_base_url(request, configuration.public_base_url)
    return urljoin(base_url, link.get_share_path().lstrip("/"))


def _deny_unless_allowed(request):
    if not _can_access(request.user):
        logout(request)
        messages.warning(request, "当前账号没有营销发布权限，请使用已开通营销权限的账号登录。")
        login_url = reverse("marketing:login")
        return redirect(f"{login_url}?{urlencode({'next': request.get_full_path()})}")
    return None


@login_required(login_url="marketing:login")
@require_GET
def dashboard(request):
    denied = _deny_unless_allowed(request)
    if denied:
        return denied
    if request.GET.get("entry") == "home":
        request.session[MARKETING_LOGOUT_REDIRECT_KEY] = reverse("core:home")
    packages = _package_queryset(request.user)
    selected_stage = request.GET.get("stage", "")
    selected_region = request.GET.get("region", "")
    selected_status = request.GET.get("status", "")
    query = request.GET.get("q", "").strip()[:100]
    if selected_stage in {value for value, _label in GrowthStage.choices}:
        packages = packages.filter(published_observation__observation__stage=selected_stage)
    else:
        selected_stage = ""
    if selected_region in {value for value, _label in Region.choices}:
        packages = packages.filter(published_observation__observation__site__region=selected_region)
    else:
        selected_region = ""
    valid_statuses = {value for value, _label in MarketingPackageStatus.choices}
    if selected_status in valid_statuses:
        packages = packages.filter(status=selected_status)
    else:
        selected_status = ""
    if query:
        from django.db.models import Q

        packages = packages.filter(
            Q(headline__icontains=query)
            | Q(published_observation__observation__site__name__icontains=query)
            | Q(published_observation__observation__site__variety__name__icontains=query)
        )
    return render(
        request,
        "campaigns/dashboard.html",
        {
            "packages": packages[:100],
            "stages": GrowthStage.choices,
            "regions": Region.choices,
            "statuses": MarketingPackageStatus.choices,
            "selected_stage": selected_stage,
            "selected_region": selected_region,
            "selected_status": selected_status,
            "query": query,
            "promotion_identity": _user_identity(request.user),
        },
    )


@login_required(login_url="marketing:login")
@require_GET
def package_detail(request, token):
    denied = _deny_unless_allowed(request)
    if denied:
        return denied
    package = get_object_or_404(_package_queryset(request.user), public_token=token)
    selected_link = None
    link_token = request.GET.get("link", "")
    if link_token:
        selected_link = _authorized_link(request.user, package, link_token)
    share_url = _absolute_tracked_url(request, selected_link) if selected_link else ""
    ensure_short_video_topics(package)
    ensure_base_poster_variants(package)
    dealer_variant = None
    if selected_link and selected_link.promoter:
        dealer_variant = generate_poster_variant(
            package,
            PosterVariantType.DEALER,
            tracked_link=selected_link,
            promoter=selected_link.promoter,
            target_url=share_url,
        )
    link_form_initial = {}
    if selected_link:
        link_form_initial = {
            "channel": selected_link.source_code,
            "promoter": selected_link.promoter_id,
        }
    return render(
        request,
        "campaigns/package_detail.html",
        {
            "package": package,
            "observation": package.observation,
            "link_form": ShareLinkForm(user=request.user, initial=link_form_initial),
            "publication_form": ExternalPublicationForm(
                initial={"title": package.douyin_title or package.headline}
            ),
            "selected_link": selected_link,
            "share_url": share_url,
            "channel_label": (
                get_distribution_channel_label(selected_link.source_code) if selected_link else ""
            ),
            "can_publish": package.is_publicly_available(),
            "short_video_topics": package.short_video_topics.filter(is_active=True),
            "external_publications": package.external_publications.all()[:20],
            "poster_variants": package.poster_variants.filter(
                is_active=True,
                tracked_link__isnull=True,
            ),
            "dealer_variant": dealer_variant,
        },
    )


@login_required(login_url="marketing:login")
@require_POST
def add_publication(request, token):
    denied = _deny_unless_allowed(request)
    if denied:
        return denied
    package = get_object_or_404(_package_queryset(request.user), public_token=token)
    form = ExternalPublicationForm(request.POST)
    if form.is_valid():
        publication = form.save(commit=False)
        publication.marketing_package = package
        publication.created_by = request.user
        publication.save()
        messages.success(request, "外部发布记录已保存；带外部链接的记录会在客户页展示。")
    else:
        messages.error(request, "外部发布记录未保存，请检查发布时间、外部链接和指标数字。")
    return redirect("marketing:package-detail", token=package.public_token)


@login_required(login_url="marketing:login")
@require_GET
def stats_dashboard(request):
    denied = _deny_unless_allowed(request)
    if denied:
        return denied
    if not _admin_marketing_user(request.user):
        return HttpResponseForbidden("营销统计看板仅对管理员和运营账号开放。")
    today = timezone.localdate()
    start_date = today - timedelta(days=29)
    end_date = today
    kpis = build_marketing_kpis(start_date, end_date)
    package_count = MarketingPackage.objects.count()
    active_publications = ExternalPublication.objects.filter(
        status=ExternalPublicationStatus.PUBLISHED
    ).count()
    channel_publications = (
        ExternalPublication.objects.values("channel")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )
    return render(
        request,
        "campaigns/stats.html",
        {
            "start_date": start_date,
            "end_date": end_date,
            "kpis": kpis,
            "package_count": package_count,
            "active_publications": active_publications,
            "channel_publications": channel_publications,
            "channel_labels": get_distribution_channel_label_map(),
        },
    )


@login_required(login_url="marketing:login")
@require_GET
def weekly_report(request):
    denied = _deny_unless_allowed(request)
    if denied:
        return denied
    if not _admin_marketing_user(request.user):
        return HttpResponseForbidden("营销周报仅对管理员和运营账号开放。")
    today = timezone.localdate()
    start_date = today - timedelta(days=6)
    report = get_or_create_weekly_report(start_date, today, request.user)
    return render(
        request,
        "campaigns/weekly_report.html",
        {
            "report": report,
            "kpis": build_marketing_kpis(start_date, today),
        },
    )


@login_required(login_url="marketing:login")
@require_POST
def prepare_link(request, token):
    denied = _deny_unless_allowed(request)
    if denied:
        return denied
    package = get_object_or_404(_package_queryset(request.user), public_token=token)
    if not package.is_publicly_available():
        messages.error(request, "该素材尚未审核为可发布，不能生成对外链接。")
        return redirect("marketing:package-detail", token=package.public_token)
    form = ShareLinkForm(request.POST, user=request.user)
    if not form.is_valid():
        messages.error(request, "请选择有效传播渠道和推广身份。")
        return redirect("marketing:package-detail", token=package.public_token)
    link, _created = TrackedLink.objects.get_or_create(
        marketing_package=package,
        source_code=form.cleaned_data["channel"],
        promoter=form.cleaned_data["promoter"],
        defaults={"purpose": "营销发布中心生成"},
    )
    if not link.is_active:
        link.is_active = True
        link.save(update_fields=("is_active",))
    messages.success(request, "专属传播链接和二维码已准备完成。")
    detail_url = reverse("marketing:package-detail", kwargs={"token": package.public_token})
    return redirect(f"{detail_url}?link={link.token}")


@login_required(login_url="marketing:login")
@require_GET
def tracked_link_qr(request, token):
    denied = _deny_unless_allowed(request)
    if denied:
        return denied
    link = get_object_or_404(
        TrackedLink.objects.select_related("marketing_package", "promoter"), token=token
    )
    if _authorized_link(request.user, link.marketing_package, token) is None:
        return HttpResponseForbidden("不能访问其他推广人的二维码。")
    response = HttpResponse(
        render_qr_png(_absolute_tracked_url(request, link)), content_type="image/png"
    )
    response["Content-Disposition"] = f'inline; filename="marketing-{link.token}.png"'
    response["Cache-Control"] = "private, no-store"
    return response


def _write_text(archive, name, content):
    archive.writestr(name, (content or "").encode("utf-8-sig"))


def _zip_safe_name(name):
    return str(name).replace("/", "／").replace("\\", "／").replace(":", "：")


@login_required(login_url="marketing:login")
@require_GET
def download_package(request, token):
    denied = _deny_unless_allowed(request)
    if denied:
        return denied
    package = get_object_or_404(_package_queryset(request.user), public_token=token)
    link_token = request.GET.get("link", "")
    link = _authorized_link(request.user, package, link_token)
    if not link or not package.is_publicly_available():
        return HttpResponseForbidden("请先生成当前账号可用的传播链接。")
    share_url = _absolute_tracked_url(request, link)
    ensure_base_poster_variants(package)
    dealer_variant = None
    if link.promoter:
        dealer_variant = generate_poster_variant(
            package,
            PosterVariantType.DEALER,
            tracked_link=link,
            promoter=link.promoter,
            target_url=share_url,
        )
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        if package.poster:
            with package.poster.open("rb") as file:
                archive.writestr("朋友圈海报.png", file.read())
        if package.video_cover:
            with package.video_cover.open("rb") as file:
                archive.writestr("短视频封面.jpg", file.read())
        _write_text(archive, "朋友圈文案.txt", package.wechat_moments_copy)
        _write_text(archive, "客户私聊文案.txt", package.customer_private_copy)
        _write_text(archive, "微信群文案.txt", package.wechat_group_copy)
        _write_text(
            archive,
            "视频号标题和文案.txt",
            f"{package.wechat_channels_title}\n\n{package.wechat_channels_copy}",
        )
        _write_text(
            archive,
            "抖音标题和话题.txt",
            f"{package.douyin_title}\n\n{package.douyin_topics}",
        )
        _write_text(archive, "短视频脚本.txt", package.short_video_script)
        _write_text(archive, "示范阶段链接.txt", share_url)
        archive.writestr("专属二维码.png", render_qr_png(share_url))
        for variant in package.poster_variants.filter(is_active=True, tracked_link__isnull=True):
            if variant.image:
                with variant.image.open("rb") as file:
                    archive.writestr(
                        f"{_zip_safe_name(variant.get_variant_type_display())}.png",
                        file.read(),
                    )
        if dealer_variant and dealer_variant.image:
            with dealer_variant.image.open("rb") as file:
                archive.writestr("经销商专属海报.png", file.read())
    response = HttpResponse(output.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="marketing-{package.public_token}.zip"'
    response["Cache-Control"] = "private, no-store"
    return response
