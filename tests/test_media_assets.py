from io import BytesIO

import pytest
from django.contrib.contenttypes.forms import generic_inlineformset_factory
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from core.models import PublicationStatus
from media_assets.forms import MediaAssetAdminForm
from media_assets.inlines import MediaAssetInlineFormSet
from media_assets.models import MediaAsset, MediaType, VideoPlatform
from media_assets.validators import MAX_IMAGE_BYTES, MAX_VIDEO_BYTES, validate_mp4_upload
from sites.models import DemoSite, Region
from varieties.models import SellingPoint, Variety


def make_variety(**overrides):
    data = {
        "name": "媒体测试品种",
        "slug": "media-test-variety",
        "positioning": "媒体测试定位",
        "summary": "媒体测试简介",
        "status": PublicationStatus.PUBLISHED,
    }
    data.update(overrides)
    return Variety.objects.create(**data)


def image_upload(name="field.png", color=(50, 130, 70)):
    output = BytesIO()
    Image.new("RGB", (120, 80), color).save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


def mpo_upload(name="phone-photo.jpg"):
    output = BytesIO()
    first = Image.new("RGB", (120, 80), (50, 130, 70))
    second = Image.new("RGB", (120, 80), (70, 90, 160))
    first.save(output, format="MPO", save_all=True, append_images=[second])
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/jpeg")


def mp4_upload(name="field.mp4"):
    payload = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"test-video-data"
    return SimpleUploadedFile(name, payload, content_type="video/mp4")


def media_for(target, **overrides):
    data = {
        "content_type": ContentType.objects.get_for_model(target),
        "object_id": target.pk,
        "media_type": MediaType.IMAGE,
        "image": image_upload(),
        "alt_text": "田间玉米长势",
        "status": PublicationStatus.PUBLISHED,
    }
    data.update(overrides)
    return MediaAsset(**data)


@pytest.mark.django_db
@pytest.mark.parametrize("target_kind", ["variety", "selling_point", "demo_site"])
def test_fe_media_001_inline_save_ignores_stale_generic_target_cache(tmp_path, target_kind):
    variety = make_variety(name=f"媒体测试品种-{target_kind}", slug=f"media-{target_kind}")
    targets = {
        "variety": variety,
        "selling_point": SellingPoint.objects.create(
            variety=variety,
            title="缓存测试卖点",
            slug="cache-test-point",
            status=PublicationStatus.DRAFT,
        ),
        "demo_site": DemoSite.objects.create(
            name="缓存测试示范点",
            slug="cache-test-site",
            variety=variety,
            region=Region.HUANG_HUAI_HAI,
            province="河南省",
            city="郑州市",
            county="测试县",
            status=PublicationStatus.DRAFT,
        ),
    }
    target = targets[target_kind]
    content_type = ContentType.objects.get_for_model(target)
    media = MediaAsset(
        media_type=MediaType.IMAGE,
        image=image_upload(),
        status=PublicationStatus.DRAFT,
    )

    # Generic inline validation may cache an empty target before Django assigns
    # the parent content type and object ID in save_new().
    assert media.target is None
    media.content_type_id = content_type.pk
    media.object_id = target.pk

    with override_settings(MEDIA_ROOT=tmp_path):
        media.save()

    assert media.target == target


@pytest.mark.django_db
def test_fe_media_001_rejects_missing_target_despite_stale_valid_cache(tmp_path):
    variety = make_variety()
    media = media_for(variety, status=PublicationStatus.DRAFT)

    with override_settings(MEDIA_ROOT=tmp_path):
        media.save()
        assert media.target == variety
        media.object_id = variety.pk + 9999

        with pytest.raises(ValidationError) as error:
            media.save()

    assert error.value.message_dict["object_id"] == ["关联对象不存在。"]


@pytest.mark.django_db
def test_fe_media_001_reassignment_refreshes_generic_target_cache(tmp_path):
    first_variety = make_variety()
    second_variety = make_variety(
        name="第二个媒体测试品种",
        slug="second-media-test-variety",
    )
    media = media_for(first_variety, status=PublicationStatus.DRAFT)

    with override_settings(MEDIA_ROOT=tmp_path):
        media.save()
        assert media.target == first_variety
        media.object_id = second_variety.pk
        media.save()

    assert media.target == second_variety


