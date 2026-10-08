(function () {
    const canvas = document.getElementById("dailyChart");
    if (!canvas) return;

    let chart = null;
    let rendering = false;

    function themeVar(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    async function render() {
        if (rendering) return;
        rendering = true;

        const res = await fetch("/stats/daily");
        const data = await res.json();

        if (chart) chart.destroy();

        if (!data.length) {
            canvas.parentElement.innerHTML = '<p class="empty">Add a habit to see stats.</p>';
            rendering = false;
            return;
        }

        const accent = themeVar("--accent");
        const accentSoft = themeVar("--accent-soft");

        chart = new Chart(canvas, {
            type: "line",
            data: {
                labels: data.map(d => d.label),
                datasets: [{
                    data: data.map(d => d.done),
                    borderColor: accent,
                    backgroundColor: accentSoft + "80",
                    pointHoverBackgroundColor: accent,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 400 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const d = data[ctx.dataIndex];
                                return ` ${d.done} of ${d.total} habits done`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        ticks: {
                            color: themeVar("--muted"),
                            maxTicksLimit: 8,
                            maxRotation: 0,
                            font: { size: 11 },
                        },
                        grid: { display: false },
                        border: { display: false },
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: themeVar("--muted"),
                            stepSize: 1,
                            precision: 0,
                            font: { size: 11 },
                        },
                        grid: { color: themeVar("--border"), drawTicks: false },
                        border: { display: false },
                    },
                },
            },
        });

        rendering = false;
    }

    render();
    window.addEventListener("theme-change", render);
})();