from django import forms

from .models import Inquiry


class InquiryForm(forms.ModelForm):
    website = forms.CharField(required=False)
    submission_key = forms.UUIDField(widget=forms.HiddenInput)
    variety_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    site_id = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Inquiry
        fields = (
            "name",
            "phone",
            "area_name",
            "organization",
            "message",
            "intent_type",
            "privacy_consent",
        )

    def clean_phone(self):
        return " ".join(self.cleaned_data["phone"].strip().split())

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("website"):
            raise forms.ValidationError("提交失败，请稍后重试。")
        return cleaned_data
