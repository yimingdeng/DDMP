import hashlib
import uuid
from io import BytesIO
from pathlib import Path

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import URLValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from PIL import Image, ImageOps

from core.models import PublicationStatus, PublishableModel

from .validators import validate_image_upload, validate_mp4_upload


class MediaType(models.TextChoices):
    IMAGE = "image", "图片"
    VIDEO_LINK = "video_link", "视频链接"
    LOCAL_VIDEO = "local_video", "本地视频"


class VideoPlatform(models.TextChoices):
    DOUYIN = "douyin", "抖音"
    WECHAT_CHANNELS = "wechat_channels", "微信视频号"
    OTHER = "other", "其他"


def media_upload_path(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"media/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{suffix}"


def thumbnail_upload_path(instance, filename):
    return f"media/thumbnails/{uuid.uuid4().hex}.webp"


def video_upload_path(instance, filename):
    return f"media/videos/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.mp4"


class MediaAsset(PublishableModel):
    content_type = models.ForeignKey(ContentType, verbose_name="关联类型", on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField("关联对象 ID")
    target = GenericForeignKey("content_type", "object_id")

    media_type = models.CharField("媒体类型", max_length=20, choices=MediaType.choices)
    title = models.CharField("标题", max_length=100, blank=True)
    description = models.TextField("说明", max_length=500, blank=True)
    alt_text = models.CharField("替代文本", max_length=160, blank=True)

    image = models.ImageField(
        "图片",
        upload_to=media_upload_path,
        validators=[validate_image_upload],
        blank=True,
        help_text="仅供“图片”类型使用；视频类型请将此字段留空。",
    )
    video_platform = models.CharField(
        "视频平台",
        max_length=30,
        choices=VideoPlatform.choices,
        blank=True,
    )
    video_url = models.URLField(
        "视频链接",
        max_length=500,
        validators=[URLValidator(schemes=("http", "https"))],
        blank=True,
    )
    video_file = models.FileField(
        "本地 MP4 视频",
        upload_to=video_upload_path,
        validators=[validate_mp4_upload],
        blank=True,
        help_text="仅供“本地视频”类型使用；最大 200 MB，建议使用 H.264 + AAC 编码。",
    )
    video_cover = models.ImageField(
        "视频封面",
        upload_to=media_upload_path,
        validators=[validate_image_upload],
        blank=True,
        help_text="供“视频链接”或“本地视频”使用；可上传 JPEG、PNG 或 WebP 封面图。",
    )
    thumbnail = models.ImageField(
        "缩略图",
        upload_to=thumbnail_upload_path,
        blank=True,
        editable=False,
    )
    captured_at = models.DateField("拍摄日期", null=True, blank=True)
    is_cover = models.BooleanField("设为封面", default=False)
    sort_order = models.PositiveIntegerField("排序", default=100)

    file_size = models.PositiveBigIntegerField("文件大小", null=True, blank=True, editable=False)
    mime_type = models.CharField("MIME 类型", max_length=100, blank=True, editable=False)
    checksum_sha256 = models.CharField("SHA-256", max_length=64, blank=True, editable=False)
    video_file_size = models.PositiveBigIntegerField(
        "视频文件大小", null=True, blank=True, editable=False
    )
    video_mime_type = models.CharField("视频 MIME 类型", max_length=100, blank=True, editable=False)
    video_checksum_sha256 = models.CharField(
        "视频 SHA-256", max_length=64, blank=True, editable=False
    )

    class Meta:
        verbose_name = "媒体素材"
        verbose_name_plural = "媒体素材"
        ordering = ("sort_order", "created_at")
        indexes = [models.Index(fields=("content_type", "object_id", "status"))]
        constraints = [
            models.UniqueConstraint(
                fields=("content_type", "object_id"),
                condition=Q(is_cover=True),
                name="one_cover_per_media_target",
                violation_error_message=(
                    "同一品种、核心卖点或示范点只能设置一张封面；"
                    "请取消其他媒体素材的“设为封面”后再保存。"
                ),
            )
        ]

    def __str__(self):
        target_name = str(self.target) if self.target else f"对象 {self.object_id}"
        return self.title or f"{target_name} · {self.get_media_type_display()}"

    @property
    def target_label(self):
        return str(self.target) if self.target else "关联对象不存在"

    @property
    def display_image(self):
        if self.thumbnail:
            return self.thumbnail
        if self.media_type == MediaType.IMAGE and self.image:
            return self.image
        if self.media_type in {MediaType.VIDEO_LINK, MediaType.LOCAL_VIDEO} and self.video_cover:
            return self.video_cover
        return None

    @property
    def original_image_url(self):
        if self.media_type == MediaType.IMAGE and self.image:
            return self.image.url
        if self.video_cover:
            return self.video_cover.url
        return ""

    def clean(self):
        super().clean()
        errors = {}
        allowed_targets = {
            ("varieties", "variety"),
            ("varieties", "sellingpoint"),
            ("sites", "demosite"),
        }
        content_type = None
        if self.content_type_id:
            content_type = ContentType.objects.filter(pk=self.content_type_id).first()
            if content_type is None:
                errors["content_type"] = "关联类型不存在。"
            elif content_type.natural_key() not in allowed_targets:
                errors["content_type"] = "媒体只能关联品种、核心卖点或示范点。"
        if content_type is not None and self.object_id:
            target_model = content_type.model_class()
            target = (
                target_model._default_manager.filter(pk=self.object_id).first()
                if target_model is not None
                else None
            )
            if target is None:
                errors["object_id"] = "关联对象不存在。"
            else:
                # GenericInlineFormSet assigns content_type_id/object_id after
                # ModelForm validation, which may have cached target=None (or an
                # old target). Keep the GenericForeignKey cache in sync with the
                # IDs that were actually validated against the database.
                self._meta.get_field("target").set_cached_value(self, target)

        if self.media_type == MediaType.IMAGE:
            if not self.image:
                errors["image"] = "图片类型必须上传图片。"
            if self.video_url or self.video_file or self.video_cover or self.video_platform:
                errors["media_type"] = "图片类型不能填写视频字段。"
            if self.status == PublicationStatus.PUBLISHED and not self.alt_text.strip():
                errors["alt_text"] = "发布图片前必须填写替代文本。"
        elif self.media_type == MediaType.VIDEO_LINK:
            if not self.video_url:
                errors["video_url"] = "视频链接类型必须填写链接。"
            if not self.video_platform:
                errors["video_platform"] = "请选择视频平台。"
            if self.image or self.video_file:
                errors["media_type"] = "视频链接类型不能上传普通图片或本地视频文件。"
        elif self.media_type == MediaType.LOCAL_VIDEO:
            if not self.video_file:
                errors["video_file"] = "本地视频类型必须上传 MP4 文件。"
            if self.image or self.video_url or self.video_platform:
                errors["media_type"] = "本地视频类型不能填写普通图片、视频平台或外部链接。"
        else:
            errors["media_type"] = "请选择媒体类型。"

        if (
            self.is_cover
            and self.media_type in {MediaType.VIDEO_LINK, MediaType.LOCAL_VIDEO}
            and not self.video_cover
        ):
            errors["video_cover"] = "视频设为封面时必须上传视频封面。"
        if errors:
            raise ValidationError(errors)

    def validate_constraints(self, exclude=None):
        # A new standalone cover intentionally replaces the old one in save().
        # Skip the conditional cover constraint during ModelForm validation so
        # that replacement can happen before the database constraint is checked.
        constraint_exclusions = set(exclude or ())
        if self.is_cover:
            constraint_exclusions.add("is_cover")
        super().validate_constraints(exclude=constraint_exclusions)

    def save(self, *args, **kwargs):
        # The cover constraint is enforced atomically by the database after the
        # previous cover is demoted below. Validate fields and business rules first.
        self.full_clean(validate_constraints=False)
        previous_files = self._previous_file_names()
        if self.is_cover and self.content_type_id and self.object_id:
            type(self).objects.filter(
                content_type_id=self.content_type_id,
                object_id=self.object_id,
                is_cover=True,
            ).exclude(pk=self.pk).update(is_cover=False)

        source = self._source_file()
        source_changed = source and source.name not in previous_files
        video_changed = self.video_file and self.video_file.name not in previous_files
        if source_changed:
            self.thumbnail = ""
        if not self.video_file:
            self.video_file_size = None
            self.video_mime_type = ""
            self.video_checksum_sha256 = ""
        super().save(*args, **kwargs)

        if source and (source_changed or not self.thumbnail):
            self._generate_thumbnail_and_metadata(source)
        if self.video_file and (video_changed or not self.video_checksum_sha256):
            self._generate_video_metadata()
        self._delete_replaced_files(previous_files)

    def _source_file(self):
        if self.media_type == MediaType.IMAGE and self.image:
            return self.image
        if self.media_type in {MediaType.VIDEO_LINK, MediaType.LOCAL_VIDEO} and self.video_cover:
            return self.video_cover
        return None

    def _previous_file_names(self):
        if not self.pk:
            return set()
        previous = (
            type(self)
            .objects.filter(pk=self.pk)
            .values("image", "video_file", "video_cover", "thumbnail")
            .first()
        )
        return {name for name in (previous or {}).values() if name}

    def _generate_thumbnail_and_metadata(self, source):
        source.open("rb")
        raw = source.read()
        source.close()
        image = Image.open(BytesIO(raw))
        detected_format = image.format or ""
        image = ImageOps.exif_transpose(image)
        image.thumbnail((800, 800), Image.Resampling.LANCZOS)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")

        output = BytesIO()
        image.save(output, format="WEBP", quality=82, method=6)
        output.seek(0)
        thumbnail_name = f"{uuid.uuid4().hex}.webp"
        self.thumbnail.save(thumbnail_name, ContentFile(output.read()), save=False)

        self.file_size = len(raw)
        self.mime_type = Image.MIME.get(detected_format, "")
        self.checksum_sha256 = hashlib.sha256(raw).hexdigest()
        type(self).objects.filter(pk=self.pk).update(
            thumbnail=self.thumbnail.name,
            file_size=self.file_size,
            mime_type=self.mime_type,
            checksum_sha256=self.checksum_sha256,
        )

    def _generate_video_metadata(self):
        self.video_file.open("rb")
        checksum = hashlib.sha256()
        for chunk in iter(lambda: self.video_file.read(1024 * 1024), b""):
            checksum.update(chunk)
        self.video_file.close()
        self.video_file_size = self.video_file.size
        self.video_mime_type = "video/mp4"
        self.video_checksum_sha256 = checksum.hexdigest()
        type(self).objects.filter(pk=self.pk).update(
            video_file_size=self.video_file_size,
            video_mime_type=self.video_mime_type,
            video_checksum_sha256=self.video_checksum_sha256,
        )

    def _delete_replaced_files(self, previous_names):
        current_names = {
            field.name
            for field in (self.image, self.video_file, self.video_cover, self.thumbnail)
            if field
        }
        for old_name in previous_names - current_names:
            self.image.storage.delete(old_name)
