(() => {
    const locateButton = document.querySelector("[data-site-locate]");
    const status = document.querySelector("[data-site-location-status]");
    const latitudeInput = document.querySelector("#id_latitude");
    const longitudeInput = document.querySelector("#id_longitude");

    if (!locateButton || !status || !latitudeInput || !longitudeInput) return;

    const PI = Math.PI;
    const A = 6378245.0;
    const EE = 0.00669342162296594323;

    const outsideChina = (latitude, longitude) =>
        longitude < 72.004 || longitude > 137.8347 || latitude < 0.8293 || latitude > 55.8271;

    function transformLatitude(x, y) {
        let value = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
        value += ((20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2) / 3;
        value += ((20 * Math.sin(y * PI) + 40 * Math.sin((y / 3) * PI)) * 2) / 3;
        return value + ((160 * Math.sin((y / 12) * PI) + 320 * Math.sin((y * PI) / 30)) * 2) / 3;
    }

    function transformLongitude(x, y) {
        let value = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
        value += ((20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2) / 3;
        value += ((20 * Math.sin(x * PI) + 40 * Math.sin((x / 3) * PI)) * 2) / 3;
        return value + ((150 * Math.sin((x / 12) * PI) + 300 * Math.sin((x / 30) * PI)) * 2) / 3;
    }

    function wgs84ToGcj02(latitude, longitude) {
        if (outsideChina(latitude, longitude)) return { latitude, longitude };
        let deltaLatitude = transformLatitude(longitude - 105, latitude - 35);
        let deltaLongitude = transformLongitude(longitude - 105, latitude - 35);
        const radians = (latitude / 180) * PI;
        let magic = Math.sin(radians);
        magic = 1 - EE * magic * magic;
        const sqrtMagic = Math.sqrt(magic);
        deltaLatitude = (deltaLatitude * 180) / (((A * (1 - EE)) / (magic * sqrtMagic)) * PI);
        deltaLongitude = (deltaLongitude * 180) / ((A / sqrtMagic) * Math.cos(radians) * PI);
        return { latitude: latitude + deltaLatitude, longitude: longitude + deltaLongitude };
    }

    function showError(error) {
        const messages = {
            1: "定位权限被拒绝，请在浏览器设置中允许定位，或手工填写坐标。",
            2: "暂时无法获取当前位置，请到开阔处重试，或手工填写坐标。",
            3: "定位超时，请重试，或手工填写坐标。",
        };
        status.textContent = messages[error.code] || "定位失败，请重试或手工填写坐标。";
        status.classList.add("error");
        locateButton.disabled = false;
    }

    locateButton.addEventListener("click", () => {
        if (!navigator.geolocation) {
            status.textContent = "当前浏览器不支持定位，请手工填写坐标。";
            status.classList.add("error");
            return;
        }
        locateButton.disabled = true;
        status.classList.remove("error");
        status.textContent = "正在定位，请保持页面打开……";
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const converted = wgs84ToGcj02(position.coords.latitude, position.coords.longitude);
                latitudeInput.value = converted.latitude.toFixed(6);
                longitudeInput.value = converted.longitude.toFixed(6);
                const accuracy = Math.round(position.coords.accuracy);
                status.textContent = `定位成功，精度约 ${accuracy} 米；坐标将在保存后上传后台。`;
                locateButton.disabled = false;
            },
            showError,
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
        );
    });
})();
