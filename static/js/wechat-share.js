(function () {
  const wxObject = window.wx;
  if (!wxObject) {
    return;
  }

  const metaElement = document.getElementById("wechat-share-meta");
  if (!metaElement) {
    return;
  }

  let shareMeta;
  try {
    shareMeta = JSON.parse(metaElement.textContent);
  } catch (error) {
    console.warn("Invalid WeChat share metadata.", error);
    return;
  }

  const pageUrl = window.location.href.split("#")[0];
  const configUrl = `/wechat/js-config/?url=${encodeURIComponent(pageUrl)}`;

  fetch(configUrl, { credentials: "same-origin" })
    .then((response) => response.json())
    .then((config) => {
      if (!config.enabled) {
        console.warn("WeChat JS-SDK is not enabled.", config.reason || "");
        return;
      }
      wxObject.config(config);
      wxObject.ready(() => {
        const sharePayload = {
          title: shareMeta.title,
          desc: shareMeta.description,
          link: shareMeta.url || pageUrl,
          imgUrl: shareMeta.image_url || "",
        };
        if (typeof wxObject.updateAppMessageShareData === "function") {
          wxObject.updateAppMessageShareData(sharePayload);
        }
        if (typeof wxObject.updateTimelineShareData === "function") {
          wxObject.updateTimelineShareData({
            title: shareMeta.title,
            link: shareMeta.url || pageUrl,
            imgUrl: shareMeta.image_url || "",
          });
        }
        if (typeof wxObject.onMenuShareAppMessage === "function") {
          wxObject.onMenuShareAppMessage(sharePayload);
        }
        if (typeof wxObject.onMenuShareTimeline === "function") {
          wxObject.onMenuShareTimeline({
            title: shareMeta.title,
            link: shareMeta.url || pageUrl,
            imgUrl: shareMeta.image_url || "",
          });
        }
      });
      wxObject.error((error) => {
        console.warn("WeChat JS-SDK config failed.", error);
      });
    })
    .catch((error) => {
      console.warn("Failed to load WeChat JS-SDK config.", error);
    });
})();
