import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.urls import reverse

from campaigns.models import ChannelQRCode, QRTargetType
from campaigns.views import build_scan_url
from core.models import PublicationStatus, SiteConfiguration
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
