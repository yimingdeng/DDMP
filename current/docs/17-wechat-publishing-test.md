# 微信发布测试集成

相关范围：FR-SHARE-01、FR-SHARE-02、FR-OPS-02。

## 1. 第一阶段目标

第一阶段做“微信内 H5 分享发布测试”，不是公众号自动发文。

完成后，用户在微信里打开：

```text
https://bzb889.originseed.com.cn/
```

或任意品种/示范点详情页，点微信右上角分享时，可使用平台配置的标题、摘要和封面图。

## 2. 公众号后台准备

需要已有服务号或订阅号，并拿到：

```text
AppID
AppSecret
```

在微信公众平台配置：

1. 设置与开发 > 基本配置：确认 AppID/AppSecret。
2. 设置与开发 > 基本配置：把服务器公网出口 IP 加入 IP 白名单。
3. 设置与开发 > 公众号设置 > 功能设置：配置 JS 接口安全域名：

```text
bzb889.originseed.com.cn
```

如果微信要求上传 `MP_verify_xxx.txt`，建议在 Caddy 增加根路径文件映射，例如：

```caddyfile
handle /MP_verify_*.txt {
    root * D:\DDMP-RUNTIME\data\wechat
    file_server
}
```

然后把微信下载的校验文件放到：

```text
D:\DDMP-RUNTIME\data\wechat\MP_verify_xxx.txt
```

## 3. 服务器环境变量

编辑：

```text
D:\DDMP-RUNTIME\config\.env
```

增加：

```dotenv
WECHAT_JS_SDK_ENABLED=true
WECHAT_OFFICIAL_ACCOUNT_APP_ID=你的公众号AppID
WECHAT_OFFICIAL_ACCOUNT_APP_SECRET=你的公众号AppSecret
WECHAT_JS_API_DEBUG=false
```

保存后重启：

```powershell
Restart-Service DDMP-App
```

## 4. 测试步骤

### 4.1 基础访问

```powershell
curl.exe -i https://bzb889.originseed.com.cn/health/
```

### 4.2 检查页面是否加载微信脚本

```powershell
curl.exe -s https://bzb889.originseed.com.cn/ | Select-String "jweixin|wechat-share-meta|wechat-share.js"
```

### 4.3 检查签名接口

```powershell
curl.exe -i "https://bzb889.originseed.com.cn/wechat/js-config/?url=https%3A%2F%2Fbzb889.originseed.com.cn%2F"
```

正常情况下返回 JSON，包含：

```json
{
  "enabled": true,
  "appId": "...",
  "timestamp": 123,
  "nonceStr": "...",
  "signature": "...",
  "jsApiList": ["updateAppMessageShareData", "updateTimelineShareData"]
}
```

如果返回 `wechat_api_unavailable`、`invalid credential` 或 IP 相关错误，通常是 AppSecret 不对或服务器公网 IP 没加到公众号 IP 白名单。

### 4.4 微信手机测试

1. 用微信打开 `https://bzb889.originseed.com.cn/`。
2. 点右上角 `...`。
3. 分享给朋友。
4. 看分享卡片标题、摘要、封面是否符合后台“站点配置/分享配置”。

## 5. 后续阶段

第二阶段再考虑公众号素材/草稿箱/群发能力。那部分需要公众号认证、素材上传接口、草稿接口和运营审核流程，不建议作为第一步。
