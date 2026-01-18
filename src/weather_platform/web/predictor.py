import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import numpy as np
from kedro.framework.session import KedroSession
from kedro.framework.startup import bootstrap_project


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
        """
        Generate 24-hour temperature forecast predictions.

        Args:
            start_time: Starting datetime for forecast
            current_temp: Current temperature in Fahrenheit

        Returns:
            List of 24 hourly predictions, each containing:
                - time: ISO format timestamp
                - hour: Hour of day (0-23)
                - predicted_temperature: Predicted temperature in F
        """
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
