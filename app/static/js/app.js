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
async function incrementFlexible(habitId, btnElement) {
    // Get CSRF token from the first form on the page
    const csrfToken = document.querySelector('input[name="csrf_token"]').value;
    const originalText = btnElement.textContent;
    
    btnElement.textContent = '...';
    btnElement.disabled = true;

    try {
        const res = await fetch(`/flexible/increment/${habitId}`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json'
            }
        });
        
        if (!res.ok) throw new Error('Network response was not ok');
        
        const data = await res.json();
        
        const countSpan = document.getElementById(`count-${habitId}`);
        if (countSpan) {
            const period = countSpan.dataset.period;
            countSpan.textContent = `${data.count} this ${period}`;
        }
        
        // Flash success
        btnElement.textContent = '✓';
        setTimeout(() => {
            btnElement.textContent = originalText;
            btnElement.disabled = false;
        }, 1000);
        
    } catch (err) {
        console.error(err);
        btnElement.textContent = originalText;
        btnElement.disabled = false;
        alert('Failed to log habit. Please try again.');
    }
}