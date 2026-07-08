document.querySelectorAll("form[data-prevent-double-submit]").forEach((form) => {
    form.addEventListener("submit", () => {
        const button = form.querySelector('button[type="submit"]');
        if (!button) return;
        button.disabled = true;
        button.setAttribute("aria-disabled", "true");
        button.textContent = button.dataset.submitLabel || "提交中…";
    });
});

document.querySelectorAll("[data-flash-message]").forEach((message) => {
    let dismissTimer;
    const dismiss = () => {
        if (message.classList.contains("is-leaving")) return;
        message.classList.add("is-leaving");
        window.setTimeout(() => {
            const stack = message.parentElement;
            message.remove();
            if (stack && !stack.querySelector("[data-flash-message]")) stack.remove();
        }, 220);
    };
    const closeButton = message.querySelector("[data-dismiss-message]");
    if (closeButton) closeButton.addEventListener("click", dismiss);
    const delay = Number(message.dataset.autoDismissMs || 0);
    if (delay > 0) {
        dismissTimer = window.setTimeout(dismiss, delay);
        message.addEventListener("mouseenter", () => window.clearTimeout(dismissTimer));
        message.addEventListener("mouseleave", () => {
            dismissTimer = window.setTimeout(dismiss, 2000);
        });
    }
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
