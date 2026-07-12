from io import BytesIO
from zipfile import ZipFile

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from analytics.models import VisitEvent
from campaigns.forms import ExternalPublicationForm, ShareLinkForm
from campaigns.models import (
    DistributionChannel,
    ExternalPublication,
    ExternalPublicationStatus,
    MarketingPackageStatus,
    MarketingWeeklyReport,
    PromoterType,
    PromotionIdentity,
    ShortVideoTopic,
    TrackedLink,
)
from campaigns.services import ensure_marketing_package, generate_marketing_images
from collection.models import (
    CollectionStatus,
    Observation,
    ObservationPhoto,
    PublishedObservation,
)
from core.models import PublicationStatus, SiteConfiguration
from inquiries.models import CustomerIdentity, Inquiry, InquiryIntent
from sites.models import DemoSite, Region
from varieties.models import Variety


def make_package(slug, *, status=MarketingPackageStatus.READY, with_images=False):
    publisher = get_user_model().objects.create_user(f"publisher-{slug}")
    variety = Variety.objects.create(
        name=f"发布中心品种-{slug}",
        slug=f"publishing-variety-{slug}",
        positioning="适宜区域推广",
        summary="发布中心测试",
        status=PublicationStatus.PUBLISHED,
    )
    site = DemoSite.objects.create(
        name=f"发布中心示范点-{slug}",
        slug=f"publishing-site-{slug}",
        variety=variety,
        region=Region.HUANG_HUAI_HAI,
        province="河南省",
        city="郑州市",
        county="测试县",
        main_performance="站秆好、穗部整齐、脱水较快",
        description="发布中心公开介绍",
        status=PublicationStatus.PUBLISHED,
    )
    observation = Observation.objects.create(
        site=site,
        stage="maturity",
        status=CollectionStatus.PUBLISHED,
        data={"lodging_rate": "1.2", "stay_green": "good"},
        created_by=publisher,
        updated_by=publisher,
    )
    if with_images:
        output = BytesIO()
        Image.new("RGB", (800, 600), "#4d955a").save(output, "JPEG")
        ObservationPhoto.objects.create(
            observation=observation,
            image=SimpleUploadedFile("field.jpg", output.getvalue(), content_type="image/jpeg"),
            uploaded_by=publisher,
        )
    snapshot = PublishedObservation.objects.create(
        observation=observation,
        version=1,
        public_data=observation.data,
        public_summary="成熟期站秆稳定，果穗整齐，适合组织看田。",
        published_by=publisher,
    )
    package = ensure_marketing_package(snapshot)
    package.status = status
    package.save(update_fields=("status", "updated_at"))
    return package


@pytest.mark.django_db
def test_mkt_center_001_requires_login_and_authorized_identity(client):
    response = client.get(reverse("marketing:dashboard"))
    assert response.status_code == 302
    assert reverse("marketing:login") in response.url

    login_page = client.get(response.url)
    login_content = login_page.content.decode()
    assert login_page.status_code == 200
    assert "我要发布登录" in login_content
    assert "营销发布中心" in login_content
    assert f'href="{reverse("core:home")}">返回首页</a>' in login_content
    assert f'href="{reverse("marketing:login")}">登录</a>' not in login_content
    assert "负责人采集登录" not in login_content

    unauthorized = get_user_model().objects.create_user("no-marketing-access")
    client.force_login(unauthorized)
    denied = client.get(reverse("marketing:dashboard"))
    assert denied.status_code == 302
    assert reverse("marketing:login") in denied.url
    assert "_auth_user_id" not in client.session

    denied_login_page = client.get(denied.url)
    assert "当前账号没有营销发布权限" in denied_login_page.content.decode()


@pytest.mark.django_db
def test_mkt_center_001_promoter_sees_only_publishable_packages(client):
    user = get_user_model().objects.create_user("marketing-sales")
    identity = PromotionIdentity.objects.create(
        user=user,
        name="河南销售",
        code="henan-marketing-sales",
        promoter_type=PromoterType.SALES,
        region="河南",
    )
    ready = make_package("ready")
    generated = make_package("generated", status=MarketingPackageStatus.GENERATED)
    client.force_login(user)

    response = client.get(reverse("marketing:dashboard"))
    content = response.content.decode()

    assert response.status_code == 200
    assert identity.name in content
    assert "一键营销" in content
    assert "一键转发素材" not in content
    assert ready.observation.site.name in content
    assert generated.observation.site.name not in content
    assert "打开转发包" in content


