from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from core.models import PublicationStatus, PublishableModel


class SellingPointType(models.TextChoices):
    YIELD = "yield", "高产潜力"
    LODGING = "lodging", "抗倒伏"
    DISEASE = "disease", "抗病性"
    DEHYDRATION = "dehydration", "脱水快"
    QUALITY = "quality", "商品性"
    OTHER = "other", "其他"


class Variety(PublishableModel):
    media_assets = GenericRelation(
        "media_assets.MediaAsset",
        related_query_name="variety_target",
    )
    name = models.CharField("品种名称", max_length=100, unique=True)
    slug = models.SlugField("URL 标识", max_length=120, unique=True)
    positioning = models.CharField("一句话定位", max_length=100, blank=True)
    summary = models.TextField("品种简介", blank=True)
    approval_number = models.CharField("审定编号", max_length=100, blank=True)
    suitable_area = models.TextField("适宜区域", blank=True)
    maturity = models.CharField("熟期", max_length=50, blank=True)
    plant_type = models.CharField("株型", max_length=50, blank=True)
    ear_type = models.CharField("穗型", max_length=50, blank=True)
    grain_type = models.CharField("籽粒类型", max_length=50, blank=True)
    density_min = models.PositiveIntegerField("适宜密度下限（株/亩）", null=True, blank=True)
    density_max = models.PositiveIntegerField("适宜密度上限（株/亩）", null=True, blank=True)
    sowing_advice = models.TextField("播期建议", blank=True)
    water_fertilizer_management = models.TextField("水肥管理", blank=True)
    cultivation_points = models.TextField("栽培要点", blank=True)
    risk_warning = models.TextField("风险提示", blank=True)
    is_featured = models.BooleanField("首页推荐", default=True)
    sort_order = models.PositiveIntegerField("排序", default=100)
    internal_notes = models.TextField("内部备注", blank=True)

    class Meta:
        verbose_name = "品种"
        verbose_name_plural = "品种"
        ordering = ("sort_order", "-published_at", "name")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("varieties:detail", kwargs={"slug": self.slug})

    def clean(self):
        super().clean()
        errors = {}
        if self.density_min and self.density_max and self.density_min > self.density_max:
            errors["density_max"] = "密度上限不能小于下限。"
        if self.status == PublicationStatus.PUBLISHED:
            if not self.positioning.strip():
                errors["positioning"] = "发布品种前必须填写一句话定位。"
            if not self.summary.strip():
                errors["summary"] = "发布品种前必须填写品种简介。"
        if errors:
            raise ValidationError(errors)

    @property
    def density_display(self):
        if self.density_min and self.density_max:
            return f"{self.density_min}—{self.density_max} 株/亩"
        if self.density_min:
            return f"不少于 {self.density_min} 株/亩"
        if self.density_max:
            return f"不高于 {self.density_max} 株/亩"
        return ""


class SellingPoint(PublishableModel):
    media_assets = GenericRelation(
        "media_assets.MediaAsset",
        related_query_name="selling_point_target",
    )
    variety = models.ForeignKey(
        Variety,
        verbose_name="所属品种",
        on_delete=models.CASCADE,
        related_name="selling_points",
    )
    title = models.CharField("标题", max_length=50)
    slug = models.SlugField("URL 标识", max_length=80)
    point_type = models.CharField(
        "卖点类型",
        max_length=30,
        choices=SellingPointType.choices,
        default=SellingPointType.OTHER,
    )
    short_description = models.CharField("简短描述", max_length=120, blank=True)
    detail = models.TextField("详细说明", blank=True)
    data_note = models.TextField("数据说明", blank=True)
    sort_order = models.PositiveIntegerField("排序", default=100)
    internal_basis = models.TextField("内部依据", blank=True)

    class Meta:
        verbose_name = "核心卖点"
        verbose_name_plural = "核心卖点"
        ordering = ("sort_order", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("variety", "slug"),
                name="unique_selling_point_slug_per_variety",
            )
        ]

    def __str__(self):
        return f"{self.variety.name} · {self.title}"

    def get_absolute_url(self):
        return reverse(
            "varieties:selling-point-detail",
            kwargs={"variety_slug": self.variety.slug, "slug": self.slug},
        )

    def clean(self):
        super().clean()
        if self.status == PublicationStatus.PUBLISHED and not self.short_description.strip():
            raise ValidationError({"short_description": "发布卖点前必须填写简短描述。"})
