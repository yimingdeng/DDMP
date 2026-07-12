from datetime import datetime, time
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

from django.core.files.base import ContentFile
from django.db.models import Count, Sum
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont, ImageOps

from collection.forms import ObservationForm
from core.models import SiteColorTheme, SiteConfiguration

from .models import (
    ExternalPublication,
    MarketingPackage,
    MarketingPosterVariant,
    MarketingWeeklyReport,
    PosterVariantType,
    ShortVideoTopic,
    TrackedLink,
)
from .qr import render_qr_png


def _compact(value, limit):
    text = " ".join(str(value or "").split())
    return text[:limit]


STAGE_MARKETING_TONES = {
    "sowing": {
        "focus": ["播种基础", "密度合理", "规范管理"],
        "opening": "这块田刚完成播种，重点看播种质量和后续苗情基础。",
        "middle": "播种期内容不追求长篇介绍，核心讲清楚地块位置、播种密度和管理起点。",
        "cta": "后续出苗和长势会持续更新，适合提前关注示范进展。",
    },
    "emergence": {
        "focus": ["出苗整齐", "苗势均衡", "成苗基础好"],
        "opening": "现在进入出苗期，第一眼要看的是出苗是否整齐、苗势是否均衡。",
        "middle": "镜头可以从地头扫到田中，重点展示行间一致性和缺苗情况。",
        "cta": "想看后续拔节长势，可以持续关注这个示范点。",
    },
    "jointing": {
        "focus": ["长势稳健", "株型清秀", "群体整齐"],
        "opening": "拔节期主要看群体长势、株型和田间整齐度。",
        "middle": "这一阶段适合用近景看叶片和茎秆，用远景看整块田的整齐度。",
        "cta": "适合转发给想提前看品种田间基础表现的客户。",
    },
    "flowering": {
        "focus": ["花期协调", "吐丝整齐", "授粉基础好"],
        "opening": "抽雄吐丝期重点看花期是否协调，吐丝和散粉是否跟得上。",
        "middle": "镜头要多给雄穗、吐丝和整体田面，突出授粉关键期表现。",
        "cta": "想组织看田的客户，可以重点关注这一阶段。",
    },
    "filling": {
        "focus": ["灌浆充分", "保绿性好", "抗病观察"],
        "opening": "灌浆期重点看叶片保绿、穗部发育和病害表现。",
        "middle": "这一阶段不要只拍单穗，要把植株、叶片和果穗一起讲清楚。",
        "cta": "后续成熟期会继续观察站秆和脱水表现。",
    },
    "maturity": {
        "focus": ["站秆稳定", "穗部整齐", "脱水表现"],
        "opening": "成熟期最抓人的就是站秆、果穗整齐度和脱水表现。",
        "middle": "镜头先看全田站秆，再看穗位和果穗，最后补充脱水和看田安排。",
        "cta": "适合邀请客户现场看田，也适合销售和经销商重点转发。",
    },
    "harvest": {
        "focus": ["测产数据", "商品性好", "收获表现"],
        "opening": "收获期要把测产、含水率和商品性讲清楚。",
        "middle": "建议用数据卡片配合现场画面，减少空泛描述，让客户看到结果。",
        "cta": "对经销合作、明年试种和大户跟进最有转化价值。",
    },
}


def _stage_tone(stage):
    return STAGE_MARKETING_TONES.get(stage, STAGE_MARKETING_TONES["maturity"])