@pytest.mark.django_db
def test_fe_media_001_invalid_content_type_returns_validation_error(tmp_path):
    media = MediaAsset(
        content_type_id=999999,
        object_id=1,
        media_type=MediaType.IMAGE,
        image=image_upload(),
        status=PublicationStatus.DRAFT,
    )

    with override_settings(MEDIA_ROOT=tmp_path):
        with pytest.raises(ValidationError) as error:
            media.save()

    assert "content_type" in error.value.message_dict


@pytest.mark.django_db
def test_fe_media_001_selling_point_inline_formset_saves_new_media(tmp_path):
    variety = make_variety()
    selling_point = SellingPoint.objects.create(
        variety=variety,
        title="后台内联卖点",
        slug="admin-inline-point",
        status=PublicationStatus.DRAFT,
    )
    formset_class = generic_inlineformset_factory(
        MediaAsset,
        formset=MediaAssetInlineFormSet,
        fields=("media_type", "title", "image", "alt_text", "is_cover", "status"),
        extra=1,
    )
    prefix = formset_class.get_default_prefix()
    data = {
        f"{prefix}-TOTAL_FORMS": "1",
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
        f"{prefix}-0-media_type": MediaType.IMAGE,
        f"{prefix}-0-title": "卖点田间图",
        f"{prefix}-0-alt_text": "卖点田间表现",
        f"{prefix}-0-status": PublicationStatus.DRAFT,
    }
    files = {f"{prefix}-0-image": image_upload("selling-point.png")}
    formset = formset_class(
        data=data,
        files=files,
        instance=selling_point,
        prefix=prefix,
    )

    assert formset.is_valid(), formset.errors
    with override_settings(MEDIA_ROOT=tmp_path):
        saved_media = formset.save()

    assert len(saved_media) == 1
    assert saved_media[0].target == selling_point


@pytest.mark.django_db
def test_image_upload_generates_thumbnail_and_metadata(tmp_path):
    variety = make_variety()

    with override_settings(MEDIA_ROOT=tmp_path):
        media = media_for(variety, title="拔节期田间图", is_cover=True)
        media.save()
        media.refresh_from_db()

        assert media.thumbnail.name.endswith(".webp")
        assert media.thumbnail.storage.exists(media.thumbnail.name)
        assert media.file_size > 0
        assert media.mime_type == "image/png"
        assert len(media.checksum_sha256) == 64


@pytest.mark.django_db
def test_invalid_or_oversized_image_is_rejected(tmp_path):
    variety = make_variety()
    fake_image = SimpleUploadedFile("fake.jpg", b"not an image", content_type="image/jpeg")

    with override_settings(MEDIA_ROOT=tmp_path):
        with pytest.raises(ValidationError):
            media_for(variety, image=fake_image).save()

        oversized = SimpleUploadedFile(
            "large.jpg",
            b"0" * (MAX_IMAGE_BYTES + 1),
            content_type="image/jpeg",
        )
        with pytest.raises(ValidationError, match="10 MB"):
            media_for(variety, image=oversized).save()


@pytest.mark.django_db
def test_fe_media_001_accepts_jpeg_compatible_mpo_phone_photo(tmp_path):
    variety = make_variety()

    with override_settings(MEDIA_ROOT=tmp_path):
        media = media_for(variety, image=mpo_upload())
        media.save()
        media.refresh_from_db()

    assert media.image.name.endswith(".jpg")
    assert media.thumbnail.name.endswith(".webp")


