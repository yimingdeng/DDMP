from django import forms

from .models import MediaAsset, MediaType


class MediaAssetAdminForm(forms.ModelForm):
    """Make the selected media type authoritative in admin edit forms."""

    video_url = forms.URLField(
        label="视频链接",
        required=False,
        max_length=500,
        assume_scheme="https",
    )

    class Meta:
        model = MediaAsset
        fields = (
            "content_type",
            "object_id",
            "media_type",
            "title",
            "description",
            "alt_text",
            "image",
            "video_platform",
            "video_url",
            "video_file",
            "video_cover",
            "captured_at",
            "is_cover",
            "sort_order",
            "status",
        )

    def clean(self):
        cleaned_data = super().clean()
        media_type = cleaned_data.get("media_type")

        if media_type == MediaType.IMAGE:
            cleaned_data["video_platform"] = ""
            cleaned_data["video_url"] = ""
            cleaned_data["video_file"] = False
            cleaned_data["video_cover"] = False
        elif media_type == MediaType.VIDEO_LINK:
            cleaned_data["image"] = False
            cleaned_data["video_file"] = False
        elif media_type == MediaType.LOCAL_VIDEO:
            cleaned_data["image"] = False
            cleaned_data["video_platform"] = ""
            cleaned_data["video_url"] = ""

        return cleaned_data
