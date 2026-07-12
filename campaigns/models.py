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


class MarketingPackageStatus(models.TextChoices):
    GENERATED = "generated", "待审核"
    READY = "ready", "可发布"
    PUBLISHED = "published", "已登记发布"
    DISABLED = "disabled", "已停用"


class PromoterType(models.TextChoices):
    SALES = "sales", "销售人员"
    DEALER = "dealer", "经销商"
    SITE_OWNER = "site_owner", "示范点负责人"


class DistributionChannel(models.TextChoices):
    WECHAT_MOMENTS = "wechat_moments", "微信朋友圈"
    WECHAT_GROUP = "wechat_group", "微信群"
    WECHAT_CHANNELS = "wechat_channels", "微信视频号"
    DOUYIN_VIDEO = "douyin_video", "抖音短视频"
    DOUYIN_LIVE = "douyin_live", "抖音直播"
    FIELD_QRCODE = "field_qrcode", "田间二维码"


LEGACY_DISTRIBUTION_CHANNEL_LABELS = {
    "sales_share": "销售转发（历史来源）",
    "dealer_share": "经销商转发（历史来源）",
}


def get_distribution_channel_label(value):
    return dict(DistributionChannel.choices).get(
        value, LEGACY_DISTRIBUTION_CHANNEL_LABELS.get(value, value)
    )


def get_distribution_channel_label_map():
    return {
        **dict(DistributionChannel.choices),
        **LEGACY_DISTRIBUTION_CHANNEL_LABELS,
    }


class ExternalPublicationStatus(models.TextChoices):
    DRAFT = "draft", "待发布"
    PUBLISHED = "published", "已发布"
    ARCHIVED = "archived", "已归档"


class PosterVariantType(models.TextChoices):
    MOMENTS = "moments", "朋友圈图文海报"
    DEALER = "dealer", "经销商专属海报"
    FIELD_DAY = "field_day", "观摩会/看田邀请"
    WEEKLY_RECOMMENDATION = "weekly_recommendation", "本周重点推荐"


