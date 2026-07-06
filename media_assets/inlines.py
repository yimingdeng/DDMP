from django.contrib.contenttypes.admin import GenericStackedInline
from django.contrib.contenttypes.forms import BaseGenericInlineFormSet
from django.core.exceptions import ValidationError

from .models import MediaAsset


class MediaAssetInlineFormSet(BaseGenericInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        selected_covers = []
        for form in self.forms:
            cleaned_data = getattr(form, "cleaned_data", None)
            if not cleaned_data or cleaned_data.get("DELETE"):
                continue
            if cleaned_data.get("is_cover"):
                selected_covers.append(cleaned_data.get("title") or "未命名媒体")

        if len(selected_covers) > 1:
            names = "、".join(selected_covers)
            raise ValidationError(
                f"当前同时选择了多张封面（{names}）。"
                "同一品种、核心卖点或示范点只能保留一张封面，"
                "请只勾选一条“设为封面”。"
            )


class MediaAssetInline(GenericStackedInline):
    model = MediaAsset
    formset = MediaAssetInlineFormSet
    extra = 0
    fields = (
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
    show_change_link = True