def build_marketing_defaults(snapshot):
    observation = snapshot.observation
    site = observation.site
    stage_label = observation.get_stage_display()
    tone = _stage_tone(observation.stage)
    form = ObservationForm(stage=observation.stage, initial=snapshot.public_data)
    rows = form.display_rows()
    tags = [_compact(f"{label} {value}", 18) for label, value in rows[:3]]
    if not tags:
        tags = [
            _compact(part, 18)
            for part in snapshot.public_summary.replace("。", "，").split("，")
            if part.strip()
        ][:3]
    if not tags:
        tags = tone["focus"][:3]
    else:
        tags = (tags + tone["focus"])[:3]
    tag_copy = "｜".join(tags)
    headline = f"{site.variety.name}｜{site.name}{stage_label}表现更新"
    summary = _compact(snapshot.public_summary, 220) or f"查看{site.name}{stage_label}田间实拍。"
    return {
        "headline": headline,
        "core_tags": tags,
        "wechat_moments_copy": (
            f"{site.variety.name}｜{site.name}{stage_label}表现更新\n"
            f"{tag_copy}\n"
            f"{summary}\n"
            "扫码查看完整田间实拍，欢迎咨询和预约看田。"
        ),
        "customer_private_copy": (
            f"您好，给您发一下{site.variety.name}在{site.name}的{stage_label}示范表现。\n"
            f"这一阶段重点可以先看：{tag_copy}。\n"
            f"{summary}\n"
            "您可以先打开链接看看田间实拍和阶段数据，如果想进一步了解、预约看田或试种，我再给您对接。"
        ),
        "wechat_group_copy": (
            f"{headline}\n"
            f"{tag_copy}\n"
            f"{tone['opening']}\n"
            f"{summary}\n"
            "点击查看完整示范表现，可咨询、预约看田或申请试种。"
        ),
        "wechat_channels_title": _compact(f"{site.variety.name}{stage_label}：{tags[0]}", 100),
        "wechat_channels_copy": (
            f"{site.name}{stage_label}更新：{tag_copy}。\n{tone['middle']}\n{summary}"
        ),
        "douyin_title": _compact(f"{site.variety.name}{stage_label}实拍，重点看{tags[0]}", 100),
        "douyin_topics": f"#{site.variety.name} #玉米示范 #田间实拍 #{stage_label} #{tags[0]}",
        "short_video_script": (
            f"开头：{tone['opening']}\n"
            f"中间：{tone['middle']} {summary}\n"
            f"重点：{tag_copy}。\n"
            f"结尾：{tone['cta']} 想看完整示范数据和更多田间实拍，"
            f"请进入{site.variety.name}数字示范平台。"
        ),
    }


def ensure_marketing_package(snapshot):
    package, created = MarketingPackage.objects.get_or_create(
        published_observation=snapshot,
        defaults=build_marketing_defaults(snapshot),
    )
    if not created and not package.headline:
        for field, value in build_marketing_defaults(snapshot).items():
            setattr(package, field, value)
        package.save()
    TrackedLink.objects.get_or_create(
        marketing_package=package,
        source_code="wechat_moments",
        promoter=None,
        defaults={"purpose": "朋友圈海报默认入口"},
    )
    ensure_short_video_topics(package)
    return package


def build_short_video_topic_defaults(package):
    observation = package.observation
    site = observation.site
    stage_label = observation.get_stage_display()
    summary = _compact(package.published_observation.public_summary, 120)
    focuses = list(package.core_tags[:4]) or [stage_label, "田间实拍", "预约看田"]
    if "预约看田" not in "".join(focuses):
        focuses.append("预约看田")
    topics = []
    for index, focus in enumerate(focuses[:5], start=1):
        title = _compact(f"{site.variety.name}{site.name}{stage_label}｜{focus}", 120)
        script = (
            f"这是第 {index} 条短视频选题，重点只讲“{focus}”。\n"
            f"开头：{site.variety.name}在{site.name}进入{stage_label}。\n"
            f"中间：{summary or '现场照片和阶段数据已经更新。'}\n"
            f"结尾：想看完整田间表现，可以扫码进入数字示范平台，提交咨询或预约看田。"
        )
        topics.append(
            {
                "title": title,
                "focus": _compact(focus, 80),
                "script": script,
                "sort_order": index * 10,
            }
        )
    return topics


def ensure_short_video_topics(package):
    if package.short_video_topics.exists():
        return package.short_video_topics.all()
    topics = [
        ShortVideoTopic(marketing_package=package, **defaults)
        for defaults in build_short_video_topic_defaults(package)
    ]
    if topics:
        ShortVideoTopic.objects.bulk_create(topics)
    return package.short_video_topics.all()


def _poster_variant_defaults(package, variant_type, promoter=None):
    observation = package.observation
    site = observation.site
    stage_label = observation.get_stage_display()
    tags = "｜".join(package.core_tags[:3]) or stage_label
    if variant_type == PosterVariantType.DEALER:
        promoter_name = promoter.name if promoter else "经销商伙伴"
        return {
            "title": f"{promoter_name}推荐｜{site.variety.name}",
            "subtitle": f"{site.name}{stage_label}表现：{tags}",
            "call_to_action": "扫码联系专属推广人",
        }
    if variant_type == PosterVariantType.FIELD_DAY:
        return {
            "title": f"{site.variety.name}看田邀请",
            "subtitle": f"{site.name} · {stage_label} · {tags}",
            "call_to_action": "扫码预约看田",
        }
    if variant_type == PosterVariantType.WEEKLY_RECOMMENDATION:
        return {
            "title": f"本周重点推荐｜{site.variety.name}",
            "subtitle": f"{site.name}{stage_label}更新：{tags}",
            "call_to_action": "扫码查看本周表现",
        }
    return {
        "title": package.headline,
        "subtitle": f"{site.name} · {stage_label} · {tags}",
        "call_to_action": "扫码查看完整表现",
    }


