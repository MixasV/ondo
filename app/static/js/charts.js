// Chart.js configuration and utilities

const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            labels: { 
                color: '#9ca3af',
                font: { family: 'Inter' }
            }
        }
    },
    scales: {
        x: { 
            ticks: { color: '#6b7280' },
            grid: { color: '#1f2937' }
        },
        y: { 
            ticks: { color: '#6b7280' },
            grid: { color: '#1f2937' }
        }
    }
};

function createSupplyChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: 'OUSG',
                    data: data.ousg,
                    borderColor: '#00d4aa',
                    backgroundColor: 'rgba(0, 212, 170, 0.1)',
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'USDY',
                    data: data.usdy,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: chartDefaults
    });
}

function createVolumeChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Volume USD',
                data: data.volumes,
                backgroundColor: '#00d4aa'
            }]
        },
        options: chartDefaults
    });
}

function createNAVChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Deviation %',
                data: data.deviations,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            ...chartDefaults,
            plugins: {
                ...chartDefaults.plugins,
                annotation: {
                    annotations: {
                        upperBand: {
                            type: 'line',
                            yMin: 0.5,
                            yMax: 0.5,
                            borderColor: '#f59e0b',
                            borderWidth: 1,
                            borderDash: [5, 5]
                        },
                        lowerBand: {
                            type: 'line',
                            yMin: -0.5,
                            yMax: -0.5,
                            borderColor: '#f59e0b',
                            borderWidth: 1,
                            borderDash: [5, 5]
                        }
                    }
                }
            }
        }
    });
}

// Export for use in templates
window.ChartUtils = {
    createSupplyChart,
    createVolumeChart,
    createNAVChart
};
