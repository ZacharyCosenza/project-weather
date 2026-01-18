# Weather Temperature Prediction Platform

Machine learning pipeline for predicting hourly temperature using XGBoost and historical weather data. Built with Kedro for reproducible data science workflows.

## Features

- **Temperature Prediction**: Predict next-hour temperature based on current conditions
- **Web Dashboard**: Interactive Flask-based interface for live predictions
- **Automated Pipeline**: Scheduled model retraining and metric updates
- **Model Performance**: MSE: 1.56, RMSE: 1.25, MAE: 0.89

## Quick Start

### Installation

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### Run the Pipeline

```bash
kedro run
```

This executes:
1. Data engineering: Feature extraction (month, day, hour, temperature)
2. Data science: Model training, validation, and evaluation

### Launch Web Dashboard

```bash
python run_dashboard.py
```

Access at: http://localhost:5000

**Options:**
- `--port 8080` - Custom port
- `--interval 30` - Pipeline run interval (minutes)
- `--no-scheduler` - Disable auto-scheduling

## Web Dashboard

The dashboard provides:
- **Prediction Form**: Input weather conditions to get next-hour temperature forecast
- **Live Metrics**: Auto-refreshing model performance statistics
- **Status Indicators**: Model availability and last update timestamp

### Public Access with ngrok

Share the dashboard publicly:

```bash
./start_public_dashboard.sh
```

Stop with:
```bash
./stop_public_dashboard.sh
```

## Model Details

**Algorithm**: XGBoost Regressor

**Input Features**:
- `ft_month`: Month (1-12)
- `ft_day`: Day of month (1-31)
- `ft_hour`: Hour of day (0-23)
- `ft_temp`: Current temperature (°F)

**Target**: `tgt_tmpf` - Temperature for next hour (°F)

**Hyperparameter Optimization**: Optional Optuna integration for automated tuning

## Project Structure

```
project-weather/
├── src/weather_platform/
│   ├── pipelines/
│   │   ├── data_engineering/    # Feature engineering
│   │   └── data_science/         # Model training & evaluation
│   └── web/                      # Flask dashboard
│       ├── app.py                # Application factory
│       ├── routes.py             # API endpoints
│       ├── predictor.py          # Prediction logic
│       ├── scheduler.py          # Pipeline scheduling
│       ├── templates/            # HTML templates
│       └── static/               # CSS & JavaScript
├── conf/
│   └── base/
│       ├── catalog.yml           # Data sources
│       └── parameters.yml        # Model & pipeline config
├── data/
│   ├── 01_raw/                   # Raw weather data
│   ├── 02_features/              # Processed features
│   └── 03_outputs/               # Models & metrics
├── run_dashboard.py              # Dashboard entry point
└── pyproject.toml                # Dependencies
```

## Configuration

### Pipeline Parameters

Edit `conf/base/parameters.yml`:

```yaml
data_science:
  feature_columns:
    - ft_month
    - ft_day
    - ft_hour
    - ft_temp
  target_column: tgt_tmpf
  val_size: 0.1
  test_size: 0.1
  random_state: 42
  optuna:
    flag_use_optuna: false
    n_trials: 50
```

### Data Catalog

Edit `conf/base/catalog.yml` to modify data sources and outputs.

## API Endpoints

- `GET /` - Dashboard homepage
- `POST /api/predict` - Make temperature prediction
- `GET /api/metrics` - Get model performance metrics
- `GET /health` - Health check

**Example Prediction Request**:
```bash
curl -X POST http://localhost:5000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"month": 6, "day": 15, "hour": 14, "temp": 75.0}'
```

**Response**:
```json
{
  "success": true,
  "prediction": 76.45,
  "input_features": {
    "ft_month": 6,
    "ft_day": 15,
    "ft_hour": 14,
    "ft_temp": 75.0
  }
}
```

## Requirements

- Python >=3.8
- Key dependencies: kedro, pandas, xgboost, scikit-learn, flask, apscheduler

See `pyproject.toml` for full dependency list.

## Security

**Environment Variables**: Copy `.env.example` to `.env` and set your configuration:

```bash
cp .env.example .env
# Edit .env with your values
```

**Important**: Never commit `.env`, `keys.md`, or any files containing secrets to version control.

## License

MIT
