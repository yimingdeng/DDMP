document.addEventListener("DOMContentLoaded", () => {
    const dialog = document.querySelector("#media-lightbox");
    if (!dialog) return;

    const image = dialog.querySelector("[data-lightbox-image]");
    const caption = dialog.querySelector("[data-lightbox-caption]");
    const closeButton = dialog.querySelector("[data-lightbox-close]");
    const previousButton = dialog.querySelector("[data-lightbox-previous]");
    const nextButton = dialog.querySelector("[data-lightbox-next]");
    let items = [];
    let currentIndex = 0;

    const showItem = (index) => {
        if (!items.length) return;
        currentIndex = (index + items.length) % items.length;
        const item = items[currentIndex];
        const thumbnail = item.querySelector("img");
        image.src = item.href;
        image.alt = thumbnail?.alt || "";
        caption.textContent = item.dataset.caption || thumbnail?.alt || "";
        const multiple = items.length > 1;
        previousButton.hidden = !multiple;
        nextButton.hidden = !multiple;
    };

    document.querySelectorAll("[data-media-gallery]").forEach((gallery) => {
        const galleryItems = Array.from(gallery.querySelectorAll("[data-gallery-item]"));
        galleryItems.forEach((item, index) => {
            item.addEventListener("click", (event) => {
                if (typeof dialog.showModal !== "function") return;
                event.preventDefault();
                items = galleryItems;
                showItem(index);
                dialog.showModal();
            });
        });
    });

    closeButton.addEventListener("click", () => dialog.close());
    previousButton.addEventListener("click", () => showItem(currentIndex - 1));
    nextButton.addEventListener("click", () => showItem(currentIndex + 1));
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
    });
    dialog.addEventListener("keydown", (event) => {
        if (event.key === "ArrowLeft") showItem(currentIndex - 1);
        if (event.key === "ArrowRight") showItem(currentIndex + 1);
    });
});
