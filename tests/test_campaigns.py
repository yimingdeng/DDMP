from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import RequestFactory
from django.urls import reverse
from PIL import Image

from analytics.models import VisitEvent
from campaigns.models import (
    ChannelQRCode,
    MarketingPackage,
    MarketingPackageStatus,
    MarketingPosterVariant,
    PosterVariantType,
    PromoterType,
    PromotionIdentity,
    QRTargetType,
    TrackedLink,
)
from campaigns.services import ensure_marketing_package, generate_marketing_images
from campaigns.views import build_scan_url
from collection.models import (
    CollectionStatus,
    Observation,
    ObservationPhoto,
    PublishedObservation,
)
from core.models import PublicationStatus, SiteColorTheme, SiteConfiguration
from inquiries.models import CustomerIdentity, Inquiry
from sites.models import DemoSite, Region
from varieties.models import Variety


def make_variety():
    return Variety.objects.create(
        name="二维码测试品种",
        slug="qr-test-variety",
        positioning="二维码测试定位",
        summary="二维码测试简介",
        status=PublicationStatus.PUBLISHED,
    )


def make_site(variety):
    return DemoSite.objects.create(
        name="二维码测试示范点",
        slug="qr-test-site",
        variety=variety,
        region=Region.HUANG_HUAI_HAI,
        province="河南省",
        city="郑州市",
        county="测试县",
        status=PublicationStatus.DRAFT,
    )


def make_snapshot(slug="marketing-snapshot", stage="maturity", with_photo=False):
    user = get_user_model().objects.create_user(f"publisher-{slug}")
    variety = Variety.objects.create(
        name=f"营销品种-{slug}",
        slug=f"variety-{slug}",
        positioning="适宜黄淮海区域推广",
        summary="营销素材测试品种",
        status=PublicationStatus.PUBLISHED,
    )
    site = DemoSite.objects.create(
        name=f"营销示范点-{slug}",
        slug=slug,
        variety=variety,
        region=Region.HUANG_HUAI_HAI,
        province="河南省",
        city="郑州市",
        county="测试县",
        main_performance="站秆好、穗部整齐、脱水较快",
        description="公开示范点介绍",
        status=PublicationStatus.PUBLISHED,
    )
    observation = Observation.objects.create(
        site=site,
        stage=stage,
        status=CollectionStatus.PUBLISHED,
        data={"standability": "好", "ear_uniformity": "整齐"},
        created_by=user,
        updated_by=user,
    )
    if with_photo:
        output = BytesIO()
        Image.new("RGB", (900, 700), "#4d955a").save(output, "JPEG")
        ObservationPhoto.objects.create(
            observation=observation,
            image=SimpleUploadedFile(
                "marketing-field.jpg", output.getvalue(), content_type="image/jpeg"
            ),
            caption="成熟期田间实拍",
            uploaded_by=user,
        )
    snapshot = PublishedObservation.objects.create(
        observation=observation,
        version=1,
        public_data=observation.data,
        public_summary="站秆表现好，果穗整齐，脱水较快。",
        published_by=user,
    )
    return snapshot


@pytest.mark.django_db
def test_qr_scan_redirects_to_target_with_source_and_counts(client):
    variety = make_variety()
    qr_code = ChannelQRCode.objects.create(
        name="微信朋友圈品种二维码",
        target_type=QRTargetType.VARIETY,
        variety=variety,
        source_code="wechat_moments",
    )

    response = client.get(qr_code.get_scan_path())

    assert response.status_code == 302
    assert response.url == f"{variety.get_absolute_url()}?source=wechat_moments"
    qr_code.refresh_from_db()
    assert qr_code.scan_count == 1
    assert qr_code.last_scanned_at is not None


@pytest.mark.django_db
def test_qr_scan_persists_source_after_redirect(client):
    qr_code = ChannelQRCode.objects.create(
        name="咨询二维码",
        target_type=QRTargetType.CONTACT,
        source_code="henan_field_sign",
    )

    response = client.get(qr_code.get_scan_path(), follow=True)

    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/?source=henan_field_sign#contact"
    assert client.session["campaign_source"] == "henan_field_sign"


