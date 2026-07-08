from urllib.parse import urlsplit

from django.conf import settings

from .models import SiteConfiguration


def site_configuration(request):
    configuration = SiteConfiguration.load()
    image_url = ""
    if configuration.default_share_image:
        image_url = request.build_absolute_uri(configuration.default_share_image.url)
    current_url = request.build_absolute_uri()
    parsed_url = urlsplit(current_url)
    canonical_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    return {
        "site_config": configuration,
        "share_meta": {
            "title": configuration.default_share_title or configuration.site_name,
            "description": configuration.default_share_description
            or configuration.meta_description,
            "image_url": image_url,
            "url": canonical_url,
        },
        "wechat_js_sdk_enabled": settings.WECHAT_JS_SDK_ENABLED,
    }
