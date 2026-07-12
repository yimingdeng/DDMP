document.querySelectorAll("[data-copy-target]").forEach((button) => {
    button.addEventListener("click", async () => {
        const source = document.getElementById(button.dataset.copyTarget);
        if (!source) return;
        const text = "value" in source ? source.value : source.textContent.trim();
        try {
            await navigator.clipboard.writeText(text);
        } catch {
            const temporary = document.createElement("textarea");
            temporary.value = text;
            temporary.style.position = "fixed";
            temporary.style.opacity = "0";
            document.body.appendChild(temporary);
            temporary.select();
            document.execCommand("copy");
            temporary.remove();
        }
        const original = button.textContent;
        button.textContent = "已复制";
        window.setTimeout(() => {
            button.textContent = original;
        }, 1600);
    });
});