@pytest.mark.django_db
def test_local_mp4_generates_metadata_and_renders_player(client, tmp_path):
    variety = make_variety()

    with override_settings(MEDIA_ROOT=tmp_path):
        media = MediaAsset.objects.create(
            content_type=ContentType.objects.get_for_model(variety),
            object_id=variety.pk,
            media_type=MediaType.LOCAL_VIDEO,
            title="本地田间视频",
            video_file=mp4_upload(),
            video_cover=image_upload("video-cover.png"),
            is_cover=True,
            status=PublicationStatus.PUBLISHED,
        )
        media.refresh_from_db()

        assert media.video_file_size > 0
        assert media.video_mime_type == "video/mp4"
        assert len(media.video_checksum_sha256) == 64
        assert media.thumbnail.name.endswith(".webp")

        response = client.get(variety.get_absolute_url())
        content = response.content.decode()
        assert '<video controls preload="metadata" playsinline' in content
        assert "data-video-maximize" in content
        assert media.video_file.url in content
        assert media.thumbnail.url in content
        assert "本地田间视频" in content


@pytest.mark.django_db
def test_adm_media_003_local_video_form_clears_stale_link_fields(tmp_path):
    variety = make_variety()
    content_type = ContentType.objects.get_for_model(variety)
    media = MediaAsset.objects.create(
        content_type=content_type,
        object_id=variety.pk,
        media_type=MediaType.VIDEO_LINK,
        title="原外部视频",
        video_platform=VideoPlatform.WECHAT_CHANNELS,
        video_url="https://weixin.qq.com/example",
        status=PublicationStatus.DRAFT,
    )
    form = MediaAssetAdminForm(
        data={
            "content_type": content_type.pk,
            "object_id": variety.pk,
            "media_type": MediaType.LOCAL_VIDEO,
            "title": "改为本地视频",
            "description": "",
            "alt_text": "",
            "video_platform": VideoPlatform.WECHAT_CHANNELS,
            "video_url": "",
            "captured_at": "",
            "sort_order": 100,
            "status": PublicationStatus.DRAFT,
        },
        files={"video_file": mp4_upload("local-replacement.mp4")},
        instance=media,
    )

    assert form.is_valid(), form.errors
    with override_settings(MEDIA_ROOT=tmp_path):
        saved_media = form.save()

    assert saved_media.media_type == MediaType.LOCAL_VIDEO
    assert saved_media.video_file.name.endswith(".mp4")
    assert saved_media.video_platform == ""
    assert saved_media.video_url == ""
    assert not saved_media.image


@pytest.mark.django_db
def test_invalid_and_oversized_local_video_is_rejected(tmp_path):
    variety = make_variety()
    invalid_video = SimpleUploadedFile("fake.mp4", b"not a video", content_type="video/mp4")

    with override_settings(MEDIA_ROOT=tmp_path):
        media = MediaAsset(
            content_type=ContentType.objects.get_for_model(variety),
            object_id=variety.pk,
            media_type=MediaType.LOCAL_VIDEO,
            video_file=invalid_video,
            status=PublicationStatus.DRAFT,
        )
        with pytest.raises(ValidationError, match="不是有效的 MP4"):
            media.save()

    class OversizedVideo(BytesIO):
        name = "large.mp4"
        size = MAX_VIDEO_BYTES + 1

    with pytest.raises(ValidationError, match="200 MB"):
        validate_mp4_upload(OversizedVideo())


@pytest.mark.django_db
def test_new_cover_demotes_previous_cover(tmp_path):
    variety = make_variety()

    with override_settings(MEDIA_ROOT=tmp_path):
        first = media_for(variety, title="第一张", is_cover=True)
        first.save()
        second = media_for(
            variety,
            title="第二张",
            image=image_upload("second.png", (190, 145, 50)),
            is_cover=True,
        )
        second.full_clean()
        second.save()
        first.refresh_from_db()

        assert first.is_cover is False
        assert second.is_cover is True
        assert MediaAsset.objects.filter(is_cover=True).count() == 1