def _font(size, bold=False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default(size=size)


def _wrapped_lines(text, width):
    text = _compact(text, 300)
    return [text[index : index + width] for index in range(0, len(text), width)] or [""]


def _first_public_photo(package):
    snapshot = package.published_observation
    return (
        snapshot.observation.photos.filter(uploaded_at__lte=snapshot.published_at)
        .order_by("uploaded_at")
        .first()
    )


def _public_tracked_url(package):
    link, _ = TrackedLink.objects.get_or_create(
        marketing_package=package,
        source_code="wechat_moments",
        promoter=None,
        defaults={"purpose": "朋友圈海报默认入口"},
    )
    base_url = SiteConfiguration.load().public_base_url or "http://127.0.0.1:8000/"
    return urljoin(f"{base_url.rstrip('/')}/", link.get_share_path().lstrip("/"))


def _gradient_canvas(size, top, bottom):
    canvas = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(canvas)
    height = max(size[1] - 1, 1)
    for y in range(size[1]):
        ratio = y / height
        color = tuple(
            round(start + (end - start) * ratio) for start, end in zip(top, bottom, strict=True)
        )
        draw.line((0, y, size[0], y), fill=color)
    return canvas


def _marketing_palette(configuration):
    if configuration.color_theme == SiteColorTheme.PURPLE_YELLOW:
        return {
            "gradient_top": (103, 61, 235),
            "gradient_bottom": (45, 18, 111),
            "primary": "#32128f",
            "secondary": "#4a24d8",
            "accent": "#fff500",
            "accent_soft": "#fff7a3",
            "circuit": "#d8c56a",
            "overlay": (45, 18, 111, 238),
        }
    return {
        "gradient_top": (30, 96, 55),
        "gradient_bottom": (11, 47, 27),
        "primary": "#123f24",
        "secondary": "#1e6037",
        "accent": "#f5cd6c",
        "accent_soft": "#fff4d1",
        "circuit": "#d9c77a",
        "overlay": (11, 47, 27, 238),
    }


def _draw_brand_circuit(draw, palette, *, offset_y=0):
    nodes = ((92, 104), (264, 104), (344, 58), (548, 58), (630, 116), (888, 116))
    shifted = [(x, y + offset_y) for x, y in nodes]
    draw.line(shifted, fill=palette["circuit"], width=4)
    for x, y in shifted:
        draw.ellipse(
            (x - 8, y - 8, x + 8, y + 8),
            outline=palette["accent"],
            width=3,
        )


def _paste_brand_logo(canvas, configuration, position):
    if not configuration.logo:
        return
    try:
        with configuration.logo.open("rb") as source:
            logo = Image.open(source).convert("RGBA")
            logo.thumbnail((150, 100), Image.Resampling.LANCZOS)
            canvas.paste(logo, position, logo)
    except (OSError, ValueError):
        return


def _poster_variant_target_url(package, tracked_link=None, target_url=""):
    if target_url:
        return target_url
    if tracked_link:
        base_url = SiteConfiguration.load().public_base_url or "http://127.0.0.1:8000/"
        return urljoin(f"{base_url.rstrip('/')}/", tracked_link.get_share_path().lstrip("/"))
    return _public_tracked_url(package)


def _draw_poster_variant_image(package, variant, target_url):
    snapshot = package.published_observation
    observation = snapshot.observation
    site = observation.site
    configuration = SiteConfiguration.load()
    palette = _marketing_palette(configuration)
    canvas = _gradient_canvas((1080, 1440), palette["gradient_top"], palette["gradient_bottom"])
    draw = ImageDraw.Draw(canvas, "RGBA")
    _draw_brand_circuit(draw, palette, offset_y=26)
    photo = _first_public_photo(package)
    if photo:
        with photo.image.open("rb") as source:
            field_image = Image.open(source).convert("RGB")
            field_image = ImageOps.fit(field_image, (960, 610), method=Image.Resampling.LANCZOS)
            draw.rounded_rectangle((44, 178, 1036, 820), radius=34, fill=palette["accent"])
            canvas.paste(field_image, (60, 194))
    else:
        draw.rounded_rectangle((44, 178, 1036, 820), radius=34, fill=palette["accent"])
        draw.rounded_rectangle((60, 194, 1020, 804), radius=24, fill="white")
        draw.text(
            (352, 470),
            "田间真实表现",
            font=_font(50, bold=True),
            fill=palette["secondary"],
        )

    panel_top = 820
    draw.rounded_rectangle((0, panel_top, 1080, 1440), radius=0, fill=palette["overlay"])
    draw.rectangle((0, panel_top, 1080, panel_top + 18), fill=palette["accent"])
    draw.text((60, 40), site.variety.name, font=_font(54, bold=True), fill=palette["accent"])
    draw.text((60, 108), site.name, font=_font(28, bold=True), fill="white")
    _paste_brand_logo(canvas, configuration, (870, 40))

    title_lines = _wrapped_lines(variant.title, 13)[:2]
    for index, line in enumerate(title_lines):
        draw.text(
            (60, 875 + index * 76),
            line,
            font=_font(60, bold=True),
            fill=palette["accent"],
        )
    subtitle_y = 875 + len(title_lines) * 78 + 18
    for index, line in enumerate(_wrapped_lines(variant.subtitle, 18)[:3]):
        draw.text((64, subtitle_y + index * 44), line, font=_font(30), fill="white")

    tag_y = subtitle_y + 150
    for tag in package.core_tags[:3]:
        draw.rounded_rectangle(
            (64, tag_y, 580, tag_y + 54),
            radius=27,
            fill=palette["accent"],
        )
        draw.text(
            (88, tag_y + 8),
            _compact(tag, 20),
            font=_font(25, bold=True),
            fill=palette["primary"],
        )
        tag_y += 66

    qr_image = Image.open(
        BytesIO(render_qr_png(target_url, fill_color=palette["primary"], back_color="white"))
    ).convert("RGB")
    qr_image = qr_image.resize((260, 260), Image.Resampling.LANCZOS)
    draw.rounded_rectangle((742, 1046, 1034, 1376), radius=24, fill="white")
    canvas.paste(qr_image, (758, 1062))
    draw.text(
        (774, 1330),
        _compact(variant.call_to_action, 13),
        font=_font(23, bold=True),
        fill=palette["primary"],
    )
    if variant.variant_type == PosterVariantType.FIELD_DAY:
        draw.rounded_rectangle((64, 1258, 622, 1326), radius=34, fill=palette["accent"])
        draw.text(
            (100, 1271),
            "欢迎预约现场看田",
            font=_font(32, bold=True),
            fill=palette["primary"],
        )
    elif variant.variant_type == PosterVariantType.WEEKLY_RECOMMENDATION:
        draw.rounded_rectangle((64, 1258, 622, 1326), radius=34, fill=palette["accent"])
        draw.text(
            (100, 1271),
            "本周重点推荐",
            font=_font(32, bold=True),
            fill=palette["primary"],
        )
    return canvas


def generate_poster_variant(
    package,
    variant_type,
    *,
    tracked_link=None,
    promoter=None,
    target_url="",
):
    defaults = _poster_variant_defaults(package, variant_type, promoter)
    variant, _created = MarketingPosterVariant.objects.get_or_create(
        marketing_package=package,
        variant_type=variant_type,
        tracked_link=tracked_link,
        defaults={
            **defaults,
            "promoter": promoter,
        },
    )
    changed = False
    for field, value in defaults.items():
        if getattr(variant, field) != value:
            setattr(variant, field, value)
            changed = True
    if promoter and variant.promoter_id != promoter.pk:
        variant.promoter = promoter
        changed = True
    target_url = _poster_variant_target_url(package, tracked_link, target_url)
    image = _draw_poster_variant_image(package, variant, target_url)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    variant.image.save(f"{variant.public_token}.png", ContentFile(output.getvalue()), save=False)
    variant.is_active = True
    update_fields = ["image", "is_active", "updated_at"]
    if changed:
        update_fields.extend(("title", "subtitle", "call_to_action", "promoter"))
    variant.save(update_fields=update_fields)
    return variant


def ensure_base_poster_variants(package):
    variants = []
    for variant_type in (
        PosterVariantType.MOMENTS,
        PosterVariantType.FIELD_DAY,
        PosterVariantType.WEEKLY_RECOMMENDATION,
    ):
        variants.append(generate_poster_variant(package, variant_type))
    return variants


def generate_marketing_images(package):
    snapshot = package.published_observation
    observation = snapshot.observation
    site = observation.site
    configuration = SiteConfiguration.load()
    palette = _marketing_palette(configuration)
    canvas = _gradient_canvas(
        (1080, 1440),
        palette["gradient_top"],
        palette["gradient_bottom"],
    )
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((38, 158, 1042, 842), radius=34, fill=palette["accent"])
    draw.rounded_rectangle((50, 170, 1030, 830), radius=27, fill="white")
    photo = _first_public_photo(package)
    if photo:
        with photo.image.open("rb") as source:
            field_image = Image.open(source).convert("RGB")
            field_image = ImageOps.fit(field_image, (956, 636), method=Image.Resampling.LANCZOS)
            canvas.paste(field_image, (62, 182))
    else:
        draw.text(
            (350, 455),
            "田间真实表现",
            font=_font(48, bold=True),
            fill=palette["secondary"],
        )

    draw.text(
        (64, 34),
        site.variety.name,
        font=_font(58, bold=True),
        fill=palette["accent"],
    )
    draw.text((64, 105), site.name, font=_font(30, bold=True), fill="white")
    draw.text(
        (64, 872),
        observation.get_stage_display(),
        font=_font(68, bold=True),
        fill=palette["accent"],
    )
    y = 975
    for tag in package.core_tags[:3]:
        draw.rounded_rectangle(
            (64, y, 600, y + 58),
            radius=28,
            fill=palette["accent"],
        )
        draw.text(
            (88, y + 9),
            _compact(tag, 20),
            font=_font(27, bold=True),
            fill=palette["primary"],
        )
        y += 72

    qr_image = Image.open(
        BytesIO(
            render_qr_png(
                _public_tracked_url(package),
                fill_color=palette["primary"],
                back_color="white",
            )
        )
    ).convert("RGB")
    qr_image = qr_image.resize((270, 270), Image.Resampling.LANCZOS)
    draw.rounded_rectangle((724, 1006, 1038, 1364), radius=24, fill="white")
    canvas.paste(qr_image, (746, 1026))
    draw.text(
        (762, 1310),
        "扫码查看完整表现",
        font=_font(24, bold=True),
        fill=palette["primary"],
    )

    _paste_brand_logo(canvas, configuration, (870, 32))

    poster_output = BytesIO()
    canvas.save(poster_output, format="PNG", optimize=True)
    package.poster.save(
        f"{package.public_token}.png",
        ContentFile(poster_output.getvalue()),
        save=False,
    )

    cover = _gradient_canvas(
        (1080, 1440),
        palette["gradient_top"],
        palette["gradient_bottom"],
    )
    cover_draw = ImageDraw.Draw(cover, "RGBA")
    _draw_brand_circuit(cover_draw, palette, offset_y=35)
    if photo:
        with photo.image.open("rb") as source:
            field_image = Image.open(source).convert("RGB")
            field_image = ImageOps.fit(field_image, (960, 780), method=Image.Resampling.LANCZOS)
            cover_draw.rounded_rectangle(
                (48, 170, 1032, 974),
                radius=34,
                fill=palette["accent"],
            )
            cover.paste(field_image, (60, 182))
    cover_draw.rectangle((0, 930, 1080, 1440), fill=palette["overlay"])
    cover_draw.rectangle((0, 930, 1080, 948), fill=palette["accent"])
    cover_draw.text(
        (60, 984),
        site.variety.name,
        font=_font(70, bold=True),
        fill=palette["accent"],
    )
    cover_draw.text(
        (60, 1080),
        f"{site.name} · {observation.get_stage_display()}",
        font=_font(36, bold=True),
        fill="white",
    )
    summary_lines = _wrapped_lines(snapshot.public_summary or "田间真实表现", 20)[:2]
    for index, line in enumerate(summary_lines):
        cover_draw.text(
            (60, 1170 + index * 48),
            line,
            font=_font(30),
            fill=palette["accent_soft"],
        )
    _paste_brand_logo(cover, configuration, (870, 42))
    cover_output = BytesIO()
    cover.save(cover_output, format="JPEG", quality=90, optimize=True)
    package.video_cover.save(
        f"{package.public_token}.jpg",
        ContentFile(cover_output.getvalue()),
        save=False,
    )
    package.save(update_fields=("poster", "video_cover", "updated_at"))
    ensure_base_poster_variants(package)
    return package


def refresh_marketing_package(package):
    defaults = build_marketing_defaults(package.published_observation)
    for field, value in defaults.items():
        setattr(package, field, value)
    package.save()
    ensure_short_video_topics(package)
    return generate_marketing_images(package)


def _period_filter(field_name, start_date, end_date):
    start_at = timezone.make_aware(datetime.combine(start_date, time.min))
    end_at = timezone.make_aware(datetime.combine(end_date, time.max))
    return {f"{field_name}__gte": start_at, f"{field_name}__lte": end_at}


def build_marketing_kpis(start_date, end_date):
    from analytics.models import VisitEvent
    from inquiries.models import Inquiry

    visits = VisitEvent.objects.filter(
        marketing_package__isnull=False,
        **_period_filter("occurred_at", start_date, end_date),
    )
    inquiries = Inquiry.objects.filter(
        marketing_package__isnull=False,
        **_period_filter("created_at", start_date, end_date),
    )
    publications = ExternalPublication.objects.filter(
        published_at__isnull=False,
        **_period_filter("published_at", start_date, end_date),
    )
    external_totals = publications.aggregate(
        views=Sum("view_count"),
        likes=Sum("like_count"),
        comments=Sum("comment_count"),
        shares=Sum("share_count"),
    )
    package_visits = (
        visits.values(
            "marketing_package_id",
            "marketing_package__headline",
            "marketing_package__published_observation__observation__site__name",
        )
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )
    package_inquiries = (
        inquiries.values(
            "marketing_package_id",
            "marketing_package__headline",
            "marketing_package__published_observation__observation__site__name",
        )
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )
    promoters = (
        inquiries.values("promotion_identity__name", "promotion_identity__promoter_type")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )
    sources = visits.values("source_code").annotate(total=Count("id")).order_by("-total")[:10]
    return {
        "visit_count": visits.count(),
        "visitor_count": visits.values("visitor_hash").distinct().count(),
        "inquiry_count": inquiries.count(),
        "publication_count": publications.count(),
        "external_views": external_totals["views"] or 0,
        "external_likes": external_totals["likes"] or 0,
        "external_comments": external_totals["comments"] or 0,
        "external_shares": external_totals["shares"] or 0,
        "package_visits": package_visits,
        "package_inquiries": package_inquiries,
        "promoters": promoters,
        "sources": sources,
        "publications": publications.select_related("marketing_package")[:10],
    }


def build_weekly_report_defaults(start_date, end_date):
    kpis = build_marketing_kpis(start_date, end_date)
    source_line = (
        "、".join(f"{row['source_code']} {row['total']} 次" for row in kpis["sources"][:5])
        or "暂无来源数据"
    )
    package_line = (
        "、".join(
            (
                f"{row['marketing_package__published_observation__observation__site__name']} "
                f"{row['total']} 次"
            )
            for row in kpis["package_visits"][:5]
        )
        or "暂无示范点访问排行"
    )
    summary = (
        f"本周营销传播访问 {kpis['visit_count']} 次，独立访客 {kpis['visitor_count']} 个，"
        f"回流咨询 {kpis['inquiry_count']} 条；外部视频/内容登记 {kpis['publication_count']} 条，"
        f"人工回填播放/浏览 {kpis['external_views']} 次。\n"
        f"主要来源：{source_line}。\n"
        f"热门示范点：{package_line}。"
    )
    recommended_actions = (
        "1. 优先跟进本周新增咨询，特别是预约看田、申请试种和代理合作线索。\n"
        "2. 对访问高但咨询少的示范点，补充更明确的咨询入口和区域联系人。\n"
        "3. 对播放量较高的短视频选题，继续拆分同类内容并复用专属二维码。"
    )
    return {
        "title": f"{start_date:%Y.%m.%d}—{end_date:%m.%d} 营销传播周报",
        "summary": summary,
        "recommended_actions": recommended_actions,
    }


def get_or_create_weekly_report(start_date, end_date, user=None):
    defaults = build_weekly_report_defaults(start_date, end_date)
    report, created = MarketingWeeklyReport.objects.get_or_create(
        start_date=start_date,
        end_date=end_date,
        defaults={
            **defaults,
            "created_by": user if getattr(user, "is_authenticated", False) else None,
        },
    )
    if not created and not report.summary:
        for field, value in defaults.items():
            setattr(report, field, value)
        if user and getattr(user, "is_authenticated", False) and report.created_by_id is None:
            report.created_by = user
        report.save()
    return report
