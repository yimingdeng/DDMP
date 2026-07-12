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

document.addEventListener("DOMContentLoaded", () => {
    const videos = Array.from(document.querySelectorAll("video[data-video-maximize]"));
    if (!videos.length) return;

    let fallbackDialog = null;
    let fallbackVideo = null;
    let sourceVideo = null;

    const getVideoSource = (video) =>
        video.currentSrc || video.src || video.querySelector("source")?.src || "";

    const ensureFallbackDialog = () => {
        if (fallbackDialog) return fallbackDialog;
        fallbackDialog = document.createElement("dialog");
        fallbackDialog.className = "video-fullscreen-dialog";
        fallbackDialog.setAttribute("aria-label", "视频播放");
        fallbackDialog.innerHTML = `
            <button class="video-fullscreen-close" type="button" aria-label="关闭视频">×</button>
            <video controls playsinline></video>
        `;
        document.body.appendChild(fallbackDialog);
        fallbackVideo = fallbackDialog.querySelector("video");
        const closeButton = fallbackDialog.querySelector("button");
        const close = () => {
            if (sourceVideo && fallbackVideo) {
                sourceVideo.currentTime = fallbackVideo.currentTime || 0;
            }
            fallbackVideo.pause();
            fallbackVideo.removeAttribute("src");
            fallbackVideo.load();
            fallbackDialog.close();
            sourceVideo = null;
        };
        closeButton.addEventListener("click", close);
        fallbackDialog.addEventListener("click", (event) => {
            if (event.target === fallbackDialog) close();
        });
        fallbackDialog.addEventListener("cancel", (event) => {
            event.preventDefault();
            close();
        });
        return fallbackDialog;
    };

    const openFallbackPlayer = async (video) => {
        const source = getVideoSource(video);
        if (!source || typeof HTMLDialogElement === "undefined") return false;
        sourceVideo = video;
        const dialog = ensureFallbackDialog();
        fallbackVideo.poster = video.poster || "";
        fallbackVideo.src = source;
        fallbackVideo.currentTime = video.currentTime || 0;
        video.pause();
        if (typeof dialog.showModal === "function" && !dialog.open) {
            dialog.showModal();
        }
        try {
            await fallbackVideo.play();
        } catch (_error) {
            // 用户仍可通过控件手动播放。
        }
        return true;
    };

    const requestVideoFullscreen = async (video) => {
        if (document.fullscreenElement === video) return true;
        if (typeof video.webkitEnterFullscreen === "function") {
            try {
                await video.play();
                video.webkitEnterFullscreen();
                return true;
            } catch (_error) {
                return false;
            }
        }
        const requestFullscreen =
            video.requestFullscreen ||
            video.webkitRequestFullscreen ||
            video.msRequestFullscreen;
        if (!requestFullscreen) return false;
        try {
            await requestFullscreen.call(video);
            if (video.paused) await video.play();
            return true;
        } catch (_error) {
            return false;
        }
    };

    const maximizeAndPlay = async (video) => {
        if (video.dataset.videoMaximizing === "1") return;
        video.dataset.videoMaximizing = "1";
        const maximized = await requestVideoFullscreen(video);
        if (!maximized) await openFallbackPlayer(video);
        window.setTimeout(() => {
            delete video.dataset.videoMaximizing;
        }, 500);
    };

    videos.forEach((video) => {
        video.addEventListener("click", () => maximizeAndPlay(video));
        video.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                maximizeAndPlay(video);
            }
        });
    });
});
