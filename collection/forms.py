from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import AnomalyReport, DemoApplication, validate_field_video
from .stage_fields import CHOICE_SETS, STAGE_FIELDS


class CollectorAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"


class ReviewActionForm(forms.Form):
    action = forms.ChoiceField(
        choices=(
            ("regional_approve", "区域审核通过"),
            ("hq_approve", "总部审核通过"),
            ("reject", "退回修改"),
            ("publish", "发布公开快照"),
        ),
        widget=forms.HiddenInput,
    )
    comment = forms.CharField(
        label="审核意见", max_length=1000, required=False, widget=forms.Textarea(attrs={"rows": 4})
    )
    public_summary = forms.CharField(
        label="对外展示摘要",
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def clean(self):
        data = super().clean()
        if data.get("action") == "reject" and not data.get("comment", "").strip():
            self.add_error("comment", "退回时必须填写原因。")
        if data.get("action") == "publish" and not data.get("public_summary", "").strip():
            self.add_error("public_summary", "发布前必须填写对外展示摘要。")
        return data


class DemoApplicationForm(forms.ModelForm):
    class Meta:
        model = DemoApplication
        fields = (
            "applicant_name",
            "phone",
            "variety",
            "proposed_site_name",
            "region",
            "province",
            "city",
            "county",
            "township_village",
            "detailed_address",
            "proposed_area_mu",
            "planned_sowing_date",
            "planting_experience",
            "request_note",
        )
        widgets = {
            "planned_sowing_date": forms.DateInput(attrs={"type": "date"}),
            "request_note": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from varieties.models import Variety

        self.fields["variety"].queryset = Variety.published.all()

    def clean_phone(self):
        return " ".join(self.cleaned_data["phone"].strip().split())


class DemoApplicationReviewForm(forms.Form):
    action = forms.ChoiceField(
        choices=(("approve", "审核通过"), ("reject", "退回申请")),
        widget=forms.HiddenInput,
    )
    review_note = forms.CharField(
        label="区域审核意见",
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    login_username = forms.CharField(label="负责人登录用户名", max_length=150, required=False)
    initial_password = forms.CharField(
        label="初始密码（至少6位）",
        required=False,
        strip=False,
        widget=forms.PasswordInput(render_value=True, attrs={"autocomplete": "new-password"}),
    )

    def clean(self):
        data = super().clean()
        if data.get("action") == "approve":
            username = data.get("login_username", "").strip()
            password = data.get("initial_password", "")
            if not username:
                self.add_error("login_username", "审核通过时必须设置登录用户名。")
            elif get_user_model().objects.filter(username=username).exists():
                self.add_error("login_username", "该用户名已经存在，请更换。")
            if not password:
                self.add_error("initial_password", "审核通过时必须设置初始密码。")
            else:
                try:
                    validate_password(password)
                except ValidationError as exc:
                    self.add_error("initial_password", exc)
        return data


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleImageInput(attrs={"accept": "image/jpeg,image/png,image/webp"})

    def clean(self, data, initial=None):
        clean_one = super().clean
        if not data:
            return []
        return [clean_one(item, initial) for item in data]


class MultipleVideoInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleVideoField(forms.FileField):
    widget = MultipleVideoInput(attrs={"accept": "video/*", "capture": "environment"})

    def clean(self, data, initial=None):
        clean_one = super().clean
        if not data:
            return []
        files = [clean_one(item, initial) for item in data]
        for item in files:
            validate_field_video(item)
        return files


class AnomalyReportForm(forms.ModelForm):
    camera_photos = MultipleImageField(
        label="拍摄异常照片（可拍多张）",
        required=False,
        widget=MultipleImageInput(attrs={"accept": "image/*", "capture": "environment"}),
    )
    photos = MultipleImageField(label="从相册选择异常照片", required=False)

    class Meta:
        model = AnomalyReport
        fields = (
            "stage",
            "anomaly_type",
            "severity",
            "occurred_date",
            "description",
            "suggested_action",
        )
        widgets = {
            "occurred_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "suggested_action": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        data = super().clean()
        if not data.get("camera_photos") and not data.get("photos"):
            self.add_error("photos", "异常上报至少需要一张现场照片。")
        return data


class ObservationForm(forms.Form):
    camera_photos = MultipleImageField(
        label="拍照（可拍多张）",
        required=False,
        widget=MultipleImageInput(attrs={"accept": "image/*", "capture": "environment"}),
    )
    photos = MultipleImageField(label="从相册选择照片（可多选）", required=False)
    camera_videos = MultipleVideoField(label="摄像（可录多段）", required=False)
    video_caption = forms.CharField(label="本次视频说明", max_length=160, required=False)
    photo_caption = forms.CharField(label="本次照片说明", max_length=160, required=False)
    collector_note = forms.CharField(
        label="负责人评价",
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def __init__(self, *args, stage, submitting=False, existing_photo_count=0, **kwargs):
        self.stage = stage
        self.submitting = submitting
        self.existing_photo_count = existing_photo_count
        super().__init__(*args, **kwargs)
        dynamic = {}
        for name, label, field_type, required_on_submit in STAGE_FIELDS[stage]:
            required = submitting and required_on_submit
            if field_type == "date":
                field = forms.DateField(
                    label=label, required=required, widget=forms.DateInput(attrs={"type": "date"})
                )
            elif field_type == "integer":
                field = forms.IntegerField(label=label, required=required, min_value=0)
            elif field_type == "decimal":
                field = forms.DecimalField(
                    label=label, required=required, min_value=Decimal("0"), decimal_places=2
                )
                if name == "plant_spacing":
                    field.widget.attrs["readonly"] = True
                    field.widget.attrs["aria-readonly"] = "true"
            elif field_type.startswith("choice:"):
                choices = CHOICE_SETS[field_type.split(":", 1)[1]]
                field = forms.ChoiceField(label=label, required=required, choices=choices)
            elif field_type.startswith("multi:"):
                choices = CHOICE_SETS[field_type.split(":", 1)[1]]
                field = forms.MultipleChoiceField(
                    label=label,
                    required=required,
                    choices=choices,
                    widget=forms.CheckboxSelectMultiple,
                )
            elif field_type == "textarea":
                field = forms.CharField(
                    label=label,
                    required=required,
                    max_length=1000,
                    widget=forms.Textarea(attrs={"rows": 3}),
                )
            else:
                field = forms.CharField(label=label, required=required, max_length=300)
            field.required_on_submit = required_on_submit
            dynamic[name] = field
        self.fields = {**dynamic, **self.fields}

    def clean(self):
        data = super().clean()
        percentage_fields = (
            "emergence_rate",
            "lodging_rate",
            "breakage_rate",
            "barren_rate",
            "ear_rot_rate",
            "moisture",
        )
        for name in percentage_fields:
            value = data.get(name)
            if value is not None and value > 100:
                self.add_error(name, "百分比不能大于 100。")
        if self.stage == "sowing":
            density = data.get("density")
            row_spacing = data.get("row_spacing")
            if density and row_spacing:
                plant_spacing = Decimal("6666666.67") / (Decimal(density) * row_spacing)
                data["plant_spacing"] = plant_spacing.quantize(Decimal("0.1"))
        if self.stage == "flowering":
            tasseling = data.get("tasseling_date")
            silking = data.get("silking_date")
            if tasseling and silking and silking < tasseling:
                self.add_error("silking_date", "吐丝日期不能早于抽雄日期。")
        new_photo_count = len(data.get("photos", [])) + len(data.get("camera_photos", []))
        if self.submitting and self.existing_photo_count + new_photo_count < 1:
            self.add_error("photos", "提交阶段记录前至少需要一张现场照片。")
        return data

    def observation_data(self):
        excluded = {
            "camera_photos",
            "photos",
            "camera_videos",
            "photo_caption",
            "video_caption",
            "collector_note",
        }
        result = {}
        for name, value in self.cleaned_data.items():
            if name in excluded or value in (None, "", []):
                continue
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            elif isinstance(value, Decimal):
                value = str(value)
            result[name] = value
        if self.stage == "flowering":
            tasseling = self.cleaned_data.get("tasseling_date")
            silking = self.cleaned_data.get("silking_date")
            if tasseling and silking:
                result["flowering_interval_days"] = (silking - tasseling).days
        elif self.stage == "harvest":
            area = self.cleaned_data.get("actual_area")
            weight = self.cleaned_data.get("actual_weight")
            if area and weight:
                result["actual_yield_kg_mu"] = str((weight / area).quantize(Decimal("0.01")))
        return result

    def display_rows(self):
        rows = []
        for name, label, _field_type, _required in STAGE_FIELDS[self.stage]:
            value = self.initial.get(name)
            if value in (None, "", []):
                continue
            field = self.fields[name]
            if getattr(field, "choices", None):
                labels = dict(field.choices)
                if isinstance(value, list):
                    value = "、".join(labels.get(item, item) for item in value)
                else:
                    value = labels.get(value, value)
            rows.append((label, value))
        calculated_labels = {
            "flowering_interval_days": "抽雄至吐丝间隔（天）",
            "actual_yield_kg_mu": "实收亩产（公斤/亩，未折算水分）",
        }
        for name, label in calculated_labels.items():
            value = self.initial.get(name)
            if value not in (None, ""):
                rows.append((label, value))
        note = self.initial.get("collector_note")
        if note:
            rows.append(("负责人评价", note))
        return rows