@pytest.mark.django_db
def test_inline_multiple_covers_returns_clear_business_error(tmp_path):
    variety = make_variety()
    formset_class = generic_inlineformset_factory(
        MediaAsset,
        formset=MediaAssetInlineFormSet,
        fields=("media_type", "title", "image", "alt_text", "is_cover", "status"),
        extra=2,
    )
    prefix = formset_class.get_default_prefix()
    data = {
        f"{prefix}-TOTAL_FORMS": "2",
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
        f"{prefix}-0-media_type": MediaType.IMAGE,
        f"{prefix}-0-title": "苗期图片",
        f"{prefix}-0-alt_text": "苗期田间图片",
        f"{prefix}-0-is_cover": "on",
        f"{prefix}-0-status": PublicationStatus.DRAFT,
        f"{prefix}-1-media_type": MediaType.IMAGE,
        f"{prefix}-1-title": "成熟期图片",
        f"{prefix}-1-alt_text": "成熟期田间图片",
        f"{prefix}-1-is_cover": "on",
        f"{prefix}-1-status": PublicationStatus.DRAFT,
    }
    files = {
        f"{prefix}-0-image": image_upload("seedling.png"),
        f"{prefix}-1-image": image_upload("maturity.png", (190, 145, 50)),
    }

    with override_settings(MEDIA_ROOT=tmp_path):
        formset = formset_class(data=data, files=files, instance=variety, prefix=prefix)

        assert formset.is_valid() is False
        error_text = " ".join(formset.non_form_errors())
        assert "当前同时选择了多张封面" in error_text
        assert "请只勾选一条“设为封面”" in error_text


@pytest.mark.django_db
def test_deleting_media_removes_original_and_thumbnail(tmp_path):
    variety = make_variety()

    with override_settings(MEDIA_ROOT=tmp_path):
        media = media_for(variety)
        media.save()
        image_name = media.image.name
        thumbnail_name = media.thumbnail.name
        storage = media.image.storage

        MediaAsset.objects.filter(pk=media.pk).delete()

        assert storage.exists(image_name) is False
        assert storage.exists(thumbnail_name) is False


@pytest.mark.django_db
def test_deleting_local_video_removes_video_and_cover_files(tmp_path):
    variety = make_variety()

    with override_settings(MEDIA_ROOT=tmp_path):
        media = MediaAsset.objects.create(
            content_type=ContentType.objects.get_for_model(variety),
            object_id=variety.pk,
            media_type=MediaType.LOCAL_VIDEO,
            video_file=mp4_upload("delete-me.mp4"),
            video_cover=image_upload("delete-cover.png"),
            status=PublicationStatus.DRAFT,
        )
        media.refresh_from_db()
        video_name = media.video_file.name
        cover_name = media.video_cover.name
        thumbnail_name = media.thumbnail.name
        storage = media.video_file.storage

        MediaAsset.objects.filter(pk=media.pk).delete()

        assert storage.exists(video_name) is False
        assert storage.exists(cover_name) is False
        assert storage.exists(thumbnail_name) is False


@pytest.mark.django_db
def test_video_link_requires_platform_and_safe_url():
    variety = make_variety()
    content_type = ContentType.objects.get_for_model(variety)
    video = MediaAsset(
        content_type=content_type,
        object_id=variety.pk,
        media_type=MediaType.VIDEO_LINK,
        video_url="javascript:alert(1)",
        status=PublicationStatus.PUBLISHED,
    )

    with pytest.raises(ValidationError) as error:
        video.save()

    assert "video_platform" in error.value.message_dict
    assert "video_url" in error.value.message_dict


@pytest.mark.django_db
def test_public_page_shows_published_media_and_hides_drafts(client, tmp_path):
    variety = make_variety()

    with override_settings(MEDIA_ROOT=tmp_path):
        media_for(variety, title="公开田间图").save()
        media_for(
            variety,
            title="内部待审图",
            image=image_upload("draft.png"),
            status=PublicationStatus.DRAFT,
            alt_text="",
        ).save()
        MediaAsset.objects.create(
            content_type=ContentType.objects.get_for_model(variety),
            object_id=variety.pk,
            media_type=MediaType.VIDEO_LINK,
            title="公开视频",
            video_platform=VideoPlatform.DOUYIN,
            video_url="https://www.douyin.com/video/example",
            status=PublicationStatus.PUBLISHED,
        )

        response = client.get(variety.get_absolute_url())
        content = response.content.decode()

        assert response.status_code == 200
        assert "公开田间图" in content
        assert "内部待审图" not in content
        assert "公开视频" in content
        assert "https://www.douyin.com/video/example" in content
