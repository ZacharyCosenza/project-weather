let forecastChart = null;

async function loadForecast() {
    showLoading();
    hideError();

    try {
        const response = await fetch('/api/forecast');
        const data = await response.json();

        if (data.success) {
            displayCurrentWeather(data.current_weather, data.location);
            displayForecastChart(data.predictions, data.current_weather.time);
            hideLoading();
        } else {
            showError(data.error || 'Failed to load forecast');
            hideLoading();
        }
    } catch (error) {
        showError('Failed to load forecast: ' + error.message);
        hideLoading();
    }
}

function displayCurrentWeather(weather, location) {
    document.getElementById('location-name').textContent = location;
    document.getElementById('current-temp-value').textContent = weather.temperature.toFixed(1);
    document.getElementById('forecast-description').textContent = weather.forecast;
    document.getElementById('forecast-period-name').textContent = weather.forecast_name;

    const weatherTime = new Date(weather.time);
    const formattedDate = weatherTime.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });
    document.getElementById('weather-timestamp').textContent = formattedDate;
    document.getElementById('forecast-start-time').textContent = formattedDate;

    document.getElementById('current-weather-display').style.display = 'block';
}

function displayForecastChart(predictions, startTimeStr) {
    const ctx = document.getElementById('forecast-chart').getContext('2d');

    const currentTime = new Date();
    const startTime = new Date(startTimeStr);

    const labels = predictions.map(pred => {
        const time = new Date(pred.time);
        return time.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    });

    const temperatures = predictions.map(pred => pred.predicted_temperature);

    const timestamps = predictions.map(pred => new Date(pred.time).getTime());
    const currentTimeMs = currentTime.getTime();

    let currentTimeIndex = null;
    for (let i = 0; i < timestamps.length - 1; i++) {
        if (currentTimeMs >= timestamps[i] && currentTimeMs <= timestamps[i + 1]) {
            const ratio = (currentTimeMs - timestamps[i]) / (timestamps[i + 1] - timestamps[i]);
            currentTimeIndex = i + ratio;
            break;
        }
    }

    if (forecastChart) {
        forecastChart.destroy();
    }

    forecastChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Predicted Temperature (°F)',
                data: temperatures,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBackgroundColor: '#667eea',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        font: {
                            size: 14,
                            weight: '500'
                        }
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return 'Temperature: ' + context.parsed.y.toFixed(1) + '°F';
                        }
                    }
                },
                annotation: currentTimeIndex !== null ? {
                    annotations: {
                        currentTimeLine: {
                            type: 'line',
                            xMin: currentTimeIndex,
                            xMax: currentTimeIndex,
                            borderColor: '#dc3545',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            label: {
                                display: true,
                                content: 'Current Time',
                                position: 'start',
                                backgroundColor: '#dc3545',
                                color: '#fff',
                                font: {
                                    size: 11,
                                    weight: 'bold'
                                }
                            }
                        }
                    }
                } : undefined
            },
            scales: {
                y: {
                    beginAtZero: false,
                    ticks: {
                        callback: function(value) {
                            return value.toFixed(0) + '°F';
                        },
                        font: {
                            size: 12
                        }
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45,
                        font: {
                            size: 11
                        }
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

function showLoading() {
    document.getElementById('loading-spinner').style.display = 'block';
    document.getElementById('current-weather-display').style.display = 'none';
}

function hideLoading() {
    document.getElementById('loading-spinner').style.display = 'none';
}

function showError(message) {
    const errorDiv = document.getElementById('error-message');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

function hideError() {
    document.getElementById('error-message').style.display = 'none';
}

document.addEventListener('DOMContentLoaded', function() {
    loadForecast();
});
