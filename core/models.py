from django.conf import settings
from django.core.validators import MaxLengthValidator, RegexValidator
from django.db import models
from django.utils import timezone

mobile_phone_validator = RegexValidator(
    regex=r"^1[3-9]\d{9}$",
    message="请输入 11 位中国大陆手机号。",
)


def generated_user_phone(user_id):
    return f"199{int(user_id) % 100000000:08d}"


class PublicationStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    PUBLISHED = "published", "已发布"
    ARCHIVED = "archived", "已归档"


class SiteColorTheme(models.TextChoices):
    SYSTEM = "system", "系统基本色调（绿色）"
    PURPLE_YELLOW = "purple_yellow", "紫色＋黄色"


class PublishedQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=PublicationStatus.PUBLISHED)


class PublishedManager(models.Manager.from_queryset(PublishedQuerySet)):
    def get_queryset(self):
        return super().get_queryset().published()


class PublishableModel(models.Model):
    status = models.CharField(
        "发布状态",
        max_length=20,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DRAFT,
        db_index=True,
    )
    published_at = models.DateTimeField("发布时间", null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="发布人",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    objects = PublishedQuerySet.as_manager()
    published = PublishedManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.status == PublicationStatus.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class SiteConfiguration(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    site_name = models.CharField("站点名称", max_length=100, default="玉米重点品种数字展示平台")
    company_name = models.CharField("公司名称", max_length=100, blank=True)
    logo = models.FileField("Logo", upload_to="site/", blank=True)
    color_theme = models.CharField(
        "系统主色调",
        max_length=30,
        choices=SiteColorTheme.choices,
        default=SiteColorTheme.PURPLE_YELLOW,
        help_text="控制公开营销首页、示范传播页以及新生成的营销图片；不改变采集端和后台管理界面。",
    )
    hero_title = models.CharField(
        "首页主标题",
        max_length=100,
        default="让每一块示范田，都有真实可见的成长记录",
    )
    hero_subtitle = models.TextField(
        "首页副标题",
        default="聚焦重点玉米品种，连接田间表现、示范展示与客户服务。",
        validators=[MaxLengthValidator(300)],
    )
    primary_cta_label = models.CharField("主按钮文字", max_length=30, default="查看示范点")
    secondary_cta_label = models.CharField("次按钮文字", max_length=30, default="我要咨询")
    contact_phone = models.CharField("客服电话", max_length=30, blank=True)
    footer_text = models.CharField("页脚文字", max_length=200, blank=True)
    meta_description = models.CharField(
        "页面描述",
        max_length=160,
        default="玉米重点品种数字示范展示平台",
    )
    default_share_title = models.CharField(
        "默认分享标题",
        max_length=100,
        blank=True,
        help_text="为空时使用站点名称。",
    )
    default_share_description = models.CharField(
        "默认分享描述",
        max_length=160,
        blank=True,
        help_text="为空时使用页面描述。",
    )
    default_share_image = models.ImageField(
        "默认分享图",
        upload_to="site/share/",
        blank=True,
        help_text="建议使用 1.91:1 横图，例如 1200×630。",
    )
    public_base_url = models.URLField(
        "公开访问地址",
        blank=True,
        help_text="生成二维码时使用，例如 https://show.example.com；为空时使用当前后台访问地址。",
    )
    amap_js_api_key = models.CharField(
        "高德地图 JS API Key",
        max_length=100,
        blank=True,
        help_text="在高德开放平台申请 Web 端（JS API）Key。",
    )
    amap_security_code = models.CharField(
        "高德地图安全密钥",
        max_length=160,
        blank=True,
        help_text="高德 JS API 2.0 的 securityJsCode；正式环境建议改用服务端代理。",
    )
    privacy_notice = models.CharField(
        "咨询隐私说明",
        max_length=300,
        default="我同意平台保存以上信息，并由相关服务人员联系我。",
    )
    privacy_version = models.CharField("隐私说明版本", max_length=30, default="2026-07-01")
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "站点配置"
        verbose_name_plural = "站点配置"

    def __str__(self) -> str:
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1
        if self._state.adding and type(self).objects.filter(pk=self.pk).exists():
            self._state.adding = False
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        configuration, _ = cls.objects.get_or_create(pk=1)
        return configuration

    @property
    def theme_css_class(self):
        return f"theme-{self.color_theme.replace('_', '-')}"

    @property
    def theme_color(self):
        if self.color_theme == SiteColorTheme.PURPLE_YELLOW:
            return "#32128f"
        return "#174b2a"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="profile",
    )
    phone = models.CharField(
        "手机",
        max_length=11,
        unique=True,
        validators=[mobile_phone_validator],
        help_text="必填。可用于登录系统，现有用户会先自动生成临时手机号，后续可修改。",
    )
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "用户扩展信息"
        verbose_name_plural = "用户扩展信息"

    def __str__(self):
        return f"{self.user.username} · {self.phone}"


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="操作人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="platform_audit_events",
    )
    action = models.CharField("操作", max_length=50, db_index=True)
    object_type = models.CharField("对象类型", max_length=80, blank=True)
    object_id = models.CharField("对象 ID", max_length=80, blank=True)
    summary = models.CharField("摘要", max_length=300, blank=True)
    created_at = models.DateTimeField("发生时间", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "敏感操作审计"
        verbose_name_plural = "敏感操作审计"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_action_label()} · {self.created_at:%Y-%m-%d %H:%M}"

    def get_action_label(self):
        return {
            "inquiry_view": "查看线索详情",
            "inquiry_change": "修改线索",
            "site_config_change": "修改站点配置",
            "site_basic_info_change": "修改示范点基本信息",
        }.get(self.action, self.action)
