from io import BytesIO

import pytest
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from core.models import PublicationStatus, SiteConfiguration
from media_assets.models import MediaAsset, MediaType, VideoPlatform
from varieties.models import SellingPoint, Variety


@pytest.mark.django_db
def test_home_page_uses_site_configuration(client):
    configuration = SiteConfiguration.load()
    configuration.site_name = "测试展示平台"
    configuration.hero_title = "真实田间，清晰呈现"
    configuration.default_share_title = "测试分享标题"
    configuration.default_share_description = "测试分享描述"
    configuration.save()

    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "测试展示平台" in content
    assert "真实田间，清晰呈现" in content
    assert '<meta property="og:title" content="测试分享标题">' in content
    assert '<meta property="og:description" content="测试分享描述">' in content


@pytest.mark.django_db
def test_home_page_contains_mobile_viewport(client):
    response = client.get(reverse("core:home"))

    assert 'name="viewport"' in response.content.decode()


@pytest.mark.django_db
def test_fe_home_001_puts_default_visual_before_copy(client):
    response = client.get(reverse("core:home"))
    content = response.content.decode()

    assert content.index('class="field-visual"') < content.index('class="hero-copy"')


@pytest.mark.django_db
def test_fe_home_002_and_fe_lead_001_use_compact_mobile_layout(client):
    response = client.get(reverse("core:home"))
    content = response.content.decode()
    css = (settings.BASE_DIR / "static/css/site.css").read_text(encoding="utf-8")

    assert "site.css?v=20260707-6" in content
    assert ".feature-card .text-link" in css
    assert ".regional-contact-card h3" in css
    assert ".inquiry-form .form-row" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in css
    assert ".lightbox[open]" in css
    assert "position: fixed;" in css
    assert "env(safe-area-inset-top)" in css


@pytest.mark.django_db
def test_fe_global_001_supports_forced_mobile_preview(client):
    response = client.get(f"{reverse('core:home')}?mobile=1")
    content = response.content.decode()
    preview_js = (settings.BASE_DIR / "static/js/mobile-preview.js").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert "mobile-preview.js?v=20260707-1" in content
    assert 'url.searchParams.get("mobile") === "1"' in preview_js
    assert 'frameUrl.searchParams.set("_mobile_frame", "1")' in preview_js
    assert 'currentFrameUrl.searchParams.set("mobile", "1")' in preview_js


@pytest.mark.django_db
def test_fe_global_001_mobile_preview_frame_is_same_origin_only(client):
    normal_response = client.get(reverse("core:home"))
    frame_response = client.get(f"{reverse('core:home')}?_mobile_frame=1")

    assert normal_response.headers["X-Frame-Options"] == "DENY"
    assert frame_response.headers["X-Frame-Options"] == "SAMEORIGIN"


@pytest.mark.django_db
def test_home_page_uses_published_featured_variety(client):
    configuration = SiteConfiguration.load()
    configuration.primary_cta_label = "查看示范点"
    configuration.secondary_cta_label = "我要咨询"
    configuration.save()
    variety = Variety.objects.create(
        name="首页重点品种",
        slug="featured-variety",
        positioning="首页重点定位",
        summary="首页重点简介",
        status=PublicationStatus.PUBLISHED,
        is_featured=True,
    )
    SellingPoint.objects.create(
        variety=variety,
        title="重点卖点",
        slug="featured-point",
        short_description="重点卖点说明",
        status=PublicationStatus.PUBLISHED,
    )

    response = client.get(reverse("core:home"))
    content = response.content.decode()

    assert "首页重点品种" in content
    assert "首页重点定位" in content
    assert "重点卖点" in content
    assert f'href="{reverse("sites:list")}">查看示范点</a>' in content
    assert f'href="{variety.get_absolute_url()}">查看品种详情</a>' in content
    assert 'href="#regional-contacts">我要咨询</a>' in content
    assert "data-home-first-action" in content
    assert "site.js?v=20260708-1" in content
    assert 'class="home-page has-mobile-action-bar"' in content
    assert 'aria-label="页面快捷操作"' in content
    assert f'data-default-href="{variety.get_absolute_url()}"' in content
    assert 'data-default-label="看详情"' in content
    assert '<span aria-hidden="true">▦</span>看详情</a>' in content
    assert f'href="{reverse("sites:list")}"><span aria-hidden="true">⌖</span>看示范</a>' in content

    site_js = (settings.BASE_DIR / "static/js/site.js").read_text(encoding="utf-8")
    assert 'new Set(["#regional-contacts", "#contact", "#inquiry"])' in site_js
    assert "labelNode.textContent = inContactSection" in site_js
    assert '? "返回"' in site_js