@pytest.mark.django_db
def test_mkt_center_001_hides_admin_menus_without_marketing_admin_permission(client):
    user = get_user_model().objects.create_user("marketing-viewer", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="view_marketingpackage"))
    make_package("viewer-menu")
    client.force_login(user)

    response = client.get(reverse("marketing:dashboard"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "统计看板" not in content
    assert "营销周报" not in content
    assert 'name="status"' not in content
    assert client.get(reverse("marketing:weekly-report")).status_code == 403


@pytest.mark.django_db
def test_mkt_center_001_logout_returns_to_entry_specific_page(client):
    direct_user = get_user_model().objects.create_user("marketing-direct", password="123456")
    PromotionIdentity.objects.create(
        user=direct_user,
        name="直接登录销售",
        code="marketing-direct",
        promoter_type=PromoterType.SALES,
    )
    client.get(reverse("marketing:login"))
    client.post(
        reverse("marketing:login"),
        {"username": direct_user.username, "password": "123456", "next": ""},
    )

    direct_logout = client.post(reverse("marketing:logout"))

    assert direct_logout.status_code == 302
    assert direct_logout.url == reverse("marketing:login")

    home_user = get_user_model().objects.create_user("marketing-home", password="123456")
    PromotionIdentity.objects.create(
        user=home_user,
        name="首页入口销售",
        code="marketing-home",
        promoter_type=PromoterType.SALES,
    )
    landing_response = client.get(f"{reverse('marketing:dashboard')}?entry=home")
    client.get(landing_response.url)
    next_url = landing_response.url.split("next=", 1)[1]
    client.post(
        reverse("marketing:login"),
        {"username": home_user.username, "password": "123456", "next": next_url},
    )

    home_logout = client.post(reverse("marketing:logout"))

    assert home_logout.status_code == 302
    assert home_logout.url == reverse("core:home")


@pytest.mark.django_db
def test_mkt_package_001_creates_promoter_link_copy_page_and_qr(client):
    user = get_user_model().objects.create_user("dealer-portal")
    identity = PromotionIdentity.objects.create(
        user=user,
        name="测试经销商",
        code="test-dealer-portal",
        promoter_type=PromoterType.DEALER,
    )
    package = make_package("dealer-link")
    client.force_login(user)

    response = client.post(
        reverse("marketing:prepare-link", args=(package.public_token,)),
        {"channel": DistributionChannel.WECHAT_GROUP},
    )

    link = TrackedLink.objects.get(
        marketing_package=package,
        source_code=DistributionChannel.WECHAT_GROUP,
    )
    assert link.promoter == identity
    assert response.status_code == 302
    assert f"?link={link.token}" in response.url

    detail = client.get(response.url)
    content = detail.content.decode()
    assert detail.status_code == 200
    assert "复制链接" in content
    assert "复制朋友圈文案" in content
    assert "复制客户私聊文案" in content
    assert "复制微信群文案" in content
    assert "下载完整转发包 ZIP" in content
    assert link.get_scan_path() in content
    assert f'<option value="{DistributionChannel.WECHAT_GROUP}" selected>' in content

    qr = client.get(reverse("marketing:tracked-link-qr", args=(link.token,)))
    assert qr.status_code == 200
    assert qr["Content-Type"] == "image/png"
    assert qr.content.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.django_db
def test_mkt_package_001_share_channels_exclude_identity_types():
    user = get_user_model().objects.create_user("channel-user")

    form = ShareLinkForm(user=user)
    channel_values = {value for value, _label in form.fields["channel"].choices}

    assert "sales_share" not in channel_values
    assert "dealer_share" not in channel_values
    assert DistributionChannel.WECHAT_MOMENTS in channel_values
    assert DistributionChannel.WECHAT_GROUP in channel_values


@pytest.mark.django_db
def test_mkt_package_001_publication_link_required_only_for_video_channels():
    published_at = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    wechat_group_form = ExternalPublicationForm(
        data={
            "channel": DistributionChannel.WECHAT_GROUP,
            "status": ExternalPublicationStatus.PUBLISHED,
            "title": "微信群发布",
            "published_at": published_at,
            "view_count": 0,
            "like_count": 0,
            "comment_count": 0,
            "share_count": 0,
        }
    )
    wechat_channels_form = ExternalPublicationForm(
        data={
            "channel": DistributionChannel.WECHAT_CHANNELS,
            "status": ExternalPublicationStatus.PUBLISHED,
            "title": "视频号发布",
            "published_at": published_at,
            "view_count": 0,
            "like_count": 0,
            "comment_count": 0,
            "share_count": 0,
        }
    )

    assert wechat_group_form.is_valid()
    assert not wechat_channels_form.is_valid()
    assert "external_url" in wechat_channels_form.errors


@pytest.mark.django_db
def test_mkt_package_001_zip_contains_images_copy_link_and_qr(client, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    configuration = SiteConfiguration.load()
    configuration.public_base_url = "https://bzb889.originseed.com.cn"
    configuration.save()
    user = get_user_model().objects.create_user("zip-sales")
    identity = PromotionIdentity.objects.create(
        user=user,
        name="ZIP销售",
        code="zip-sales",
        promoter_type=PromoterType.SALES,
    )
    package = make_package("zip", with_images=True)
    generate_marketing_images(package)
    link = TrackedLink.objects.create(
        marketing_package=package,
        source_code=DistributionChannel.WECHAT_MOMENTS,
        promoter=identity,
    )
    client.force_login(user)

    response = client.get(
        reverse("marketing:download-package", args=(package.public_token,)),
        {"link": link.token},
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "application/zip"
    with ZipFile(BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert "朋友圈海报.png" in names
        assert "短视频封面.jpg" in names
        assert "朋友圈文案.txt" in names
        assert "客户私聊文案.txt" in names
        assert "微信群文案.txt" in names
        assert "视频号标题和文案.txt" in names
        assert "抖音标题和话题.txt" in names
        assert "短视频脚本.txt" in names
        assert "示范阶段链接.txt" in names
        assert "专属二维码.png" in names
        assert "朋友圈图文海报.png" in names
        assert "观摩会／看田邀请.png" in names
        assert "本周重点推荐.png" in names
        assert "经销商专属海报.png" in names
        link_text = archive.read("示范阶段链接.txt").decode("utf-8-sig")
        assert str(link.token) in link_text
        moments_text = archive.read("朋友圈文案.txt").decode("utf-8-sig")
        assert package.wechat_moments_copy in moments_text
        private_text = archive.read("客户私聊文案.txt").decode("utf-8-sig")
        assert package.customer_private_copy in private_text


@pytest.mark.django_db
def test_mkt_package_001_promoter_cannot_download_another_promoters_link(client):
    first_user = get_user_model().objects.create_user("first-promoter")
    first = PromotionIdentity.objects.create(
        user=first_user,
        name="第一推广人",
        code="first-promoter",
        promoter_type=PromoterType.SALES,
    )
    second_user = get_user_model().objects.create_user("second-promoter")
    PromotionIdentity.objects.create(
        user=second_user,
        name="第二推广人",
        code="second-promoter",
        promoter_type=PromoterType.DEALER,
    )
    package = make_package("permission")
    link = TrackedLink.objects.create(
        marketing_package=package,
        source_code=DistributionChannel.WECHAT_MOMENTS,
        promoter=first,
    )
    client.force_login(second_user)

    response = client.get(
        reverse("marketing:download-package", args=(package.public_token,)),
        {"link": link.token},
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_mkt_center_001_admin_can_approve_generated_package(admin_client):
    package = make_package("admin-review", status=MarketingPackageStatus.GENERATED)

    response = admin_client.post(
        reverse("admin:campaigns_marketingpackage_changelist"),
        {
            "action": "mark_ready",
            "_selected_action": [package.pk],
        },
    )

    assert response.status_code == 302
    package.refresh_from_db()
    assert package.status == MarketingPackageStatus.READY
    assert package.reviewed_by is not None
    assert package.reviewed_at is not None


@pytest.mark.django_db
def test_mkt_center_001_registered_published_package_remains_public(client):
    package = make_package("published", status=MarketingPackageStatus.PUBLISHED)

    response = client.get(package.get_absolute_url())

    assert response.status_code == 200


@pytest.mark.django_db
def test_mkt_poster_001_admin_detail_can_generate_missing_materials(
    admin_client, tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    configuration = SiteConfiguration.load()
    configuration.public_base_url = "https://bzb889.originseed.com.cn"
    configuration.save()
    package = make_package("admin-generate", with_images=True)
    assert not package.poster

    response = admin_client.post(
        reverse("admin:campaigns_marketingpackage_generate_materials", args=(package.pk,))
    )

    assert response.status_code == 302
    assert response.url == reverse("admin:campaigns_marketingpackage_change", args=(package.pk,))
    package.refresh_from_db()
    assert package.poster
    assert package.video_cover


@pytest.mark.django_db
def test_mkt_publish_001_records_external_publication_and_displays_on_stage_page(client):
    user = get_user_model().objects.create_user("video-publisher")
    PromotionIdentity.objects.create(
        user=user,
        name="视频运营",
        code="video-publisher",
        promoter_type=PromoterType.SALES,
    )
    package = make_package("external-video")
    client.force_login(user)

    response = client.post(
        reverse("marketing:add-publication", args=(package.public_token,)),
        {
            "channel": DistributionChannel.DOUYIN_VIDEO,
            "status": ExternalPublicationStatus.PUBLISHED,
            "title": "棒中棒889成熟期站秆表现",
            "account_name": "奥瑞金官方抖音",
            "external_url": "https://www.douyin.com/video/example",
            "published_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "view_count": 1200,
            "like_count": 80,
            "comment_count": 12,
            "share_count": 9,
        },
    )

    assert response.status_code == 302
    publication = ExternalPublication.objects.get(marketing_package=package)
    assert publication.created_by == user
    assert publication.engagement_count == 101

    stage_page = client.get(package.get_absolute_url())
    content = stage_page.content.decode()
    assert stage_page.status_code == 200
    assert "已发布短视频" in content
    assert "奥瑞金官方抖音" in content
    assert "https://www.douyin.com/video/example" in content


@pytest.mark.django_db
def test_mkt_topic_001_package_detail_creates_single_focus_video_topics(client):
    user = get_user_model().objects.create_user("topic-sales")
    PromotionIdentity.objects.create(
        user=user,
        name="选题销售",
        code="topic-sales",
        promoter_type=PromoterType.SALES,
    )
    package = make_package("topics")
    ShortVideoTopic.objects.filter(marketing_package=package).delete()
    client.force_login(user)

    response = client.get(reverse("marketing:package-detail", args=(package.public_token,)))
    content = response.content.decode()

    assert response.status_code == 200
    assert package.short_video_topics.count() >= 3
    assert "短视频选题拆分" in content
    assert "复制脚本" in content


@pytest.mark.django_db
def test_mkt_dashboard_001_stats_counts_attributed_visits_inquiries_and_publications(
    admin_client,
):
    package = make_package("stats")
    promoter = PromotionIdentity.objects.create(
        name="统计销售",
        code="stats-sales",
        promoter_type=PromoterType.SALES,
    )
    tracked_link = TrackedLink.objects.create(
        marketing_package=package,
        source_code=DistributionChannel.WECHAT_MOMENTS,
        promoter=promoter,
    )
    VisitEvent.objects.create(
        path=package.get_absolute_url(),
        source_code=DistributionChannel.WECHAT_MOMENTS,
        visitor_hash="visitor-stats-1",
        marketing_package=package,
        promotion_identity=promoter,
        tracked_link=tracked_link,
    )
    Inquiry.objects.create(
        name="统计客户",
        phone="13800000020",
        area_name="河南",
        privacy_consent=True,
        customer_identity=CustomerIdentity.DEALER,
        intent_type=InquiryIntent.AGENCY,
        source_code=DistributionChannel.WECHAT_MOMENTS,
        marketing_package=package,
        promotion_identity=promoter,
        tracked_link=tracked_link,
    )
    ExternalPublication.objects.create(
        marketing_package=package,
        channel=DistributionChannel.WECHAT_CHANNELS,
        status=ExternalPublicationStatus.PUBLISHED,
        title="视频号发布测试",
        external_url="https://channels.weixin.qq.com/example",
        published_at=timezone.now(),
        view_count=300,
        like_count=20,
    )

    response = admin_client.get(reverse("marketing:stats"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "营销统计看板" in content
    assert "统计销售" in content
    assert "300" in content
    assert package.observation.site.name in content


@pytest.mark.django_db
def test_mkt_weekly_001_current_week_report_is_generated_for_admin(admin_client):
    package = make_package("weekly")
    VisitEvent.objects.create(
        path=package.get_absolute_url(),
        source_code=DistributionChannel.WECHAT_GROUP,
        visitor_hash="weekly-visitor",
        marketing_package=package,
    )

    response = admin_client.get(reverse("marketing:weekly-report"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "营销传播周报" in content
    assert "周报摘要" in content
    assert "本周营销传播访问 1 次" in content
    assert MarketingWeeklyReport.objects.count() == 1
