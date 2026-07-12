from django.core.management.base import BaseCommand

from campaigns.services import ensure_marketing_package, generate_marketing_images
from collection.models import PublishedObservation


class Command(BaseCommand):
    help = "为已公开的阶段快照生成营销文案、朋友圈海报和短视频封面。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--missing-only",
            action="store_true",
            help="仅处理尚未生成海报或视频封面的素材包。",
        )

    def handle(self, *args, **options):
        snapshots = PublishedObservation.objects.select_related(
            "observation__site__variety"
        ).prefetch_related("observation__photos")
        completed = 0
        failed = 0
        for snapshot in snapshots.iterator(chunk_size=100):
            package = ensure_marketing_package(snapshot)
            if (
                options["missing_only"]
                and package.poster
                and package.video_cover
                and package.poster_variants.filter(image__gt="").exists()
            ):
                continue
            try:
                generate_marketing_images(package)
            except Exception as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f"生成失败：{package}（{exc}）"))
            else:
                completed += 1
                self.stdout.write(f"已生成：{package}")
        self.stdout.write(self.style.SUCCESS(f"生成完成：成功 {completed}，失败 {failed}。"))
