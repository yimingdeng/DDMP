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
