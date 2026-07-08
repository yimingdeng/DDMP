document.querySelectorAll("form[data-prevent-double-submit]").forEach((form) => {
    form.addEventListener("submit", () => {
        const button = form.querySelector('button[type="submit"]');
        if (!button) return;
        button.disabled = true;
        button.setAttribute("aria-disabled", "true");
        button.textContent = button.dataset.submitLabel || "提交中…";
    });
});

if (/aweme|douyin|bytedance/i.test(navigator.userAgent)) {
    document.documentElement.classList.add("douyin-browser");
}

const homeFirstAction = document.querySelector("[data-home-first-action]");
if (homeFirstAction) {
    const icon = homeFirstAction.querySelector("span");
    const labelNode = Array.from(homeFirstAction.childNodes).find(
        (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim(),
    );
    const contactHashes = new Set(["#regional-contacts", "#contact", "#inquiry"]);

    const updateHomeFirstAction = () => {
        const inContactSection = contactHashes.has(window.location.hash);
        homeFirstAction.href = inContactSection
            ? "#main-content"
            : homeFirstAction.dataset.defaultHref;
        if (icon) {
            icon.textContent = inContactSection ? "‹" : homeFirstAction.dataset.defaultIcon;
        }
        if (labelNode) {
            labelNode.textContent = inContactSection
                ? "返回"
                : homeFirstAction.dataset.defaultLabel;
        }
    };

    updateHomeFirstAction();
    window.addEventListener("hashchange", updateHomeFirstAction);
}
