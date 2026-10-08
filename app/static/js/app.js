(function () {
    const root = document.documentElement;

    function applyTheme(theme) {
        if (theme === "dark") {
            root.setAttribute("data-theme", "dark");
        } else {
            root.removeAttribute("data-theme");
        }
        window.dispatchEvent(new Event("theme-change"));
    }

    applyTheme(localStorage.getItem("theme") || "light");

    const btn = document.getElementById("theme-toggle");
    if (btn) {
        btn.addEventListener("click", () => {
            const isDark = root.getAttribute("data-theme") === "dark";
            const next = isDark ? "light" : "dark";
            applyTheme(next);
            localStorage.setItem("theme", next);
        });
    }
})();