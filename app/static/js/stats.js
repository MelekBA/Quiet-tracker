(function () {
    const canvas = document.getElementById("completionChart");
    if (!canvas) return;

    let chart = null;
    let rendering = false;

    function themeVar(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    async function render() {
        if (rendering) return;
        rendering = true;

        const res = await fetch("/stats");
        const data = await res.json();

        if (chart) chart.destroy();

        if (!data.length) {
            canvas.parentElement.innerHTML = '<p class="empty">Add a habit to see stats.</p>';
            rendering = false;
            return;
        }

        chart = new Chart(canvas, {
            type: "bar",
            data: {
                labels: data.map(h => h.name),
                datasets: [{
                    data: data.map(h => h.rate),
                    backgroundColor: data.map(h => h.color + "cc"),
                    borderColor: data.map(h => h.color),
                    borderWidth: 1,
                    borderRadius: 8,
                    barThickness: 22,
                }],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 400 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const h = data[ctx.dataIndex];
                                const started = h.days_old === 1
                                    ? " (started today)"
                                    : ` (day ${h.days_old})`;
                                return ` ${h.done} of ${h.window} days · ${h.rate}%${started}`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        min: 0,
                        max: 100,
                        ticks: {
                            color: themeVar("--muted"),
                            callback: (v) => v + "%",
                            font: { size: 11 },
                        },
                        grid: { display: false },
                        border: { display: false },
                    },
                    y: {
                        ticks: {
                            color: themeVar("--text"),
                            font: { size: 12, weight: "500" },
                        },
                        grid: { display: false },
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