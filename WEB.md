# Web Module Technical Documentation

This document explains how the Flask web application works, focusing on the Python backend components.

## Architecture Overview

The web module follows this request/response flow:

```
Browser                    Flask Server                    External Services
   |                            |                                |
   |-- GET / ------------------>|                                |
   |<-- HTML (index.html) ------|                                |
   |                            |                                |
   |-- GET /api/forecast ------>|                                |
   |                            |-- GET weather.gov API -------->|
   |                            |<-- Current temperature --------|
   |                            |                                |
   |                            |-- Load XGBoost model           |
   |                            |-- Generate 24h predictions     |
   |                            |-- Compute SHAP values          |
   |                            |-- Generate LLM summary         |
   |                            |                                |
   |<-- JSON response ----------|                                |
   |                            |                                |
   |   (JavaScript updates UI)  |                                |
```

There are two refresh mechanisms:
1. **Frontend refresh** (every 10 minutes): JavaScript calls `/api/forecast` and updates the UI
2. **Backend scheduler** (configurable, default 60 minutes): APScheduler calls the NWS API and saves temperatures to build lag history

---

## Entry Point: `run_dashboard.py`

This script starts the Flask server:

```python
from weather_platform.web import create_app

app = create_app(
    project_path=str(project_path),
    scheduler_interval=args.interval,      # Default: 60 minutes
    enable_scheduler=not args.no_scheduler
)

app.run(host=args.host, port=args.port, debug=True, use_reloader=False)
```

Command line options:
- `--port`: Server port (default 5000)
- `--interval`: Backend scheduler interval in minutes
- `--no-scheduler`: Disable the background scheduler entirely

---

## Application Factory: `app.py`

Flask uses the "application factory" pattern. The `create_app()` function builds and configures the app:

```python
def create_app(project_path, scheduler_interval, enable_scheduler):
    app = Flask(__name__,
                template_folder=Path(__file__).parent / 'templates',
                static_folder=Path(__file__).parent / 'static')
```

### Key concepts:

**Flask app configuration:**
```python
app.config['KEDRO_PROJECT_PATH'] = str(project_path)  # Path to Kedro project
app.config['SCHEDULER_INTERVAL'] = scheduler_interval  # Minutes between API calls
app.config['SECRET_KEY'] = secrets.token_hex(32)       # For session security
```

**Blueprint registration:**
```python
app.register_blueprint(web_bp)
```
A Blueprint is a way to organize routes. All routes in `routes.py` are registered under `web_bp`.

**Scheduler initialization:**
```python
if enable_scheduler:
    scheduler = init_scheduler(app)
    app.scheduler = scheduler
```
The scheduler is attached to the app object so it persists for the lifetime of the server.

**Teardown handler:**
```python
@app.teardown_appcontext
def shutdown_scheduler(exception=None):
    if hasattr(app, 'scheduler') and app.scheduler.running:
        app.scheduler.shutdown()
```
This ensures the scheduler stops cleanly when the app shuts down.

---

## Routes: `routes.py`

Routes define URL endpoints. Each route is a function decorated with `@web_bp.route()`.

### Route: `GET /`

```python
@web_bp.route('/')
def index():
    predictor = get_predictor()
    initial_metrics = predictor.get_metrics()
    return render_template('index.html', metrics=initial_metrics)
```

- Returns the main HTML page
- `render_template()` loads `templates/index.html` and injects the `metrics` variable
- The HTML contains placeholders that JavaScript will populate later

### Route: `GET /api/forecast`

This is the main API endpoint. It returns JSON data that JavaScript uses to update the page.

**Step 1: Load configuration from Kedro**
```python
ensure_bootstrap(current_app.config['KEDRO_PROJECT_PATH'])
with KedroSession.create(project_path=...) as session:
    context = session.load_context()
    dashboard_config = context.params.get('dashboard', {})
    lat = dashboard_config['location']['latitude']
    lon = dashboard_config['location']['longitude']
```
This reads `conf/base/parameters.yml` to get the location coordinates.

