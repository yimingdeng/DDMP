import uuid
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from core.models import PublicationStatus
from inquiries.models import source_code_validator
from sites.models import DemoSite
from varieties.models import Variety


class QRTargetType(models.TextChoices):
    HOME = "home", "首页"
    VARIETY = "variety", "品种详情"
    SITE = "site", "示范点详情"
    CONTACT = "contact", "咨询表单"


class ChannelQRCode(models.Model):
    name = models.CharField("二维码名称", max_length=100)
    token = models.UUIDField("访问标识", default=uuid.uuid4, unique=True, editable=False)
    target_type = models.CharField("目标类型", max_length=20, choices=QRTargetType.choices)
    variety = models.ForeignKey(
        Variety,
        verbose_name="目标品种",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="channel_qr_codes",
    )
    demo_site = models.ForeignKey(
        DemoSite,
        verbose_name="目标示范点",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="channel_qr_codes",
    )
    source_code = models.CharField(
        "来源代码",
        max_length=40,
        unique=True,
        validators=[source_code_validator],
        help_text="例如 wechat_moments、douyin_profile、henan_field_sign。",
    )
    purpose = models.CharField("用途说明", max_length=200, blank=True)
    is_active = models.BooleanField("启用", default=True)
    scan_count = models.PositiveBigIntegerField("扫码次数", default=0, editable=False)
    last_scanned_at = models.DateTimeField("最近扫码时间", null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="created_channel_qr_codes",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "渠道二维码"
        verbose_name_plural = "渠道二维码"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.name} · {self.source_code}"

    def clean(self):
        super().clean()
        errors = {}
        if self.target_type == QRTargetType.VARIETY:
            self.demo_site = None
            if not self.variety_id:
                errors["variety"] = "品种详情二维码必须选择目标品种。"
        elif self.target_type == QRTargetType.SITE:
            self.variety = None
            if not self.demo_site_id:
                errors["demo_site"] = "示范点详情二维码必须选择目标示范点。"
        elif self.target_type in {QRTargetType.HOME, QRTargetType.CONTACT}:
            self.variety = None
            self.demo_site = None
        else:
            errors["target_type"] = "请选择有效的二维码目标类型。"
        if errors:
            raise ValidationError(errors)

    @property
    def target_label(self):
        if self.target_type == QRTargetType.VARIETY and self.variety:
            return str(self.variety)
        if self.target_type == QRTargetType.SITE and self.demo_site:
            return str(self.demo_site)
        return self.get_target_type_display()

    def target_is_available(self):
        if self.target_type == QRTargetType.VARIETY:
            return bool(self.variety and self.variety.status == PublicationStatus.PUBLISHED)
        if self.target_type == QRTargetType.SITE:
            return bool(
                self.demo_site
                and self.demo_site.status == PublicationStatus.PUBLISHED
                and self.demo_site.variety.status == PublicationStatus.PUBLISHED
            )
        return True

    def get_target_url(self):
        if self.target_type == QRTargetType.VARIETY:
            path = self.variety.get_absolute_url()
            fragment = ""
        elif self.target_type == QRTargetType.SITE:
            path = self.demo_site.get_absolute_url()
            fragment = ""
        elif self.target_type == QRTargetType.CONTACT:
            path = reverse("core:home")
            fragment = "#contact"
        else:
            path = reverse("core:home")
            fragment = ""
        return f"{path}?{urlencode({'source': self.source_code})}{fragment}"

    def get_scan_path(self):
        return reverse("campaigns:scan", kwargs={"token": self.token})
