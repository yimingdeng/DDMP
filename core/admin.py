from types import MethodType

from django import forms
from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError

from .models import AuditEvent, SiteConfiguration, UserProfile, mobile_phone_validator

User = get_user_model()

admin.site.site_header = "玉米重点品种数字展示平台"
admin.site.site_title = "平台管理"
admin.site.index_title = "平台业务管理"

ADMIN_APP_ORDER = (
    "varieties",
    "sites",
    "media_assets",
    "collection",
    "inquiries",
    "campaigns",
    "analytics",
    "core",
    "auth",
)

ADMIN_MODEL_ORDER = {
    "varieties": ("Variety", "SellingPoint"),
    "sites": ("DemoSite", "Contact"),
    "media_assets": ("MediaAsset",),
    "collection": (
        "DemoApplication",
        "Observation",
        "AnomalyReport",
        "SiteAssignment",
        "CollectionReviewer",
        "PublishedObservation",
        "CollectionEvent",
    ),
    "inquiries": ("Inquiry", "RegionalContact", "InquiryFollowUp"),
    "campaigns": (
        "MarketingPackage",
        "TrackedLink",
        "PromotionIdentity",
        "ChannelQRCode",
    ),
    "analytics": ("VisitEvent",),
    "core": ("SiteConfiguration", "AuditEvent"),
    "auth": ("User", "Group"),
}


def _user_has_admin_permission(user):
    if not user.is_active or not user.is_staff:
        return False
    if user.is_superuser:
        return True
    admin_app_labels = {model._meta.app_label for model in admin.site._registry}
    return any(user.has_module_perms(app_label) for app_label in admin_app_labels)


class PermissionAwareAdminAuthenticationForm(AdminAuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not _user_has_admin_permission(user):
            raise ValidationError(
                "当前账号没有后台管理权限，请联系管理员开通相应权限。",
                code="no_admin_permission",
            )


def _set_chinese_name_labels(form):
    if "last_name" in form.fields:
        form.fields["last_name"].label = "姓"
    if "first_name" in form.fields:
        form.fields["first_name"].label = "名"


def _user_phone(user):
    profile = getattr(user, "profile", None)
    return profile.phone if profile else ""


def _save_user_phone(user, phone):
    UserProfile.objects.update_or_create(user=user, defaults={"phone": phone})


class PlatformUserChangeForm(UserChangeForm):
    phone = forms.CharField(
        label="手机",
        max_length=11,
        required=True,
        validators=[mobile_phone_validator],
        help_text="必填，可用于登录系统。",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _set_chinese_name_labels(self)
        if self.instance.pk:
            self.fields["phone"].initial = _user_phone(self.instance)

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        queryset = UserProfile.objects.filter(phone=phone)
        if self.instance.pk:
            queryset = queryset.exclude(user=self.instance)
        if queryset.exists():
            raise ValidationError("该手机号已被其他用户使用。")
        return phone

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            _save_user_phone(user, self.cleaned_data["phone"])
        return user


class PlatformUserCreationForm(AdminUserCreationForm):
    phone = forms.CharField(
        label="手机",
        max_length=11,
        required=True,
        validators=[mobile_phone_validator],
        help_text="必填，可用于登录系统。",
    )

    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("username", "last_name", "first_name", "email", "phone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _set_chinese_name_labels(self)
        if "email" in self.fields:
            self.fields["email"].label = "电子邮箱"
            self.fields["email"].required = False

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if UserProfile.objects.filter(phone=phone).exists():
            raise ValidationError("该手机号已被其他用户使用。")
        return phone

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            _save_user_phone(user, self.cleaned_data["phone"])
        return user


def _has_admin_permission(self, request):
    return _user_has_admin_permission(request.user)


def _order_key(value, preferred_order):
    try:
        return preferred_order.index(value)
    except ValueError:
        return len(preferred_order)


def _get_ordered_app_list(self, request, app_label=None):
    app_dict = self._build_app_dict(request, app_label)
    app_list = list(app_dict.values())
    app_list.sort(
        key=lambda app: (
            _order_key(app["app_label"], ADMIN_APP_ORDER),
            app["name"],
        )
    )
    for app in app_list:
        model_order = ADMIN_MODEL_ORDER.get(app["app_label"], ())
        app["models"].sort(
            key=lambda model: (
                _order_key(model["object_name"], model_order),
                model["name"],
            )
        )
    return app_list


admin.site.get_app_list = MethodType(_get_ordered_app_list, admin.site)
admin.site.has_permission = MethodType(_has_admin_permission, admin.site)
admin.site.login_form = PermissionAwareAdminAuthenticationForm

try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class PlatformUserAdmin(DjangoUserAdmin):
    form = PlatformUserChangeForm
    add_form = PlatformUserCreationForm
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("个人信息", {"fields": ("last_name", "first_name", "phone", "email")}),
        (
            "权限",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("重要日期", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "last_name",
                    "first_name",
                    "phone",
                    "email",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    list_display = ("username", "display_name", "phone_number", "email", "is_staff", "is_active")
    search_fields = ("username", "first_name", "last_name", "email", "profile__phone")

    @admin.display(description="姓名")
    def display_name(self, obj):
        return obj.get_full_name()

    @admin.display(description="手机")
    def phone_number(self, obj):
        return _user_phone(obj) or "未设置"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        phone = form.cleaned_data.get("phone")
        if phone:
            _save_user_phone(obj, phone)


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "基本信息",
            {
                "fields": (
                    "site_name",
                    "company_name",
                    "logo",
                    "color_theme",
                    "contact_phone",
                )
            },
        ),
        (
            "首页首屏",
            {
                "fields": (
                    "hero_title",
                    "hero_subtitle",
                    "primary_cta_label",
                    "secondary_cta_label",
                )
            },
        ),
        (
            "分享配置",
            {
                "fields": (
                    "default_share_title",
                    "default_share_description",
                    "default_share_image",
                    "public_base_url",
                )
            },
        ),
        ("地图配置", {"fields": ("amap_js_api_key", "amap_security_code")}),
        ("咨询隐私", {"fields": ("privacy_notice", "privacy_version")}),
        ("页面信息", {"fields": ("meta_description", "footer_text")}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not SiteConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action="site_config_change",
            object_type="站点配置",
            object_id=str(obj.pk),
            summary="更新站点配置（未记录字段内容）",
        )


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action_label", "actor", "object_type", "object_id", "summary")
    list_filter = ("action", "created_at")
    search_fields = ("actor__username", "object_type", "object_id", "summary")
    readonly_fields = ("created_at", "actor", "action", "object_type", "object_id", "summary")

    @admin.display(description="操作")
    def action_label(self, obj):
        return obj.get_action_label()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