**Step 2: Fetch current weather**
```python
weather_data = get_current_weather(lat, lon)
current_temp = weather_data['temperature']
start_time = weather_data['start_time']
```

**Step 3: Save temperature and get lag values**
```python
predictor.save_temperature(start_time, current_temp)
lag_temps = predictor.get_lag_temperatures(start_time)
```
Temperatures are stored in a parquet file. Lag temperatures are the previous N hours needed for prediction features.

**Step 4: Generate predictions**
```python
predictions = predictor.predict_24h(start_time=start_time, current_temp=current_temp)
historical = predictor.get_historical_temperatures(start_time=start_time, num_years=5)
shap_data = predictor.get_shap_contributions(dt=start_time, temp=current_temp, lag_temps=lag_temps)
```

**Step 5: Generate LLM summary**
```python
weather_bot.load_model(str(Path(project_path) / model_path))
bot_summary = weather_bot.generate_forecast_summary(predictions, current_temp, location_name)
```

**Step 6: Return JSON**
```python
return jsonify({
    'success': True,
    'current_weather': {...},
    'predictions': [...],
    'historical': [...],
    'shap': {...},
    'weather_bot': {'summary': bot_summary, 'model_name': model_name},
    'technical': {...}
})
```
`jsonify()` converts a Python dict to a JSON HTTP response.

### Helper functions

**`get_predictor()`**: Singleton pattern for the predictor
```python
def get_predictor():
    if not hasattr(current_app, 'predictor'):
        current_app.predictor = WeatherPredictor(current_app.config['KEDRO_PROJECT_PATH'])
    return current_app.predictor
```
The predictor is expensive to create (loads model, connects to Kedro), so we create it once and store it on the Flask app object.

**`current_app`**: Flask's context-local proxy
Within a request, `current_app` refers to the Flask application handling the request. This allows access to `app.config` without passing the app object explicitly.

---

## Weather API Client: `weather_api.py`

Fetches live weather data from the National Weather Service API.

```python
def get_current_weather(lat: float, lon: float) -> Dict[str, Any]:
    # Step 1: Get forecast URL for coordinates
    points_url = f"https://api.weather.gov/points/{lat},{lon}"
    points_response = requests.get(points_url, headers=headers, timeout=10)
    forecast_url = points_response.json()["properties"]["forecast"]

    # Step 2: Get forecast data
    forecast_response = requests.get(forecast_url, headers=headers, timeout=10)
    first_period = forecast_response.json()["properties"]["periods"][0]

    return {
        "start_time": datetime.fromisoformat(first_period["startTime"]),
        "temperature": float(first_period["temperature"]),
        ...
    }
```

The NWS API requires two calls:
1. `/points/{lat},{lon}` returns metadata including the forecast URL
2. The forecast URL returns actual weather data

**Headers**: NWS requires a User-Agent header identifying your application.

---

## Predictor: `predictor.py`

The `WeatherPredictor` class wraps all ML inference logic.

### Initialization

```python
class WeatherPredictor:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self._model = None              # Cached XGBoost model
        self._model_timestamp = None    # File modification time for cache invalidation
        self.inference_dir = self.project_path / 'data' / '04_inference'
        self.temperatures_file = self.inference_dir / 'temperatures.parquet'
        bootstrap_project(self.project_path)  # Initialize Kedro
```

### Model loading with caching

```python
def load_model(self):
    current_mtime = self._get_file_mtime("trained_model")
    if self._model is None or current_mtime != self._model_timestamp:
        with KedroSession.create(...) as session:
            context = session.load_context()
            self._model = context.catalog.load("trained_model")
            self._model_timestamp = current_mtime
    return self._model
```

The model is cached in memory. It only reloads if:
- First request (model is None)
- Model file has been modified (timestamp changed, e.g., after `kedro run`)

