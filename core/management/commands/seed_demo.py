from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import PublicationStatus, SiteConfiguration
from sites.models import Contact, DemoSite, GrowthStage, Region, VisitingStatus
from varieties.models import SellingPoint, SellingPointType, Variety


class Command(BaseCommand):
    help = "创建本地演示品种、卖点、示范点和联系人；命令可重复执行。"

    def handle(self, *args, **options):
        now = timezone.now()
        configuration = SiteConfiguration.load()
        configuration.company_name = "演示种业公司"
        configuration.footer_text = "本地演示环境 · 页面内容仅用于功能测试"
        configuration.contact_phone = "13800000000"
        configuration.save()

        variety, _ = Variety.objects.update_or_create(
            slug="demo-corn-a",
            defaults={
                "name": "示范玉米A（演示数据）",
                "positioning": "以稳产、抗倒和适应性展示为重点的演示品种",
                "summary": (
                    "本品种及页面数据均为系统演示内容，用于验证品种、卖点和示范点的"
                    "展示流程，不代表正式审定或推广结论。"
                ),
                "approval_number": "演示编号-001",
                "suitable_area": "黄淮海区域（演示）",
                "maturity": "中熟",
                "plant_type": "紧凑型",
                "ear_type": "筒型",
                "grain_type": "半马齿型",
                "density_min": 4500,
                "density_max": 5500,
                "sowing_advice": "根据当地墒情和农时安排播种，演示数据不作为生产建议。",
                "water_fertilizer_management": "结合土壤基础和长势进行管理。",
                "cultivation_points": "合理密植，关注关键生育阶段的水肥和病虫害管理。",
                "risk_warning": "本页面为演示内容，正式种植前请以审定公告和技术指导为准。",
                "is_featured": True,
                "sort_order": 10,
                "status": PublicationStatus.PUBLISHED,
                "published_at": now,
                "internal_notes": "DEMO_SEED",
            },
        )

        points = [
            (
                "稳产表现",
                "stable-yield",
                SellingPointType.YIELD,
                "展示不同区域示范点的综合表现和田间整齐度。",
                "通过多个示范点的持续记录，观察不同环境下的田间表现。",
            ),
            (
                "抗倒观察",
                "lodging-resistance",
                SellingPointType.LODGING,
                "重点记录成熟期站秆、倒伏和倒折情况。",
                "结合种植密度、天气和田间管理，持续更新成熟期观察。",
            ),
            (
                "脱水进度",
                "dehydration",
                SellingPointType.DEHYDRATION,
                "通过成熟和收获阶段记录观察籽粒脱水进度。",
                "后续采集端上线后，将关联阶段调查数据和现场图片。",
            ),
            (
                "商品性展示",
                "grain-quality",
                SellingPointType.QUALITY,
                "展示果穗整齐度、籽粒外观和收获表现。",
                "图片与视频素材将在 Sprint 3 接入。",
            ),
        ]
        for order, (title, slug, point_type, short_description, detail) in enumerate(
            points, start=1
        ):
            SellingPoint.objects.update_or_create(
                variety=variety,
                slug=slug,
                defaults={
                    "title": title,
                    "point_type": point_type,
                    "short_description": short_description,
                    "detail": detail,
                    "data_note": "当前为演示说明，不包含正式试验数据。",
                    "sort_order": order * 10,
                    "status": PublicationStatus.PUBLISHED,
                    "published_at": now,
                    "internal_basis": "DEMO_SEED",
                },
            )

        site_specs = [
            {
                "name": "河南新乡示范点（演示）",
                "slug": "demo-xinxiang",
                "province": "河南省",
                "city": "新乡市",
                "county": "演示区县",
                "township_village": "演示乡镇",
                "latitude": "35.303000",
                "longitude": "113.926800",
                "stage": GrowthStage.MATURITY,
                "performance": "成熟期站秆整齐，现场内容持续更新。",
                "visiting": VisitingStatus.OPEN,
            },
            {
                "name": "山东德州示范点（演示）",
                "slug": "demo-dezhou",
                "province": "山东省",
                "city": "德州市",
                "county": "演示区县",
                "township_village": "演示乡镇",
                "latitude": "37.435500",
                "longitude": "116.359300",
                "stage": GrowthStage.FILLING,
                "performance": "灌浆期长势整齐，保绿表现正在观察。",
                "visiting": VisitingStatus.NOT_OPEN,
            },
            {
                "name": "河北邯郸示范点（演示）",
                "slug": "demo-handan",
                "province": "河北省",
                "city": "邯郸市",
                "county": "演示区县",
                "township_village": "演示乡镇",
                "latitude": "36.625600",
                "longitude": "114.539100",
                "stage": GrowthStage.MATURITY,
                "performance": "成熟期果穗整齐度和脱水进度持续记录。",
                "visiting": VisitingStatus.CLOSED,
            },
        ]

        created_sites = []
        for order, spec in enumerate(site_specs, start=1):
            site, _ = DemoSite.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["name"],
                    "variety": variety,
                    "region": Region.HUANG_HUAI_HAI,
                    "province": spec["province"],
                    "city": spec["city"],
                    "county": spec["county"],
                    "township_village": spec["township_village"],
                    "latitude": spec["latitude"],
                    "longitude": spec["longitude"],
                    "show_township": True,
                    "show_detailed_address": False,
                    "area_mu": 20 + order * 5,
                    "sowing_date": date(2026, 6, min(order * 2, 28)),
                    "planting_density": 4800 + order * 100,
                    "planting_mode": "夏播 · 机播（演示）",
                    "current_stage": spec["stage"],
                    "main_performance": spec["performance"],
                    "description": (
                        "这是用于验证系统功能的示范点介绍。后续可在后台替换为真实的"
                        "种植信息、田间表现和负责人评价。"
                    ),
                    "is_featured": True,
                    "visiting_status": spec["visiting"],
                    "visiting_note": "请提前联系确认，当前为演示信息。",
                    "sort_order": order * 10,
                    "status": PublicationStatus.PUBLISHED,
                    "published_at": now,
                    "internal_owner": "演示负责人",
                    "internal_notes": "DEMO_SEED",
                },
            )
            created_sites.append(site)

        contact, _ = Contact.objects.update_or_create(
            phone="13800000000",
            defaults={
                "name": "演示联系人",
                "role_title": "区域服务人员",
                "region": "黄淮海（演示）",
                "show_name": True,
                "show_phone": True,
                "is_active": True,
                "sort_order": 10,
            },
        )
        contact.sites.set(created_sites)

        self.stdout.write(self.style.SUCCESS("演示数据已创建或更新。"))
        self.stdout.write(f"品种页面：{variety.get_absolute_url()}")
        self.stdout.write("示范点列表：/sites/")
