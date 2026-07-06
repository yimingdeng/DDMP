const collectionForm = document.querySelector("[data-observation-form]");

if (collectionForm) {
    const numberValue = (name) => {
        const value = Number.parseFloat(collectionForm.elements[name]?.value || "");
        return Number.isFinite(value) ? value : null;
    };

    const updateCalculations = () => {
        const stage = collectionForm.dataset.stage;
        if (stage === "sowing") {
            const density = numberValue("density");
            const row = numberValue("row_spacing");
            const spacing = density > 0 && row > 0 ? 6666666.67 / (density * row) : null;
            const output = collectionForm.querySelector("[data-calculated-spacing]");
            const input = collectionForm.elements.plant_spacing;
            output.textContent = spacing ? spacing.toFixed(1) : "—";
            if (input) input.value = spacing ? spacing.toFixed(1) : "";
        } else if (stage === "flowering") {
            const tasseling = collectionForm.elements.tasseling_date?.value;
            const silking = collectionForm.elements.silking_date?.value;
            const output = collectionForm.querySelector("[data-flowering-interval]");
            if (tasseling && silking) {
                const days = Math.round((new Date(silking) - new Date(tasseling)) / 86400000);
                output.textContent = days >= 0 ? days : "日期有误";
            } else {
                output.textContent = "—";
            }
        } else if (stage === "harvest") {
            const area = numberValue("actual_area");
            const weight = numberValue("actual_weight");
            const output = collectionForm.querySelector("[data-actual-yield]");
            output.textContent = area > 0 && weight >= 0 ? (weight / area).toFixed(2) : "—";
        }
    };

    collectionForm.addEventListener("input", updateCalculations);
    collectionForm.addEventListener("change", updateCalculations);
    updateCalculations();

    document.querySelectorAll("[data-capture-control]").forEach((control) => {
        const button = control.querySelector("[data-capture-trigger]");
        const status = control.querySelector("[data-capture-status]");
        let capturedCount = 0;

        const activeInput = () => control.querySelector("input[type=file]:not([data-captured])");
        button.addEventListener("click", () => activeInput()?.click());
        control.addEventListener("change", (event) => {
            const input = event.target;
            if (!(input instanceof HTMLInputElement) || input.type !== "file") return;
            const count = input.files?.length || 0;
            if (!count) return;
            capturedCount += count;
            input.dataset.captured = "true";
            const next = input.cloneNode();
            next.removeAttribute("id");
            next.removeAttribute("data-captured");
            next.value = "";
            control.insertBefore(next, button);
            status.textContent = `已拍摄 ${capturedCount} 个文件，可继续${input.accept.startsWith("video") ? "摄像" : "拍照"}`;
            button.textContent = input.accept.startsWith("video") ? "继续摄像" : "继续拍照";
        });
    });
}