@pytest.mark.django_db
def test_home_page_puts_featured_cover_first_and_uses_thumbnail(client, tmp_path):
    variety = Variety.objects.create(
        name="首屏图片品种",
        slug="featured-cover-variety",
        positioning="首屏图片定位",
        summary="首屏图片简介",
        status=PublicationStatus.PUBLISHED,
        is_featured=True,
    )
    image_bytes = BytesIO()
    Image.new("RGB", (120, 80), (46, 120, 62)).save(image_bytes, format="PNG")

    with override_settings(MEDIA_ROOT=tmp_path):
        media = MediaAsset.objects.create(
            content_type=ContentType.objects.get_for_model(variety),
            object_id=variety.pk,
            media_type=MediaType.IMAGE,
            image=SimpleUploadedFile("featured.png", image_bytes.getvalue()),
            alt_text="推荐品种田间图片",
            is_cover=True,
            status=PublicationStatus.PUBLISHED,
        )
        media.refresh_from_db()

        response = client.get(reverse("core:home"))
        content = response.content.decode()

        assert response.status_code == 200
        assert "hero-grid has-featured-image" in content
        assert 'class="field-cover-image"' in content
        assert content.index('class="field-cover-image"') < content.index('class="hero-copy"')
        assert media.thumbnail.url in content
        assert media.image.url not in content
        assert (
            f'<meta property="og:image" content="http://testserver{media.thumbnail.url}">'
            in content
        )
        assert "真实田间表现" not in content
        assert "从播种到收获，持续沉淀示范数据" not in content


@pytest.mark.django_db
def test_home_video_cover_links_to_video_and_shows_play_button(client, tmp_path):
    variety = Variety.objects.create(
        name="视频封面品种",
        slug="featured-video-variety",
        positioning="视频封面定位",
        summary="视频封面简介",
        status=PublicationStatus.PUBLISHED,
        is_featured=True,
    )
    cover_bytes = BytesIO()
    Image.new("RGB", (120, 80), (35, 90, 48)).save(cover_bytes, format="JPEG")
    video_url = "https://weixin.qq.com/sph/example"

    with override_settings(MEDIA_ROOT=tmp_path):
        MediaAsset.objects.create(
            content_type=ContentType.objects.get_for_model(variety),
            object_id=variety.pk,
            media_type=MediaType.VIDEO_LINK,
            title="品种介绍视频",
            video_platform=VideoPlatform.WECHAT_CHANNELS,
            video_url=video_url,
            video_cover=SimpleUploadedFile("video-cover.jpg", cover_bytes.getvalue()),
            is_cover=True,
            status=PublicationStatus.PUBLISHED,
        )

        response = client.get(reverse("core:home"))
        content = response.content.decode()

        assert response.status_code == 200
        assert f'class="hero-video-link" href="{video_url}"' in content
        assert 'target="_blank" rel="noopener noreferrer"' in content
        assert 'class="hero-play-button"' in content
        assert content.index('class="hero-video-link"') < content.index('class="hero-copy"')


@pytest.mark.django_db
def test_home_local_video_cover_renders_inline_player(client, tmp_path):
    variety = Variety.objects.create(
        name="本地视频品种",
        slug="local-video-variety",
        positioning="本地视频定位",
        summary="本地视频简介",
        status=PublicationStatus.PUBLISHED,
        is_featured=True,
    )
    cover_bytes = BytesIO()
    Image.new("RGB", (120, 80), (35, 90, 48)).save(cover_bytes, format="JPEG")
    video_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"local-video"

    with override_settings(MEDIA_ROOT=tmp_path):
        media = MediaAsset.objects.create(
            content_type=ContentType.objects.get_for_model(variety),
            object_id=variety.pk,
            media_type=MediaType.LOCAL_VIDEO,
            title="本地品种视频",
            video_file=SimpleUploadedFile("local-video.mp4", video_bytes),
            video_cover=SimpleUploadedFile("local-cover.jpg", cover_bytes.getvalue()),
            is_cover=True,
            status=PublicationStatus.PUBLISHED,
        )
        media.refresh_from_db()

        response = client.get(reverse("core:home"))
        content = response.content.decode()

        assert response.status_code == 200
        assert 'class="hero-local-video" controls' in content
        assert media.video_file.url in content
        assert f'poster="{media.thumbnail.url}"' in content
        assert content.index('class="hero-local-video"') < content.index('class="hero-copy"')