@pytest.mark.django_db
def test_inactive_qr_returns_home_without_counting(client):
    qr_code = ChannelQRCode.objects.create(
        name="已停用二维码",
        target_type=QRTargetType.HOME,
        source_code="old_campaign",
        is_active=False,
    )

    response = client.get(qr_code.get_scan_path())

    assert response.status_code == 302
    assert response.url == reverse("core:home")
    qr_code.refresh_from_db()
    assert qr_code.scan_count == 0


@pytest.mark.django_db
def test_qr_target_validation_is_clear():
    qr_code = ChannelQRCode(
        name="缺少目标",
        target_type=QRTargetType.VARIETY,
        source_code="missing_target",
    )

    with pytest.raises(ValidationError) as error:
        qr_code.full_clean()

    assert "variety" in error.value.message_dict


@pytest.mark.django_db
def test_adm_qr_001_target_type_clears_irrelevant_previous_targets():
    variety = make_variety()
    site = make_site(variety)
    qr_code = ChannelQRCode(
        name="目标类型切换测试",
        target_type=QRTargetType.HOME,
        variety=variety,
        demo_site=site,
        source_code="switch_target",
    )

    qr_code.full_clean()
    assert qr_code.variety is None
    assert qr_code.demo_site is None

    qr_code.target_type = QRTargetType.SITE
    qr_code.variety = variety
    qr_code.demo_site = site
    qr_code.full_clean()
    assert qr_code.variety is None
    assert qr_code.demo_site == site


@pytest.mark.django_db
def test_staff_can_preview_and_download_qr_png(client):
    user = get_user_model().objects.create_user(
        username="qr-admin",
        password="test-password",
        is_staff=True,
    )
    qr_code = ChannelQRCode.objects.create(
        name="下载测试二维码",
        target_type=QRTargetType.HOME,
        source_code="download_test",
    )
    client.force_login(user)
    url = reverse("campaigns-admin:qr-png", kwargs={"pk": qr_code.pk})

    preview = client.get(url)
    download = client.get(url, {"download": "1"})

    assert preview.status_code == 200
    assert preview["Content-Type"] == "image/png"
    assert preview.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert download["Content-Disposition"].startswith("attachment;")


@pytest.mark.django_db
def test_qr_uses_current_public_host_when_config_contains_local_dev_url(settings):
    settings.ALLOWED_HOSTS = ["bzb889.originseed.com.cn"]
    SiteConfiguration.objects.create(public_base_url="http://127.0.0.1:8000")
    qr_code = ChannelQRCode.objects.create(
        name="公网二维码",
        target_type=QRTargetType.HOME,
        source_code="public_host_qr",
    )
    request = RequestFactory().get(
        "/campaigns/qr/1.png",
        secure=True,
        HTTP_HOST="bzb889.originseed.com.cn",
    )

    scan_url = build_scan_url(request, qr_code)

    assert scan_url == f"https://bzb889.originseed.com.cn{qr_code.get_scan_path()}"


