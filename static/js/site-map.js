const viewButtons = document.querySelectorAll("[data-site-view]");
const viewPanels = document.querySelectorAll("[data-site-panel]");
const mapDataElement = document.getElementById("site-map-data");
const amapConfigElement = document.getElementById("amap-config");
let siteMap;
let amapLoading;
const desktopProvinceZoom = 7.2;
const desktopMapWidth = 1200;

function getProvinceViewZoom() {
    const mapWidth = document.getElementById("site-map")?.clientWidth || window.innerWidth || 390;
    const widthAdjustedZoom = desktopProvinceZoom + Math.log2(mapWidth / desktopMapWidth);
    return Math.max(5.4, Math.min(desktopProvinceZoom, widthAdjustedZoom));
}

function distanceInKilometers(latitude, longitude, site) {
    const toRadians = (value) => (value * Math.PI) / 180;
    const latitudeDelta = toRadians(site.latitude - latitude);
    const longitudeDelta = toRadians(site.longitude - longitude);
    const startLatitude = toRadians(latitude);
    const endLatitude = toRadians(site.latitude);
    const haversine =
        Math.sin(latitudeDelta / 2) ** 2
        + Math.cos(startLatitude)
            * Math.cos(endLatitude)
            * Math.sin(longitudeDelta / 2) ** 2;
    return 6371 * 2 * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
}

function convertGpsToAmapCoordinate(AMap, longitude, latitude) {
    return new Promise((resolve) => {
        AMap.convertFrom([longitude, latitude], "gps", (status, result) => {
            if (status === "complete" && result.locations?.length) {
                const location = result.locations[0];
                resolve({ latitude: location.getLat(), longitude: location.getLng() });
                return;
            }
            resolve({ latitude, longitude });
        });
    });
}

function loadAmap() {
    if (window.AMap) return Promise.resolve(window.AMap);
    if (amapLoading) return amapLoading;
    const config = JSON.parse(amapConfigElement?.textContent || "{}");
    if (!config.key) return Promise.reject(new Error("missing-amap-key"));
    window._AMapSecurityConfig = { securityJsCode: config.securityCode || "" };
    amapLoading = new Promise((resolve, reject) => {
        const callbackName = `ddmpAmapReady${Date.now()}`;
        window[callbackName] = () => {
            delete window[callbackName];
            resolve(window.AMap);
        };
        const script = document.createElement("script");
        script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(config.key)}&callback=${callbackName}`;
        script.onerror = reject;
        document.head.appendChild(script);
    });
    return amapLoading;
}

async function initializeSiteMap() {
    const container = document.getElementById("site-map");
    if (!container || siteMap) return;
    const sites = JSON.parse(mapDataElement?.textContent || "[]");
    try {
        const AMap = await loadAmap();
        siteMap = new AMap.Map(container, {
            zoom: 5,
            center: [104, 35.5],
            mapStyle: "amap://styles/whitesmoke",
            viewMode: "2D",
        });
        function openSitePopup(site, marker, distance) {
            const popup = document.createElement("div");
            const title = document.createElement("strong");
            const link = document.createElement("a");
            const distanceText = Number.isFinite(distance)
                ? ` · 距您约 ${distance < 10 ? distance.toFixed(1) : Math.round(distance)} 公里`
                : "";
            title.textContent = `${site.name}${distanceText}`;
            link.href = site.url;
            link.textContent = "查看详情";
            popup.append(title, link);
            new AMap.InfoWindow({
                autoMove: false,
                content: popup,
                offset: new AMap.Pixel(0, -38),
            }).open(siteMap, marker.getPosition());
        }

        function centerSiteMarker(marker) {
            const position = marker.getPosition();
            const applyCenter = () => {
                siteMap.setZoomAndCenter(getProvinceViewZoom(), position, true);
            };
            applyCenter();
            window.requestAnimationFrame(applyCenter);
        }

        const markers = sites.map((site) => {
            const position = [site.longitude, site.latitude];
            const marker = new AMap.Marker({
                anchor: "bottom-center",
                position,
                title: site.name,
            });
            marker.on("click", () => openSitePopup(site, marker));
            siteMap.add(marker);
            return marker;
        });
        if (markers.length === 1) {
            centerSiteMarker(markers[0]);
        }
        else if (markers.length > 1) siteMap.setFitView(markers, false, [40, 40, 40, 40], 11);

        const locationStatus = document.getElementById("map-location-status");
        if (!navigator.geolocation) {
            if (locationStatus) locationStatus.textContent = "浏览器不支持定位，已展示当前区域全部示范点。";
            return;
        }
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const amapCoordinate = await convertGpsToAmapCoordinate(
                    AMap,
                    position.coords.longitude,
                    position.coords.latitude,
                );
                const distances = sites.map((site, index) => ({
                    distance: distanceInKilometers(
                        amapCoordinate.latitude,
                        amapCoordinate.longitude,
                        site,
                    ),
                    index,
                }));
                distances.sort((left, right) => left.distance - right.distance);
                const nearest = distances[0];
                const nearestSite = sites[nearest.index];
                const nearestMarker = markers[nearest.index];
                openSitePopup(nearestSite, nearestMarker, nearest.distance);
                centerSiteMarker(nearestMarker);
                if (locationStatus) {
                    const distance = nearest.distance < 10
                        ? nearest.distance.toFixed(1)
                        : Math.round(nearest.distance);
                    locationStatus.textContent = `离您最近的是“${nearestSite.name}”，直线距离约 ${distance} 公里。`;
                }
            },
            () => {
                if (locationStatus) {
                    locationStatus.textContent = "未获得定位权限，已展示当前区域全部示范点。";
                }
            },
            { enableHighAccuracy: false, maximumAge: 300000, timeout: 10000 },
        );
    } catch (error) {
        container.classList.add("map-configuration-missing");
        container.textContent = error.message === "missing-amap-key"
            ? "地图尚未配置：请管理员在站点配置中填写高德地图 JS API Key 和安全密钥。"
            : "高德地图加载失败，请检查网络、Key 和安全域名配置。";
    }
}

function setSiteView(mode) {
    viewButtons.forEach((button) => {
        const active = button.dataset.siteView === mode;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
    });
    viewPanels.forEach((panel) => {
        panel.hidden = panel.dataset.sitePanel !== mode;
    });
    if (mode === "map") initializeSiteMap();
}

viewButtons.forEach((button) => {
    button.addEventListener("click", () => setSiteView(button.dataset.siteView));
});

setSiteView("map");
