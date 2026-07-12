import hashlib

import pytest
from django.urls import reverse

from core.models import SiteConfiguration
from core.wechat import build_js_sdk_config, build_signature


def test_wechat_js_config_is_disabled_without_credentials(client, settings):
    settings.WECHAT_JS_SDK_ENABLED = True
    settings.WECHAT_OFFICIAL_ACCOUNT_APP_ID = ""
    settings.WECHAT_OFFICIAL_ACCOUNT_APP_SECRET = ""
    response = client.get(
        reverse("core:wechat-js-config"),
        {"url": "http://testserver/"},
        HTTP_HOST="testserver",
    )
    assert response.status_code == 200
    assert response.json() == {"enabled": False, "reason": "wechat_js_sdk_not_configured"}


def test_wechat_js_config_rejects_external_url(client, settings):
    settings.WECHAT_JS_SDK_ENABLED = True
    response = client.get(
        reverse("core:wechat-js-config"),
        {"url": "https://evil.example/"},
        HTTP_HOST="bzb889.originseed.com.cn",
    )
    assert response.status_code == 400


def test_wechat_signature_uses_official_parameter_order():
    signature = build_signature(
        ticket="ticket",
        nonce_str="nonce",
        timestamp=1234567890,
        url="https://bzb889.originseed.com.cn/",
    )
    expected_raw = (
        "jsapi_ticket=ticket&noncestr=nonce&"
        "timestamp=1234567890&url=https://bzb889.originseed.com.cn/"
    )
    assert signature == hashlib.sha1(expected_raw.encode("utf-8")).hexdigest()


def test_wechat_js_sdk_config_includes_new_and_legacy_share_apis(monkeypatch, settings):
    settings.WECHAT_JS_SDK_ENABLED = True
    settings.WECHAT_OFFICIAL_ACCOUNT_APP_ID = "wx-test"
    settings.WECHAT_OFFICIAL_ACCOUNT_APP_SECRET = "secret"
    monkeypatch.setattr("core.wechat.get_jsapi_ticket", lambda: "ticket")

    config = build_js_sdk_config("https://bzb889.originseed.com.cn/")

    assert set(config["jsApiList"]) >= {
        "updateAppMessageShareData",
        "updateTimelineShareData",
        "onMenuShareAppMessage",
        "onMenuShareTimeline",
    }


@pytest.mark.django_db
def test_wechat_js_sdk_scripts_render_when_enabled(client, settings):
    settings.WECHAT_JS_SDK_ENABLED = True
    SiteConfiguration.load()
    response = client.get(reverse("core:home"))
    content = response.content.decode()
    assert "wechat-share-meta" in content
    assert "https://res.wx.qq.com/open/js/jweixin-1.6.0.js" in content
    assert "/static/js/wechat-share.js" in content
