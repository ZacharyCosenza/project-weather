let forecastChart = null;
let historicalChart = null;

async function loadForecast() {
    showLoading();
    hideError();

    try {
        const response = await fetch('/api/forecast');
        const data = await response.json();

        if (data.success) {
            displayCurrentWeather(data.current_weather, data.location);
            displayShapContributions(data.shap);
            displayWeatherBot(data.weather_bot);
            displayCharts(data.predictions, data.current_weather.time, data.historical);
            displayTechnicalDetails(data.technical, data.current_weather.time);
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

function getTemperatureEmoji(tempF) {
    if (tempF <= 20) return '🥶';
    if (tempF <= 32) return '❄️';
    if (tempF <= 50) return '🌬️';
    if (tempF <= 65) return '🌤️';
    if (tempF <= 80) return '☀️';
    if (tempF <= 95) return '🔥';
    return '🌡️';
}

function displayCurrentWeather(weather, location) {
    document.getElementById('location-name').textContent = location;
    document.getElementById('current-temp-value').textContent = weather.temperature.toFixed(1);
    document.getElementById('forecast-description').textContent = weather.forecast;
    document.getElementById('forecast-period-name').textContent = weather.forecast_name;
    document.getElementById('weather-emoji').textContent = getTemperatureEmoji(weather.temperature);

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

    document.getElementById('top-cards-container').style.display = 'flex';
}

function displayWeatherBot(botData) {
    const messageEl = document.getElementById('weather-bot-message');
    const modelEl = document.getElementById('weather-bot-model');

    if (botData && botData.summary) {
        messageEl.textContent = botData.summary;
        modelEl.textContent = `powered by ${botData.model_name}`;
    } else {
        messageEl.textContent = 'Weather-Bot model not available. Run the notebook to download the model.';
        messageEl.classList.add('weather-bot-unavailable');
        modelEl.textContent = '';
    }
}

function displayTechnicalDetails(technical, updateTime) {
    if (!technical) return;

    document.getElementById('technical-details').style.display = 'block';

    const features = technical.feature_columns || [];
    const featureNames = features.map(f => f.replace('ft_', '').replace(/_/g, ' ')).join(', ');
    document.getElementById('tech-features').textContent = featureNames || '-';

    document.getElementById('tech-lags').textContent = `${technical.num_lags} hours`;
    document.getElementById('tech-llm').textContent = technical.llm_model || '-';

    const updatedTime = new Date(updateTime);
    document.getElementById('tech-updated').textContent = updatedTime.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });
}

function displayShapContributions(shapData) {
    if (!shapData || !shapData.contributions) return;

    const colors = {
        'Month': '#667eea',
        'Day': '#764ba2',
        'Hour': '#f093fb',
        'Current Temp': '#4facfe'
    };

    const barContainer = document.getElementById('shap-stacked-bar');
    const legendContainer = document.getElementById('shap-legend');

    barContainer.innerHTML = '';
    legendContainer.innerHTML = '';

    shapData.contributions.forEach(item => {
        const segment = document.createElement('div');
        segment.className = 'shap-segment';
        segment.style.width = item.percentage + '%';
        segment.style.backgroundColor = colors[item.feature] || '#999';
        segment.title = `${item.feature}: ${item.percentage.toFixed(1)}%`;
        barContainer.appendChild(segment);
    });

    shapData.contributions.forEach(item => {
        const legendItem = document.createElement('div');
        legendItem.className = 'shap-legend-item';

        const colorBox = document.createElement('span');
        colorBox.className = 'shap-legend-color';
        colorBox.style.backgroundColor = colors[item.feature] || '#999';

        const label = document.createElement('span');
        label.className = 'shap-legend-label';
        label.textContent = `${item.feature}: ${item.percentage.toFixed(1)}%`;

        legendItem.appendChild(colorBox);
        legendItem.appendChild(label);
        legendContainer.appendChild(legendItem);
    });
}

function displayCharts(predictions, _startTimeStr, historical) {
    document.getElementById('charts-row-container').style.display = 'flex';

    const currentTime = new Date();
    const labels = predictions.map(pred => {
        const time = new Date(pred.time);
        return time.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    });

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

    displayPredictionChart(predictions, labels, currentTimeIndex);
    displayHistoricalChart(historical, labels);
}

function displayPredictionChart(predictions, labels, currentTimeIndex) {
    const ctx = document.getElementById('forecast-chart').getContext('2d');
    const temperatures = predictions.map(pred => pred.predicted_temperature);

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
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return 'Predicted: ' + context.parsed.y.toFixed(1) + '°F';
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
                                content: 'Now',
                                position: 'start',
                                backgroundColor: '#dc3545',
                                color: '#fff',
                                font: {
                                    size: 10,
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
                            return value.toFixed(1) + '°F';
                        },
                        font: {
                            size: 11
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
                            size: 10
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

function displayHistoricalChart(historical, labels) {
    const ctx = document.getElementById('historical-chart').getContext('2d');

    if (historicalChart) {
        historicalChart.destroy();
    }

    const historicalColors = [
        '#667eea',
        '#764ba2',
        '#f093fb',
        '#f5576c',
        '#4facfe'
    ];

    const historicalDatasets = (historical || []).map((yearData, index) => ({
        label: `${yearData.year}`,
        data: yearData.temperatures,
        borderColor: historicalColors[index % historicalColors.length],
        backgroundColor: 'transparent',
        borderWidth: 2,
        fill: false,
        tension: 0.4,
        pointRadius: 2,
        pointHoverRadius: 4
    }));

    historicalChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: historicalDatasets
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
                            size: 11
                        },
                        boxWidth: 12
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            if (context.parsed.y === null) return null;
                            return context.dataset.label + ': ' + context.parsed.y.toFixed(1) + '°F';
                        }
                    },
                    filter: function(tooltipItem) {
                        return tooltipItem.parsed.y !== null;
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    ticks: {
                        callback: function(value) {
                            return value.toFixed(1) + '°F';
                        },
                        font: {
                            size: 11
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
                            size: 10
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
    document.getElementById('top-cards-container').style.display = 'none';
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

const REFRESH_INTERVAL_MS = 60 * 60 * 1000; // 1 hour in milliseconds

document.addEventListener('DOMContentLoaded', function() {
    loadForecast();
    setInterval(loadForecast, REFRESH_INTERVAL_MS);
});
