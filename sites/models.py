from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.urls import reverse

from core.models import PublicationStatus, PublishableModel
from varieties.models import Variety


class Region(models.TextChoices):
    NORTHEAST = "northeast", "东北"
    HUANG_HUAI_HAI = "huang_huai_hai", "黄淮海"
    NORTHWEST = "northwest", "西北"
    SOUTHWEST = "southwest", "西南"
    OTHER = "other", "其他"


class GrowthStage(models.TextChoices):
    SOWING = "sowing", "播种"
    EMERGENCE = "emergence", "出苗"
    JOINTING = "jointing", "拔节"
    FLOWERING = "flowering", "抽雄吐丝"
    FILLING = "filling", "灌浆"
    MATURITY = "maturity", "成熟"
    HARVEST = "harvest", "收获"


class VisitingStatus(models.TextChoices):
    NOT_OPEN = "not_open", "暂不开放"
    OPEN = "open", "可预约看田"
    CLOSED = "closed", "已结束"


class DemoSite(PublishableModel):
    media_assets = GenericRelation(
        "media_assets.MediaAsset",
        related_query_name="demo_site_target",
    )
    name = models.CharField("示范点名称", max_length=100)
    slug = models.SlugField("URL 标识", max_length=120, unique=True)
    variety = models.ForeignKey(
        Variety,
        verbose_name="所属品种",
        on_delete=models.PROTECT,
        related_name="demo_sites",
    )
    region = models.CharField("区域", max_length=30, choices=Region.choices)
    province = models.CharField("省份", max_length=50)
    city = models.CharField("城市", max_length=50)
    county = models.CharField("区县", max_length=50)
    township_village = models.CharField("乡镇/村", max_length=100, blank=True)
    detailed_address = models.CharField("详细地址", max_length=200, blank=True)
    latitude = models.DecimalField(
        "地图纬度",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text="高德地图 GCJ-02 纬度，例如 34.746600。",
    )
    longitude = models.DecimalField(
        "地图经度",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text="高德地图 GCJ-02 经度，例如 113.625400。",
    )
    show_township = models.BooleanField("公开乡镇/村", default=True)
    show_detailed_address = models.BooleanField("公开详细地址", default=False)
    area_mu = models.DecimalField(
        "示范面积（亩）", max_digits=10, decimal_places=2, null=True, blank=True
    )
    sowing_date = models.DateField("播种日期", null=True, blank=True)
    planting_density = models.PositiveIntegerField("种植密度（株/亩）", null=True, blank=True)
    planting_mode = models.CharField("种植模式", max_length=100, blank=True)
    current_stage = models.CharField(
        "当前阶段",
        max_length=30,
        choices=GrowthStage.choices,
        blank=True,
    )
    main_performance = models.CharField("主要表现", max_length=120, blank=True)
    description = models.TextField("详细介绍", blank=True)
    is_featured = models.BooleanField("首页推荐", default=False)
    visiting_status = models.CharField(
        "参观状态",
        max_length=20,
        choices=VisitingStatus.choices,
        default=VisitingStatus.NOT_OPEN,
    )
    visiting_note = models.CharField("预约提示", max_length=200, blank=True)
    sort_order = models.PositiveIntegerField(
        "展示顺序",
        default=100,
        help_text="数字越小越靠前；相同数字再按省份、城市和名称排列。",
    )
    internal_owner = models.CharField("内部负责人", max_length=100, blank=True)
    internal_notes = models.TextField("内部备注", blank=True)

    class Meta:
        verbose_name = "示范点"
        verbose_name_plural = "示范点"
        ordering = ("sort_order", "province", "city", "name")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("sites:detail", kwargs={"slug": self.slug})

    def clean(self):
        super().clean()
        if self.area_mu is not None and self.area_mu <= 0:
            raise ValidationError({"area_mu": "示范面积必须大于 0。"})
        if self.status == PublicationStatus.PUBLISHED:
            errors = {}
            if not self.main_performance.strip():
                errors["main_performance"] = "发布示范点前必须填写主要表现。"
            if not self.description.strip():
                errors["description"] = "发布示范点前必须填写详细介绍。"
            if errors:
                raise ValidationError(errors)

    @property
    def public_location(self):
        parts = [self.province, self.city, self.county]
        if self.show_township and self.township_village:
            parts.append(self.township_village)
        if self.show_detailed_address and self.detailed_address:
            parts.append(self.detailed_address)
        return " ".join(part for part in parts if part)


phone_validator = RegexValidator(r"^1[3-9]\d{9}$", "请输入正确的中国大陆手机号。")


class Contact(models.Model):
    name = models.CharField("姓名", max_length=50)
    role_title = models.CharField("职位/角色", max_length=50, blank=True)
    region = models.CharField("覆盖区域", max_length=100, blank=True)
    phone = models.CharField("手机号", max_length=20, validators=[phone_validator])
    enterprise_wechat_note = models.CharField("企业微信说明", max_length=200, blank=True)
    sites = models.ManyToManyField(
        DemoSite, verbose_name="关联示范点", related_name="contacts", blank=True
    )
    show_name = models.BooleanField("公开姓名", default=False)
    show_phone = models.BooleanField("公开电话", default=False)
    is_active = models.BooleanField("启用", default=True)
    sort_order = models.PositiveIntegerField("排序", default=100)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "联系人"
        verbose_name_plural = "联系人"
        ordering = ("sort_order", "name")

    def __str__(self):
        return f"{self.name} · {self.region or self.role_title}"
