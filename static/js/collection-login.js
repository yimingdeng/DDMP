const loginForm = document.querySelector("[data-login-form]");

if (loginForm) {
    const username = loginForm.elements.username;
    username.value = username.value || window.localStorage.getItem("ddmp_last_username") || "";
    loginForm.addEventListener("submit", () => {
        window.localStorage.setItem("ddmp_last_username", username.value.trim());
    });
}
