import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import numpy as np
from kedro.framework.session import KedroSession
from kedro.framework.startup import bootstrap_project
import pandas as pd

class WeatherPredictor:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self._model = None
        self._model_timestamp = None
        self._metrics = None
        self._metrics_timestamp = None

        bootstrap_project(self.project_path)

    def _get_file_mtime(self, filename: str) -> Optional[float]:
        try:
            with KedroSession.create(project_path=self.project_path) as session:
                context = session.load_context()
                dataset = context.catalog._datasets.get(filename)
                if dataset and hasattr(dataset, '_filepath'):
                    filepath = dataset._filepath
                    if os.path.exists(filepath):
                        return os.path.getmtime(filepath)
        except Exception:
            pass
        return None

    def load_model(self):
        try:
            current_mtime = self._get_file_mtime("trained_model")

            if self._model is None or current_mtime != self._model_timestamp:
                with KedroSession.create(project_path=self.project_path) as session:
                    context = session.load_context()
                    self._model = context.catalog.load("trained_model")
                    self._model_timestamp = current_mtime

            return self._model
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {str(e)}")

    def get_metrics(self) -> Dict[str, Any]:
        try:
            current_mtime = self._get_file_mtime("model_metrics")

            if self._metrics is None or current_mtime != self._metrics_timestamp:
                with KedroSession.create(project_path=self.project_path) as session:
                    context = session.load_context()
                    self._metrics = context.catalog.load("model_metrics")
                    self._metrics_timestamp = current_mtime

            metrics = self._metrics.copy() if self._metrics else {}
            metrics['last_updated'] = datetime.fromtimestamp(self._metrics_timestamp).strftime('%Y-%m-%d %H:%M:%S') if self._metrics_timestamp else 'Unknown'
            metrics['model_exists'] = self._model is not None or os.path.exists(self.project_path / 'data' / '03_outputs' / 'weather_model.pkl')

            return metrics
        except Exception as e:
            return {
                'mse': None,
                'rmse': None,
                'mae': None,
                'last_updated': 'N/A',
                'model_exists': False,
                'error': str(e)
            }

    def predict(self, month: int, day: int, hour: int, temp: float) -> Dict[str, Any]:
        if not (1 <= month <= 12):
            raise ValueError(f"Month must be between 1 and 12, got {month}")
        if not (1 <= day <= 31):
            raise ValueError(f"Day must be between 1 and 31, got {day}")
        if not (0 <= hour <= 23):
            raise ValueError(f"Hour must be between 0 and 23, got {hour}")

        model = self.load_model()

        features = np.array([[month, day, hour, temp]])
        prediction = model.predict(features)[0]

        return {
            'prediction': float(prediction),
            'input_features': {
                'ft_month': month,
                'ft_day': day,
                'ft_hour': hour,
                'ft_temp': temp
            },
            'model_timestamp': datetime.fromtimestamp(self._model_timestamp).strftime('%Y-%m-%d %H:%M:%S') if self._model_timestamp else 'Unknown'
        }

    def predict_24h(self, start_time: datetime, current_temp: float) -> List[Dict[str, Any]]:
        model = self.load_model()
        predictions = []

        for i in range(24):
            future_time = start_time + timedelta(hours=i)
            month = future_time.month
            day = future_time.day
            hour = future_time.hour

            features = np.array([[month, day, hour, current_temp]])
            predicted_temp = model.predict(features)[0]

            predictions.append({
                "time": future_time.isoformat(),
                "hour": hour,
                "predicted_temperature": float(predicted_temp)
            })

        return predictions

    def get_historical_temperatures(self, start_time: datetime, num_years: int = 5) -> List[Dict[str, Any]]:
        try:
            with KedroSession.create(project_path=self.project_path) as session:
                context = session.load_context()
                raw_data = context.catalog.load("raw_weather_data")

            raw_data['valid'] = pd.to_datetime(raw_data['valid'], errors='coerce')
            raw_data['tmpf'] = pd.to_numeric(raw_data['tmpf'], errors='coerce')
            raw_data = raw_data.dropna(subset=['valid', 'tmpf'])

            raw_data['month'] = raw_data['valid'].dt.month
            raw_data['day'] = raw_data['valid'].dt.day
            raw_data['hour'] = raw_data['valid'].dt.hour
            raw_data['year'] = raw_data['valid'].dt.year

            current_year = start_time.year
            available_years = sorted(raw_data['year'].unique(), reverse=True)
            historical_years = [y for y in available_years if y < current_year][:num_years]

            historical_data = []

            for year in historical_years:
                year_temps = []
                for i in range(24):
                    future_time = start_time + timedelta(hours=i)
                    month = future_time.month
                    day = future_time.day
                    hour = future_time.hour

                    matching = raw_data[
                        (raw_data['year'] == year) &
                        (raw_data['month'] == month) &
                        (raw_data['day'] == day) &
                        (raw_data['hour'] == hour)
                    ]

                    if not matching.empty:
                        year_temps.append(float(matching['tmpf'].iloc[0]))
                    else:
                        year_temps.append(None)

                historical_data.append({
                    'year': int(year),
                    'temperatures': year_temps
                })

            return historical_data

        except Exception:
            return []

    def get_shap_contributions(self, month: int, day: int, hour: int, temp: float) -> Dict[str, Any]:
        """
        Calculate SHAP values for a single prediction to explain feature contributions.

        Returns normalized percentages that sum to 100%.
        """
        import shap

        model = self.load_model()
        features = np.array([[month, day, hour, temp]])
        feature_names = ['Month', 'Day', 'Hour', 'Current Temp']

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(features)

        abs_shap = np.abs(shap_values[0])
        total = abs_shap.sum()

        if total > 0:
            percentages = (abs_shap / total) * 100
        else:
            percentages = np.zeros_like(abs_shap)

        contributions = []
        for i, name in enumerate(feature_names):
            contributions.append({
                'feature': name,
                'percentage': float(percentages[i]),
                'shap_value': float(shap_values[0][i])
            })

        contributions.sort(key=lambda x: x['percentage'], reverse=True)

        return {
            'contributions': contributions,
            'base_value': float(explainer.expected_value)
        }