@pytest.mark.django_db
def test_mkt_content_001_builds_package_and_public_stage_page(client):
    snapshot = make_snapshot("stage-page")
    package = ensure_marketing_package(snapshot)
    package.status = MarketingPackageStatus.READY
    package.save(update_fields=("status", "updated_at"))

    response = client.get(package.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert snapshot.observation.site.name in content
    assert snapshot.observation.get_stage_display() in content
    assert snapshot.public_summary in content
    assert package.headline in response.context["share_meta"]["title"]
    assert package.core_tags
    assert 'class="theme-purple-yellow stage-detail-page has-mobile-action-bar"' in content
    assert 'content="#32128f"' in content
    assert TrackedLink.objects.filter(
        marketing_package=package, source_code="wechat_moments"
    ).exists()


@pytest.mark.django_db
def test_mkt_content_001_disabled_package_token_is_not_public(client):
    snapshot = make_snapshot("disabled-package")
    package = ensure_marketing_package(snapshot)
    package.status = "disabled"
    package.save(update_fields=("status", "updated_at"))

    assert client.get(package.get_absolute_url()).status_code == 404


@pytest.mark.django_db
def test_mkt_link_001_stage_qr_targets_exact_public_snapshot(client):
    snapshot = make_snapshot("stage-qr")
    package = ensure_marketing_package(snapshot)
    package.status = MarketingPackageStatus.READY
    package.save(update_fields=("status", "updated_at"))
    qr_code = ChannelQRCode.objects.create(
        name="成熟期阶段二维码",
        target_type=QRTargetType.STAGE,
        published_observation=snapshot,
        source_code="field_qrcode",
    )

    response = client.get(qr_code.get_scan_path())

    assert response.status_code == 302
    assert package.get_absolute_url() in response.url
    assert "source=field_qrcode" in response.url
    assert f"content={package.public_token}" in response.url


@pytest.mark.django_db
def test_mkt_attr_001_tracked_link_flows_into_visit_and_inquiry(client):
    snapshot = make_snapshot("attribution")
    package = ensure_marketing_package(snapshot)
    package.status = MarketingPackageStatus.READY
    package.save(update_fields=("status", "updated_at"))
    promoter = PromotionIdentity.objects.create(
        name="河南销售王经理",
        code="henan-sales-wang",
        promoter_type=PromoterType.SALES,
        region="河南",
    )
    tracked_link = TrackedLink.objects.create(
        marketing_package=package,
        source_code="wechat_moments",
        promoter=promoter,
    )

    landing = client.get(tracked_link.get_scan_path())

    assert landing.status_code == 200
    assert landing.context["share_meta"]["url"].endswith(tracked_link.get_share_path())
    assert "?v=" in landing.context["share_meta"]["url"]
    assert f"share={tracked_link.token}" in landing.context["redirect_url"]
    landing_html = landing.content.decode()
    assert 'property="og:title"' in landing_html
    assert tracked_link.get_share_path() in landing_html

    stage_page = client.get(landing.context["redirect_url"])
    assert stage_page.status_code == 200
    assert stage_page.context["share_meta"]["url"].endswith(tracked_link.get_share_path())
    event = VisitEvent.objects.filter(path=package.get_absolute_url()).latest("occurred_at")
    assert event.marketing_package == package
    assert event.promotion_identity == promoter
    assert event.tracked_link == tracked_link

    response = client.post(
        reverse("inquiries:submit"),
        {
            "name": "渠道客户",
            "phone": "13800000019",
            "area_name": "河南",
            "customer_identity": CustomerIdentity.DEALER,
            "intent_type": "agency",
            "privacy_consent": "on",
            "submission_key": "5cf79cf3-55fc-4f72-989a-5c07812c0137",
            "next": package.get_absolute_url(),
        },
    )

    assert response.status_code == 302
    inquiry = Inquiry.objects.get(name="渠道客户")
    assert inquiry.source_code == "wechat_moments"
    assert inquiry.marketing_package == package
    assert inquiry.promotion_identity == promoter
    assert inquiry.tracked_link == tracked_link


@pytest.mark.django_db
def test_mkt_poster_001_generates_wechat_poster_video_cover_and_copy(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    configuration = SiteConfiguration.load()
    configuration.public_base_url = "https://bzb889.originseed.com.cn"
    configuration.save()
    snapshot = make_snapshot("poster", with_photo=True)
    package = ensure_marketing_package(snapshot)

    generate_marketing_images(package)

    package.refresh_from_db()
    assert package.poster.name.endswith(".png")
    assert package.video_cover.name.endswith(".jpg")
    assert package.wechat_moments_copy
    assert "扫码查看完整田间实拍" in package.wechat_moments_copy
    assert package.customer_private_copy
    assert "您可以先打开链接看看田间实拍" in package.customer_private_copy
    assert package.wechat_group_copy
    assert package.short_video_script
    with package.poster.open("rb") as image_file:
        poster = Image.open(image_file).convert("RGB")
        assert poster.size == (1080, 1440)
        poster_colors = list(poster.resize((108, 144)).get_flattened_data())
    with package.video_cover.open("rb") as image_file:
        cover = Image.open(image_file).convert("RGB")
        assert cover.size == (1080, 1440)
        cover_colors = list(cover.resize((108, 144)).get_flattened_data())

    def is_purple(pixel):
        red, green, blue = pixel
        return blue > red * 1.15 and blue > green * 1.15

    def is_yellow(pixel):
        red, green, blue = pixel
        return red > 180 and green > 160 and blue < 140

    assert sum(map(is_purple, poster_colors)) > len(poster_colors) * 0.15
    assert sum(map(is_yellow, poster_colors)) > len(poster_colors) * 0.005
    assert sum(map(is_purple, cover_colors)) > len(cover_colors) * 0.15
    assert sum(map(is_yellow, cover_colors)) > len(cover_colors) * 0.005
    assert set(package.poster_variants.values_list("variant_type", flat=True)) >= {
        PosterVariantType.MOMENTS,
        PosterVariantType.FIELD_DAY,
        PosterVariantType.WEEKLY_RECOMMENDATION,
    }
    for variant in package.poster_variants.all():
        assert variant.image.name.endswith(".png")
        with variant.image.open("rb") as image_file:
            variant_image = Image.open(image_file).convert("RGB")
            assert variant_image.size == (1080, 1440)


@pytest.mark.django_db
def test_mkt_copy_001_uses_stage_specific_short_video_templates():
    emergence = ensure_marketing_package(make_snapshot("stage-copy-emergence", stage="emergence"))
    maturity = ensure_marketing_package(make_snapshot("stage-copy-maturity", stage="maturity"))

    assert "出苗是否整齐" in emergence.short_video_script
    assert "苗势" in emergence.wechat_group_copy
    assert "成熟期最抓人的就是站秆" in maturity.short_video_script
    assert "站秆" in maturity.douyin_title


@pytest.mark.django_db
def test_mkt_poster_002_dealer_specific_poster_binds_promoter_and_link(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    SiteConfiguration.load().save()
    package = ensure_marketing_package(make_snapshot("dealer-poster", with_photo=True))
    promoter = PromotionIdentity.objects.create(
        name="河南经销商李总",
        code="dealer-li",
        promoter_type=PromoterType.DEALER,
    )
    tracked_link = TrackedLink.objects.create(
        marketing_package=package,
        source_code="wechat_group",
        promoter=promoter,
    )

    from campaigns.services import generate_poster_variant

    variant = generate_poster_variant(
        package,
        PosterVariantType.DEALER,
        tracked_link=tracked_link,
        promoter=promoter,
        target_url="https://bzb889.originseed.com.cn/q/go/test/",
    )

    assert variant.promoter == promoter
    assert variant.tracked_link == tracked_link
    assert "河南经销商李总推荐" in variant.title
    assert MarketingPosterVariant.objects.filter(
        marketing_package=package,
        variant_type=PosterVariantType.DEALER,
        tracked_link=tracked_link,
    ).exists()
    with variant.image.open("rb") as image_file:
        image = Image.open(image_file).convert("RGB")
        assert image.size == (1080, 1440)


@pytest.mark.django_db
def test_mkt_poster_001_uses_configured_system_color_theme(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    configuration = SiteConfiguration.load()
    configuration.color_theme = SiteColorTheme.SYSTEM
    configuration.public_base_url = "https://bzb889.originseed.com.cn"
    configuration.save()
    snapshot = make_snapshot("system-theme-poster", with_photo=True)
    package = ensure_marketing_package(snapshot)

    generate_marketing_images(package)

    package.refresh_from_db()
    with package.poster.open("rb") as image_file:
        poster = Image.open(image_file).convert("RGB")
        red, green, blue = poster.getpixel((0, 0))
        assert green > red
        assert green > blue
    with package.video_cover.open("rb") as image_file:
        cover = Image.open(image_file).convert("RGB")
        red, green, blue = cover.getpixel((0, 0))
        assert green > red
        assert green > blue


@pytest.mark.django_db
def test_mkt_poster_001_new_public_snapshot_generates_package_automatically(
    tmp_path,
    settings,
    django_capture_on_commit_callbacks,
):
    settings.MEDIA_ROOT = tmp_path
    configuration = SiteConfiguration.load()
    configuration.public_base_url = "https://bzb889.originseed.com.cn"
    configuration.save()

    with django_capture_on_commit_callbacks(execute=True):
        snapshot = make_snapshot("automatic-poster", with_photo=True)

    package = MarketingPackage.objects.get(published_observation=snapshot)
    assert package.status == MarketingPackageStatus.GENERATED
    assert package.poster
    assert package.video_cover
    assert package.tracked_links.filter(source_code="wechat_moments").exists()


@pytest.mark.django_db
def test_mkt_poster_001_management_command_backfills_missing_images(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    configuration = SiteConfiguration.load()
    configuration.public_base_url = "https://bzb889.originseed.com.cn"
    configuration.save()
    snapshot = make_snapshot("command-poster", with_photo=True)
    package = ensure_marketing_package(snapshot)
    assert not package.poster

    call_command("generate_marketing_materials", "--missing-only")

    package.refresh_from_db()
    assert package.poster
    assert package.video_cover
