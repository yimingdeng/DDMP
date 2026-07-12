const demoApplicationForm = document.querySelector("[data-demo-application-form]");

if (demoApplicationForm) {
    const countyInput = demoApplicationForm.querySelector('[name="county"]');
    const townshipInput = demoApplicationForm.querySelector('[name="township_village"]');
    const siteNameInput = demoApplicationForm.querySelector('[name="proposed_site_name"]');
    let siteNameEdited = Boolean(siteNameInput?.value.trim());

    function buildDefaultSiteName() {
        const county = countyInput?.value.trim() || "";
        const township = townshipInput?.value.trim() || "";
        return `${county}${township}`;
    }

    function updateDefaultSiteName() {
        if (!siteNameInput || siteNameEdited) return;
        siteNameInput.value = buildDefaultSiteName();
    }

    siteNameInput?.addEventListener("input", () => {
        siteNameEdited = siteNameInput.value.trim() !== buildDefaultSiteName();
    });
    countyInput?.addEventListener("input", updateDefaultSiteName);
    townshipInput?.addEventListener("input", updateDefaultSiteName);
    updateDefaultSiteName();
}
