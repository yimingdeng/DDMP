from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import (
    DistributionChannel,
    ExternalPublication,
    ExternalPublicationStatus,
    PromotionIdentity,
)


class MarketingAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"


class ShareLinkForm(forms.Form):
    channel = forms.ChoiceField(label="传播渠道", choices=DistributionChannel.choices)
    promoter = forms.ModelChoiceField(
        label="推广身份",
        queryset=PromotionIdentity.objects.none(),
        required=False,
        empty_label="公司公共链接",
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        own_identity = PromotionIdentity.objects.filter(user=user, is_active=True).first()
        can_choose_promoter = user.is_superuser or user.has_perm("campaigns.change_trackedlink")
        if can_choose_promoter:
            self.fields["promoter"].queryset = PromotionIdentity.objects.filter(is_active=True)
        elif own_identity:
            self.fields["promoter"].queryset = PromotionIdentity.objects.filter(pk=own_identity.pk)
            self.fields["promoter"].initial = own_identity
            self.fields["promoter"].widget = forms.HiddenInput()
        else:
            self.fields["promoter"].widget = forms.HiddenInput()
        self.own_identity = own_identity
        self.can_choose_promoter = can_choose_promoter

    def clean_promoter(self):
        promoter = self.cleaned_data.get("promoter")
        if not self.can_choose_promoter:
            return self.own_identity
        return promoter


class ExternalPublicationForm(forms.ModelForm):
    video_link_required_channels = {
        DistributionChannel.WECHAT_CHANNELS,
        DistributionChannel.DOUYIN_VIDEO,
        DistributionChannel.DOUYIN_LIVE,
    }

    published_at = forms.DateTimeField(
        label="发布时间",
        required=False,
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
    )

    class Meta:
        model = ExternalPublication
        fields = (
            "channel",
            "status",
            "title",
            "account_name",
            "external_url",
            "published_at",
            "view_count",
            "like_count",
            "comment_count",
            "share_count",
            "notes",
        )
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned_data = super().clean()
        channel = cleaned_data.get("channel")
        status = cleaned_data.get("status")
        external_url = (cleaned_data.get("external_url") or "").strip()
        published_at = cleaned_data.get("published_at")
        if (
            status == ExternalPublicationStatus.PUBLISHED
            and channel in self.video_link_required_channels
            and not external_url
        ):
            self.add_error(
                "external_url", "视频号、抖音发布记录必须填写外部链接，方便客户查看视频内容。"
            )
        if status == ExternalPublicationStatus.PUBLISHED and not published_at:
            self.add_error("published_at", "已发布记录必须填写发布时间。")
        return cleaned_data
