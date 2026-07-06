from urllib.parse import urlsplit

from .models import SiteConfiguration


def build_share_meta(request, *, title="", description="", image_url=""):
    configuration = SiteConfiguration.load()
    absolute_image_url = request.build_absolute_uri(image_url) if image_url else ""
    if not absolute_image_url and configuration.default_share_image:
        absolute_image_url = request.build_absolute_uri(configuration.default_share_image.url)

    parsed_url = urlsplit(request.build_absolute_uri())
    canonical_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    return {
        "title": title or configuration.default_share_title or configuration.site_name,
        "description": description
        or configuration.default_share_description
        or configuration.meta_description,
        "image_url": absolute_image_url,
        "url": canonical_url,
    }
