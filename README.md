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