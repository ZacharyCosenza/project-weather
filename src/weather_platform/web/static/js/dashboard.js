function startMetricsPolling(intervalSeconds = 30) {
    updateMetrics();
    setInterval(updateMetrics, intervalSeconds * 1000);
}

async function updateMetrics() {
    try {
        const response = await fetch('/api/metrics');
        const data = await response.json();

        if (data.mse !== null) {
            document.getElementById('metric-mse').textContent = data.mse.toFixed(4);
        }
        if (data.rmse !== null) {
            document.getElementById('metric-rmse').textContent = data.rmse.toFixed(4);
        }
        if (data.mae !== null) {
            document.getElementById('metric-mae').textContent = data.mae.toFixed(4);
        }

        document.getElementById('last-updated').textContent = data.last_updated || 'N/A';

        updateStatusIndicator(data.model_exists);
    } catch (error) {
        console.error('Failed to fetch metrics:', error);
    }
}

function updateStatusIndicator(modelExists) {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');

    if (modelExists) {
        statusDot.classList.remove('status-error');
        statusDot.classList.add('status-healthy');
        statusText.textContent = 'Model Ready';
    } else {
        statusDot.classList.remove('status-healthy');
        statusDot.classList.add('status-error');
        statusText.textContent = 'Model Not Available - Run pipeline first';
    }
}

async function submitPrediction(event) {
    event.preventDefault();

    const formData = new FormData(event.target);
    const data = {
        month: parseInt(formData.get('month')),
        day: parseInt(formData.get('day')),
        hour: parseInt(formData.get('hour')),
        temp: parseFloat(formData.get('temp'))
    };

    hideError();

    try {
        const response = await fetch('/api/predict', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            displayPrediction(result);
        } else {
            showError(result.error || 'Prediction failed');
        }
    } catch (error) {
        showError('Failed to get prediction: ' + error.message);
    }
}

function displayPrediction(result) {
    document.getElementById('pred-value').textContent = result.prediction.toFixed(2);

    const inputText = `Month: ${result.input_features.ft_month}, Day: ${result.input_features.ft_day}, Hour: ${result.input_features.ft_hour}, Temp: ${result.input_features.ft_temp}°F`;
    document.getElementById('pred-input').textContent = inputText;
    document.getElementById('pred-timestamp').textContent = result.model_timestamp || 'Unknown';

    document.getElementById('prediction-result').style.display = 'block';

    document.getElementById('prediction-result').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function showError(message) {
    const errorDiv = document.getElementById('error-message');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    document.getElementById('prediction-result').style.display = 'none';
}

function hideError() {
    document.getElementById('error-message').style.display = 'none';
}

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('prediction-form');
    if (form) {
        form.addEventListener('submit', submitPrediction);
    }

    startMetricsPolling(30);
});
