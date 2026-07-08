import hashlib
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

from django.conf import settings
from django.core.cache import cache

from .models import SiteConfiguration

ACCESS_TOKEN_URL = (
    "https://api.weixin.qq.com/cgi-bin/token"
    "?grant_type=client_credential&appid={app_id}&secret={app_secret}"
)
JSAPI_TICKET_URL = (
    "https://api.weixin.qq.com/cgi-bin/ticket/getticket?access_token={token}&type=jsapi"
)


class WeChatConfigurationError(RuntimeError):
    pass


def wechat_enabled():
    return bool(
        settings.WECHAT_JS_SDK_ENABLED
        and settings.WECHAT_OFFICIAL_ACCOUNT_APP_ID
        and settings.WECHAT_OFFICIAL_ACCOUNT_APP_SECRET
    )


def validate_wechat_share_url(request, target_url):
    parsed = urlsplit(target_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    request_host = request.get_host().lower()
    target_host = parsed.netloc.lower()
    if target_host == request_host:
        return True
    allowed_hosts = {request_host}
    public_base_url = SiteConfiguration.load().public_base_url
    if public_base_url:
        public_host = urlsplit(public_base_url).netloc.lower()
        if public_host:
            allowed_hosts.add(public_host)
    return target_host in allowed_hosts


def build_signature(*, ticket, nonce_str, timestamp, url):
    raw = f"jsapi_ticket={ticket}&noncestr={nonce_str}&timestamp={timestamp}&url={url}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def build_js_sdk_config(url):
    if not wechat_enabled():
        raise WeChatConfigurationError("wechat_js_sdk_not_configured")
    nonce_str = secrets.token_hex(8)
    timestamp = int(time.time())
    ticket = get_jsapi_ticket()
    return {
        "enabled": True,
        "debug": settings.WECHAT_JS_API_DEBUG,
        "appId": settings.WECHAT_OFFICIAL_ACCOUNT_APP_ID,
        "timestamp": timestamp,
        "nonceStr": nonce_str,
        "signature": build_signature(
            ticket=ticket,
            nonce_str=nonce_str,
            timestamp=timestamp,
            url=url,
        ),
        "jsApiList": [
            "updateAppMessageShareData",
            "updateTimelineShareData",
        ],
    }


def get_jsapi_ticket():
    ticket = cache.get("wechat:jsapi_ticket")
    if ticket:
        return ticket
    token = get_access_token()
    payload = fetch_wechat_json(JSAPI_TICKET_URL.format(token=token))
    ticket = payload.get("ticket")
    if not ticket:
        raise WeChatConfigurationError(payload.get("errmsg", "missing_jsapi_ticket"))
    expires_in = max(int(payload.get("expires_in", 7200)) - 300, 60)
    cache.set("wechat:jsapi_ticket", ticket, expires_in)
    return ticket


def get_access_token():
    token = cache.get("wechat:access_token")
    if token:
        return token
    payload = fetch_wechat_json(
        ACCESS_TOKEN_URL.format(
            app_id=settings.WECHAT_OFFICIAL_ACCOUNT_APP_ID,
            app_secret=settings.WECHAT_OFFICIAL_ACCOUNT_APP_SECRET,
        )
    )
    token = payload.get("access_token")
    if not token:
        raise WeChatConfigurationError(payload.get("errmsg", "missing_access_token"))
    expires_in = max(int(payload.get("expires_in", 7200)) - 300, 60)
    cache.set("wechat:access_token", token, expires_in)
    return token


def fetch_wechat_json(url):
    try:
        with urlopen(url, timeout=8) as response:  # noqa: S310
            import json

            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise WeChatConfigurationError("wechat_api_unavailable") from exc