### Temperature persistence

Temperatures are stored in a parquet file to build up lag feature history over time.

```python
def save_temperature(self, dt: datetime, temperature: float):
    df = self._load_temperatures_df()
    # Check if this hour already exists
    exists = ((df['year'] == dt.year) & (df['month'] == dt.month) &
              (df['day'] == dt.day) & (df['hour'] == dt.hour)).any()
    if not exists:
        # Append new row
        new_row = pd.DataFrame([{...}])
        df = pd.concat([df, new_row], ignore_index=True)
        self._save_temperatures_df(df)
```

This prevents duplicate entries for the same hour.

### Feature building

```python
def _build_features(self, dt: datetime, temp: float, lag_temps: List[Optional[float]]) -> np.ndarray:
    params = self._load_params()
    feature_cols = params['data_science']['feature_columns']

    features_dict = {
        'ft_month': dt.month,
        'ft_day': dt.day,
        'ft_hour': dt.hour,
        'ft_days_since_2000': self._compute_days_since_reference(dt),
        'ft_temp': temp
    }
    for i, lag_temp in enumerate(lag_temps, 1):
        features_dict[f'ft_temp_lag_{i}h'] = lag_temp

    # Build array in same order as training
    features_list = [features_dict.get(col, np.nan) for col in feature_cols]
    return np.array([features_list])
```

Features must be in the exact same order as during training. The `feature_columns` list from `parameters.yml` defines this order.

### 24-hour prediction

```python
def predict_24h(self, start_time: datetime, current_temp: float) -> List[Dict]:
    lag_temps = self.get_lag_temperatures(start_time)
    predictions = []
    current_temp_val = current_temp

    for i in range(24):
        future_time = start_time + timedelta(hours=i)
        features = self._build_features(future_time, current_temp_val, lag_temps)
        predicted_temp = float(model.predict(features)[0])

        predictions.append({
            "time": future_time.isoformat(),
            "predicted_temperature": predicted_temp
        })

        # Shift lag window: current becomes lag_1, lag_1 becomes lag_2, etc.
        lag_temps = [current_temp_val] + lag_temps[:-1]
        current_temp_val = predicted_temp

    return predictions
```

This uses the model iteratively: each prediction becomes input for the next hour.

### SHAP computation

```python
def get_shap_contributions(self, dt, temp, lag_temps):
    import shap
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(features)

    # Convert to percentages
    abs_shap = np.abs(shap_values[0])
    total = abs_shap.sum()
    percentages = (abs_shap / total) * 100
```

SHAP values show how much each feature contributed to the prediction. We convert to percentages for the UI visualization.

---

## Background Scheduler: `scheduler.py`

Uses APScheduler to run periodic tasks in the background.

```python
def init_scheduler(app) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    interval_minutes = app.config.get('SCHEDULER_INTERVAL', 60)

    scheduler.add_job(
        func=update_forecast,
        args=[app],
        trigger=IntervalTrigger(minutes=interval_minutes),
        id='forecast_update_job',
        misfire_grace_time=60,  # If job is late by <60s, still run it
        coalesce=True,          # If multiple runs were missed, only run once
        replace_existing=True   # Replace job if it already exists
    )

    scheduler.start()
    return scheduler
```

**Why a background scheduler?**

The scheduler runs independently of user requests. It:
1. Fetches current weather from the API
2. Saves the temperature to the parquet file

This builds up the historical temperature data needed for lag features. Even if no one visits the website, temperatures are still being collected.

**`update_forecast()` function:**

```python
def update_forecast(app):
    with app.app_context():  # Required to access Flask context
        weather_data = get_current_weather(lat, lon)
        predictor = WeatherPredictor(project_path)
        predictor.save_temperature(start_time_weather, current_temp)
```

`app.app_context()` is required because we're running outside a request context but still need access to Flask's `current_app` and configuration.