class PromotionIdentity(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="登录账号",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="promotion_identity",
        help_text="绑定后，该账号可登录营销发布中心获取专属链接和二维码。",
    )
    name = models.CharField("推广人名称", max_length=100)
    code = models.SlugField("内部代码", max_length=50, unique=True)
    promoter_type = models.CharField("推广身份", max_length=20, choices=PromoterType.choices)
    region = models.CharField("所属区域", max_length=100, blank=True)
    public_token = models.UUIDField("公开标识", default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField("有效", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "推广身份"
        verbose_name_plural = "推广身份"
        ordering = ("region", "name")

    def __str__(self):
        return f"{self.name} · {self.get_promoter_type_display()}"


def marketing_poster_path(instance, filename):
    return f"marketing/posters/{instance.public_token}.png"


def marketing_video_cover_path(instance, filename):
    return f"marketing/video-covers/{instance.public_token}.jpg"


def marketing_poster_variant_path(instance, filename):
    return f"marketing/poster-variants/{instance.public_token}.png"


class MarketingPackage(models.Model):
    published_observation = models.OneToOneField(
        "collection.PublishedObservation",
        verbose_name="公开阶段快照",
        on_delete=models.PROTECT,
        related_name="marketing_package",
    )
    public_token = models.UUIDField("内容标识", default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        "状态",
        max_length=20,
        choices=MarketingPackageStatus.choices,
        default=MarketingPackageStatus.GENERATED,
        db_index=True,
    )
    headline = models.CharField("传播标题", max_length=160)
    core_tags = models.JSONField("核心表现标签", default=list, blank=True)
    wechat_moments_copy = models.TextField("朋友圈文案", max_length=1000, blank=True)
    customer_private_copy = models.TextField("客户私聊文案", max_length=1000, blank=True)
    wechat_group_copy = models.TextField("微信群文案", max_length=1000, blank=True)
    wechat_channels_title = models.CharField("视频号标题", max_length=100, blank=True)
    wechat_channels_copy = models.TextField("视频号文案", max_length=1000, blank=True)
    douyin_title = models.CharField("抖音标题", max_length=100, blank=True)
    douyin_topics = models.CharField("抖音话题", max_length=300, blank=True)
    short_video_script = models.TextField("短视频脚本", max_length=2000, blank=True)
    poster = models.ImageField("朋友圈海报", upload_to=marketing_poster_path, blank=True)
    video_cover = models.ImageField("短视频封面", upload_to=marketing_video_cover_path, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="审核人",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="reviewed_marketing_packages",
    )
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True, editable=False)
    published_at = models.DateTimeField("登记发布时间", null=True, blank=True, editable=False)
    generated_at = models.DateTimeField("生成时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "营销素材包"
        verbose_name_plural = "营销素材包"
        ordering = ("-generated_at",)

    def __str__(self):
        return self.headline

    def get_absolute_url(self):
        return reverse(
            "sites:stage-content-detail",
            kwargs={
                "slug": self.observation.site.slug,
                "stage": self.observation.stage,
                "content_token": self.public_token,
            },
        )

    @property
    def observation(self):
        return self.published_observation.observation

    def is_publicly_available(self):
        observation = self.observation
        return bool(
            self.status in {MarketingPackageStatus.READY, MarketingPackageStatus.PUBLISHED}
            and observation.site.status == PublicationStatus.PUBLISHED
            and observation.site.variety.status == PublicationStatus.PUBLISHED
        )


class ShortVideoTopic(models.Model):
    marketing_package = models.ForeignKey(
        MarketingPackage,
        verbose_name="营销素材包",
        on_delete=models.CASCADE,
        related_name="short_video_topics",
    )
    title = models.CharField("选题标题", max_length=120)
    focus = models.CharField("单一重点", max_length=80)
    script = models.TextField("口播脚本", max_length=1200)
    sort_order = models.PositiveIntegerField("排序", default=100)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "短视频选题"
        verbose_name_plural = "短视频选题"
        ordering = ("sort_order", "id")

    def __str__(self):
        return self.title


class MarketingPosterVariant(models.Model):
    marketing_package = models.ForeignKey(
        MarketingPackage,
        verbose_name="营销素材包",
        on_delete=models.CASCADE,
        related_name="poster_variants",
    )
    variant_type = models.CharField("模板类型", max_length=40, choices=PosterVariantType.choices)
    public_token = models.UUIDField("公开标识", default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField("海报标题", max_length=120)
    subtitle = models.CharField("海报副标题", max_length=180, blank=True)
    call_to_action = models.CharField("行动提示", max_length=80, default="扫码查看完整表现")
    promoter = models.ForeignKey(
        PromotionIdentity,
        verbose_name="专属推广人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="poster_variants",
    )
    tracked_link = models.ForeignKey(
        "campaigns.TrackedLink",
        verbose_name="专属追踪链接",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="poster_variants",
    )
    image = models.ImageField("海报图片", upload_to=marketing_poster_variant_path, blank=True)
    is_active = models.BooleanField("启用", default=True)
    generated_at = models.DateTimeField("生成时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "营销海报模板"
        verbose_name_plural = "营销海报模板"
        ordering = ("variant_type", "-updated_at")

    def __str__(self):
        return f"{self.get_variant_type_display()} · {self.title}"


class ExternalPublication(models.Model):
    marketing_package = models.ForeignKey(
        MarketingPackage,
        verbose_name="营销素材包",
        on_delete=models.CASCADE,
        related_name="external_publications",
    )
    channel = models.CharField("发布渠道", max_length=40, choices=DistributionChannel.choices)
    status = models.CharField(
        "发布状态",
        max_length=20,
        choices=ExternalPublicationStatus.choices,
        default=ExternalPublicationStatus.DRAFT,
        db_index=True,
    )
    title = models.CharField("发布标题", max_length=160)
    account_name = models.CharField("发布账号", max_length=100, blank=True)
    external_url = models.URLField("外部链接", max_length=500, blank=True)
    published_at = models.DateTimeField("发布时间", null=True, blank=True)
    view_count = models.PositiveBigIntegerField("播放/浏览量", default=0)
    like_count = models.PositiveBigIntegerField("点赞量", default=0)
    comment_count = models.PositiveBigIntegerField("评论量", default=0)
    share_count = models.PositiveBigIntegerField("转发量", default=0)
    notes = models.TextField("备注", max_length=1000, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="登记人",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="created_external_publications",
    )
    created_at = models.DateTimeField("登记时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "外部发布记录"
        verbose_name_plural = "外部发布记录"
        ordering = ("-published_at", "-created_at")
        indexes = [
            models.Index(fields=("channel", "status")),
            models.Index(fields=("published_at",)),
        ]

    def __str__(self):
        return f"{self.channel_label} · {self.title}"

    @property
    def channel_label(self):
        return get_distribution_channel_label(self.channel)

    @property
    def engagement_count(self):
        return self.like_count + self.comment_count + self.share_count


class MarketingWeeklyReport(models.Model):
    start_date = models.DateField("开始日期", db_index=True)
    end_date = models.DateField("结束日期", db_index=True)
    title = models.CharField("周报标题", max_length=160)
    summary = models.TextField("周报摘要", max_length=4000)
    recommended_actions = models.TextField("建议动作", max_length=2000, blank=True)
    is_archived = models.BooleanField("已归档", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="created_marketing_weekly_reports",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "营销周报"
        verbose_name_plural = "营销周报"
        ordering = ("-start_date",)
        constraints = [
            models.UniqueConstraint(fields=("start_date", "end_date"), name="unique_weekly_report")
        ]

    def __str__(self):
        return self.title


class TrackedLink(models.Model):
    token = models.UUIDField("访问标识", default=uuid.uuid4, unique=True, editable=False)
    marketing_package = models.ForeignKey(
        MarketingPackage,
        verbose_name="营销素材包",
        on_delete=models.CASCADE,
        related_name="tracked_links",
    )
    source_code = models.CharField(
        "渠道来源",
        max_length=40,
        validators=[source_code_validator],
        db_index=True,
    )
    promoter = models.ForeignKey(
        PromotionIdentity,
        verbose_name="推广人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tracked_links",
    )
    purpose = models.CharField("用途说明", max_length=200, blank=True)
    is_active = models.BooleanField("有效", default=True)
    click_count = models.PositiveBigIntegerField("访问次数", default=0, editable=False)
    last_clicked_at = models.DateTimeField("最近访问", null=True, blank=True, editable=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "传播追踪链接"
        verbose_name_plural = "传播追踪链接"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("marketing_package", "source_code", "promoter"),
                name="unique_package_source_promoter_link",
            )
        ]

    def __str__(self):
        return f"{self.marketing_package} · {self.source_code}"

    def get_scan_path(self):
        return reverse("campaigns:tracked-link", kwargs={"token": self.token})

    def get_share_path(self):
        version_source = getattr(self.marketing_package, "updated_at", None) or self.created_at
        if not version_source:
            return self.get_scan_path()
        version = version_source.strftime("%Y%m%d%H%M%S")
        return f"{self.get_scan_path()}?{urlencode({'v': version})}"


class QRTargetType(models.TextChoices):
    HOME = "home", "首页"
    VARIETY = "variety", "品种详情"
    SITE = "site", "示范点详情"
    STAGE = "stage", "示范阶段表现"
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
    published_observation = models.ForeignKey(
        "collection.PublishedObservation",
        verbose_name="目标阶段表现",
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
            self.published_observation = None
            if not self.variety_id:
                errors["variety"] = "品种详情二维码必须选择目标品种。"
        elif self.target_type == QRTargetType.SITE:
            self.variety = None
            self.published_observation = None
            if not self.demo_site_id:
                errors["demo_site"] = "示范点详情二维码必须选择目标示范点。"
        elif self.target_type == QRTargetType.STAGE:
            self.variety = None
            self.demo_site = None
            if not self.published_observation_id:
                errors["published_observation"] = "阶段表现二维码必须选择公开阶段快照。"
        elif self.target_type in {QRTargetType.HOME, QRTargetType.CONTACT}:
            self.variety = None
            self.demo_site = None
            self.published_observation = None
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
        if self.target_type == QRTargetType.STAGE and self.published_observation:
            return str(self.published_observation)
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
        if self.target_type == QRTargetType.STAGE:
            available = bool(
                self.published_observation
                and self.published_observation.observation.site.status
                == PublicationStatus.PUBLISHED
                and self.published_observation.observation.site.variety.status
                == PublicationStatus.PUBLISHED
            )
            if not available:
                return False
            try:
                return self.published_observation.marketing_package.is_publicly_available()
            except MarketingPackage.DoesNotExist:
                return True
        return True

    def get_target_url(self):
        if self.target_type == QRTargetType.VARIETY:
            path = self.variety.get_absolute_url()
            fragment = ""
        elif self.target_type == QRTargetType.SITE:
            path = self.demo_site.get_absolute_url()
            fragment = ""
        elif self.target_type == QRTargetType.STAGE:
            try:
                path = self.published_observation.marketing_package.get_absolute_url()
            except MarketingPackage.DoesNotExist:
                observation = self.published_observation.observation
                path = reverse(
                    "sites:stage-detail",
                    kwargs={"slug": observation.site.slug, "stage": observation.stage},
                )
            fragment = ""
        elif self.target_type == QRTargetType.CONTACT:
            path = reverse("core:home")
            fragment = "#contact"
        else:
            path = reverse("core:home")
            fragment = ""
        query = {"source": self.source_code}
        if self.target_type == QRTargetType.STAGE:
            try:
                query["content"] = str(self.published_observation.marketing_package.public_token)
            except MarketingPackage.DoesNotExist:
                pass
        return f"{path}?{urlencode(query)}{fragment}"

    def get_scan_path(self):
        return reverse("campaigns:scan", kwargs={"token": self.token})
