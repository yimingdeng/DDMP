from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from core.models import PublicationStatus, PublishableModel
from sites.models import DemoSite
from varieties.models import Variety

contact_phone_validator = RegexValidator(
    r"^[0-9+()\-\s]{7,30}$",
    "请输入正确的联系电话，可使用数字、空格、+、- 和括号。",
)
source_code_validator = RegexValidator(
    r"^[a-z0-9][a-z0-9_-]{1,39}$",
    "来源代码只能包含小写字母、数字、下划线和连字符，长度为 2—40 位。",
)


class InquiryStatus(models.TextChoices):
    NEW = "new", "待处理"
    FOLLOWING = "following", "跟进中"
    COMPLETED = "completed", "已完成"
    INVALID = "invalid", "无效线索"


class InquiryIntent(models.TextChoices):
    CONSULTATION = "consultation", "产品咨询"
    SITE_VISIT = "site_visit", "预约看田"
    TRIAL = "trial", "申请试种"
    AGENCY = "agency", "代理合作"
    EVENT = "event", "参加观摩会"
    FEEDBACK = "feedback", "提交反馈"


class CustomerIdentity(models.TextChoices):
    DEALER = "dealer", "经销商"
    FARMER = "farmer", "农户"
    LARGE_GROWER = "large_grower", "种植大户"
    COOPERATIVE = "cooperative", "合作社"
    RETAILER = "retailer", "零售商"
    OTHER = "other", "其他"


class RegionalContact(PublishableModel):
    area_name = models.CharField("服务区域", max_length=50, db_index=True)
    manager_name = models.CharField("联系人姓名", max_length=50)
    role_title = models.CharField("职位", max_length=50, default="区域经理")
    phone = models.CharField("联系电话", max_length=30, validators=[contact_phone_validator])
    service_note = models.CharField("服务说明", max_length=160, blank=True)
    sort_order = models.PositiveIntegerField("排序", default=100)

    class Meta:
        verbose_name = "区域联系人"
        verbose_name_plural = "区域联系人"
        ordering = ("sort_order", "area_name", "manager_name")

    def __str__(self):
        return f"{self.area_name} · {self.manager_name}"

    def clean(self):
        super().clean()
        if self.status == PublicationStatus.PUBLISHED:
            errors = {}
            if not self.area_name.strip():
                errors["area_name"] = "发布前必须填写服务区域。"
            if not self.manager_name.strip():
                errors["manager_name"] = "发布前必须填写联系人姓名。"
            if errors:
                raise ValidationError(errors)


class Inquiry(models.Model):
    name = models.CharField("姓名", max_length=50)
    phone = models.CharField("联系电话", max_length=30, validators=[contact_phone_validator])
    area_name = models.CharField("所在区域", max_length=50)
    organization = models.CharField("单位/组织", max_length=100, blank=True)
    message = models.TextField("咨询内容", max_length=500, blank=True)
    customer_identity = models.CharField(
        "客户身份", max_length=30, choices=CustomerIdentity.choices, default=CustomerIdentity.OTHER
    )
    intent_type = models.CharField(
        "意向类型",
        max_length=30,
        choices=InquiryIntent.choices,
        default=InquiryIntent.CONSULTATION,
        db_index=True,
    )
    variety = models.ForeignKey(
        Variety,
        verbose_name="感兴趣品种",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inquiries",
    )
    demo_site = models.ForeignKey(
        DemoSite,
        verbose_name="感兴趣示范点",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inquiries",
    )
    privacy_consent = models.BooleanField("已同意联系和信息处理", default=False)
    privacy_version = models.CharField("隐私说明版本", max_length=30, blank=True, editable=False)
    consent_at = models.DateTimeField("同意时间", null=True, blank=True, editable=False)
    status = models.CharField(
        "处理状态",
        max_length=20,
        choices=InquiryStatus.choices,
        default=InquiryStatus.NEW,
        db_index=True,
    )
    assigned_to = models.ForeignKey(
        RegionalContact,
        verbose_name="分配给",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inquiries",
    )
    admin_notes = models.TextField("内部跟进记录", blank=True)
    source_code = models.CharField(
        "来源代码",
        max_length=40,
        default="direct",
        validators=[source_code_validator],
        db_index=True,
        editable=False,
    )
    source_path = models.CharField("来源页面", max_length=300, blank=True, editable=False)
    marketing_package = models.ForeignKey(
        "campaigns.MarketingPackage",
        verbose_name="来源营销素材",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="inquiries",
    )
    promotion_identity = models.ForeignKey(
        "campaigns.PromotionIdentity",
        verbose_name="来源推广人",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="inquiries",
    )
    tracked_link = models.ForeignKey(
        "campaigns.TrackedLink",
        verbose_name="来源追踪链接",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="inquiries",
    )
    submission_key = models.CharField(
        "防重复提交标识",
        max_length=36,
        blank=True,
        editable=False,
    )
    followed_at = models.DateTimeField("最近跟进时间", null=True, blank=True)
    followed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="最近跟进人",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="followed_inquiries",
    )
    created_at = models.DateTimeField("提交时间", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "咨询记录"
        verbose_name_plural = "咨询记录"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("submission_key",),
                condition=~models.Q(submission_key=""),
                name="unique_nonempty_inquiry_submission_key",
            )
        ]

    def __str__(self):
        return f"{self.name} · {self.area_name} · {self.get_status_display()}"

    def clean(self):
        super().clean()
        if not self.privacy_consent:
            raise ValidationError({"privacy_consent": "必须取得用户同意后才能保存联系信息。"})


class InquiryFollowUp(models.Model):
    inquiry = models.ForeignKey(
        Inquiry, verbose_name="咨询记录", on_delete=models.CASCADE, related_name="follow_ups"
    )
    status = models.CharField("处理状态", max_length=20, choices=InquiryStatus.choices)
    note = models.TextField("跟进记录", max_length=1000)
    next_action = models.CharField("下一步计划", max_length=300, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="记录人",
        null=True,
        on_delete=models.SET_NULL,
        related_name="inquiry_follow_ups",
    )
    created_at = models.DateTimeField("记录时间", auto_now_add=True)

    class Meta:
        verbose_name = "线索跟进记录"
        verbose_name_plural = "线索跟进记录"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.inquiry} · {self.get_status_display()}"
