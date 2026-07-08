from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_VIDEO_BYTES = 200 * 1024 * 1024
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}


def validate_image_upload(uploaded_file):
    if uploaded_file.size > MAX_IMAGE_BYTES:
        raise ValidationError("图片不能超过 10 MB。")

    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise ValidationError("仅支持 JPEG、PNG 和 WebP 图片。")

    position = uploaded_file.tell() if hasattr(uploaded_file, "tell") else 0
    try:
        image = Image.open(uploaded_file)
        if image.format not in ALLOWED_IMAGE_FORMATS:
            detected_format = image.format or "未知"
            raise ValidationError(
                f"图片真实格式不受支持（检测为 {detected_format}）；请使用 JPEG、PNG 或 WebP 图片。"
            )
        width, height = image.size
        if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
            raise ValidationError("图片尺寸无效或像素总量超过 4000 万。")
        image.verify()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("文件不是有效图片或图片已经损坏。") from exc
    finally:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(position)


def validate_mp4_upload(uploaded_file):
    if uploaded_file.size <= 0:
        raise ValidationError("视频文件不能为空。")
    if uploaded_file.size > MAX_VIDEO_BYTES:
        raise ValidationError("本地视频不能超过 200 MB。")

    if Path(uploaded_file.name).suffix.lower() != ".mp4":
        raise ValidationError("本地视频仅支持 MP4 文件。")

    position = uploaded_file.tell() if hasattr(uploaded_file, "tell") else 0
    try:
        header = uploaded_file.read(64)
        # MP4 is an ISO Base Media File Format container and normally exposes
        # an ftyp box near the start. Checking the signature rejects renamed files.
        if len(header) < 12 or b"ftyp" not in header[4:64]:
            raise ValidationError("文件不是有效的 MP4 视频。")
    finally:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(position)
