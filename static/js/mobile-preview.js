(() => {
    const url = new URL(window.location.href);
    const isMobilePreview = url.searchParams.get("mobile") === "1";
    const isPreviewFrame = url.searchParams.get("_mobile_frame") === "1";

    if (isPreviewFrame) {
        document.documentElement.classList.add("mobile-preview-document");
        return;
    }

    if (!isMobilePreview || window.matchMedia("(max-width: 560px)").matches) {
        return;
    }

    const frameUrl = new URL(url.href);
    frameUrl.searchParams.delete("mobile");
    frameUrl.searchParams.set("_mobile_frame", "1");

    const showPreview = () => {
        const frame = document.createElement("iframe");
        frame.className = "mobile-preview-frame";
        frame.title = "移动端页面预览";
        frame.src = frameUrl.href;

        frame.addEventListener("load", () => {
            try {
                const currentFrameUrl = new URL(frame.contentWindow.location.href);
                currentFrameUrl.searchParams.delete("_mobile_frame");
                currentFrameUrl.searchParams.set("mobile", "1");
                const displayUrl = `${currentFrameUrl.pathname}${currentFrameUrl.search}${currentFrameUrl.hash}`;
                window.history.replaceState({}, "", displayUrl);
            } catch (error) {
                // External pages cannot be inspected and should keep their own URL.
            }
        });

        document.body.className = "mobile-preview-host";
        document.body.replaceChildren(frame);
        document.documentElement.classList.add("mobile-preview-active");
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", showPreview, { once: true });
    } else {
        showPreview();
    }
})();