---

## Weather-Bot LLM: `weather_bot.py`

Generates natural language forecast summaries using TinyLlama.

### Module-level caching

```python
_model = None
_tokenizer = None

def load_model(model_path: str):
    global _model, _tokenizer
    if _model is not None:
        return  # Already loaded

    _tokenizer = AutoTokenizer.from_pretrained(model_path)
    _model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.float16)
```

The model is loaded once and cached at module level. This persists across requests because Python modules are only imported once.

### Prompt construction

```python
def generate_forecast_summary(predictions, current_temp, location):
    # Group predictions by time period
    temps_by_period = {'morning': [], 'afternoon': [], 'evening': [], 'night': []}
    for pred in predictions:
        hour = datetime.fromisoformat(pred['time']).hour
        if 5 <= hour < 12:
            temps_by_period['morning'].append(temp)
        # ... etc

    # Build summary string
    summary_parts = []
    for period, temps in temps_by_period.items():
        if temps:
            summary_parts.append(f"{period}: high {max(temps):.0f}°F, low {min(temps):.0f}°F")

    prompt = f"""<|system|>
You are a weather assistant. Write one short natural sentence...
<|user|>
Current: {current_temp:.0f}°F. Forecast: {forecast_summary}
<|assistant|>
"""
```

The prompt uses TinyLlama's chat template format with special tokens.

### Response parsing

```python
full_response = _tokenizer.decode(outputs[0], skip_special_tokens=True)

# Extract just the assistant's response
if "<|assistant|>" in full_response:
    response = full_response.split("<|assistant|>")[-1].strip()

# Clean up any trailing tokens
response = response.split("</s>")[0].strip()
response = response.split("<|")[0].strip()
response = response.split("\n")[0].strip()
```

LLMs often include extra tokens or continue generating. We extract only the first sentence after the assistant marker.

---

## Frontend Refresh (JavaScript)

The frontend JavaScript in `dashboard.js` handles UI updates:

```javascript
const REFRESH_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes

async function loadForecast() {
    const response = await fetch('/api/forecast');
    const data = await response.json();

    if (data.success) {
        displayCurrentWeather(data.current_weather, data.location);
        displayShapContributions(data.shap);
        displayWeatherBot(data.weather_bot);
        displayCharts(data.predictions, ...);
        displayTechnicalDetails(data.technical, ...);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    loadForecast();                              // Initial load
    setInterval(loadForecast, REFRESH_INTERVAL_MS);  // Periodic refresh
});
```

Key points:
- `fetch('/api/forecast')` makes an HTTP GET request to the Flask backend
- Response is JSON, parsed with `.json()`
- `setInterval()` calls `loadForecast()` every 10 minutes
- Each `display*()` function updates specific DOM elements

---

## Data Flow Summary

1. **User visits `/`** → Flask returns `index.html` with empty placeholders

2. **JavaScript calls `/api/forecast`** → Flask:
   - Reads location from `parameters.yml` via Kedro
   - Calls NWS API for current weather
   - Saves temperature to parquet file
   - Loads XGBoost model from `data/03_outputs/`
   - Generates 24 predictions iteratively
   - Computes SHAP values
   - Generates LLM summary
   - Returns JSON

3. **JavaScript updates DOM** with received data

4. **Every 10 minutes** → JavaScript repeats step 2-3

5. **Background scheduler (hourly)** → Independently fetches and saves temperatures to build lag history

---

## File Locations

| File | Purpose |
|------|---------|
| `data/03_outputs/weather_model.pkl` | Trained XGBoost model |
| `data/03_outputs/model_metrics.json` | Model evaluation metrics |
| `data/04_inference/temperatures.parquet` | Stored API temperatures for lag features |
| `data/05_ai/tinyllama/` | LLM model weights |
| `conf/base/parameters.yml` | All configuration (features, location, etc.) |
