import os
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
        self._params = None
        self.inference_dir = self.project_path / 'data' / '04_inference'
        self.inference_dir.mkdir(parents=True, exist_ok=True)
        self.temperatures_file = self.inference_dir / 'temperatures.parquet'
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

    def _load_params(self) -> Dict[str, Any]:
        if self._params is None:
            with KedroSession.create(project_path=self.project_path) as session:
                context = session.load_context()
                self._params = context.params
        return self._params

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
                'mse': None, 'rmse': None, 'mae': None,
                'last_updated': 'N/A', 'model_exists': False, 'error': str(e)
            }

    def _load_temperatures_df(self) -> pd.DataFrame:
        if self.temperatures_file.exists():
            return pd.read_parquet(self.temperatures_file)
        return pd.DataFrame(columns=['year', 'month', 'day', 'hour', 'temperature', 'timestamp'])

    def _save_temperatures_df(self, df: pd.DataFrame):
        df.to_parquet(self.temperatures_file, index=False)

    def save_temperature(self, dt: datetime, temperature: float):
        df = self._load_temperatures_df()
        dt_naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
        exists = (
            (df['year'] == dt_naive.year) &
            (df['month'] == dt_naive.month) &
            (df['day'] == dt_naive.day) &
            (df['hour'] == dt_naive.hour)
        ).any()

        if not exists:
            new_row = pd.DataFrame([{
                'year': dt_naive.year,
                'month': dt_naive.month,
                'day': dt_naive.day,
                'hour': dt_naive.hour,
                'temperature': temperature,
                'timestamp': dt_naive.isoformat()
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            self._save_temperatures_df(df)

    def load_temperature(self, dt: datetime) -> Optional[float]:
        df = self._load_temperatures_df()
        dt_naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
        match = df[
            (df['year'] == dt_naive.year) &
            (df['month'] == dt_naive.month) &
            (df['day'] == dt_naive.day) &
            (df['hour'] == dt_naive.hour)
        ]
        if not match.empty:
            return float(match.iloc[0]['temperature'])
        return None

    def get_lag_temperatures(self, dt: datetime) -> List[Optional[float]]:
        params = self._load_params()
        num_lags = params['data_engineering']['num_lags']
        lags = []
        for i in range(1, num_lags + 1):
            lag_time = dt - timedelta(hours=i)
            temp = self.load_temperature(lag_time)
            lags.append(temp)
        return lags

    def _compute_days_since_reference(self, dt: datetime) -> float:
        params = self._load_params()
        reference_date = pd.Timestamp(params['data_engineering']['reference_date'])
        dt_naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
        return (pd.Timestamp(dt_naive) - reference_date).total_seconds() / (24 * 3600)

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

        features_list = [features_dict.get(col, np.nan) for col in feature_cols]
        return np.array([features_list]), features_dict

    def predict(self, dt: datetime, temp: float, lag_temps: List[Optional[float]]) -> Dict[str, Any]:
        model = self.load_model()
        features, features_dict = self._build_features(dt, temp, lag_temps)
        prediction = model.predict(features)[0]

        return {
            'prediction': float(prediction),
            'input_features': features_dict,
            'model_timestamp': datetime.fromtimestamp(self._model_timestamp).strftime('%Y-%m-%d %H:%M:%S') if self._model_timestamp else 'Unknown'
        }

    def predict_24h(self, start_time: datetime, current_temp: float) -> List[Dict[str, Any]]:
        model = self.load_model()
        lag_temps = self.get_lag_temperatures(start_time)
        predictions = []
        current_temp_val = current_temp

        for i in range(24):
            future_time = start_time + timedelta(hours=i)
            features, features_dict = self._build_features(future_time, current_temp_val, lag_temps)
            predicted_temp = float(model.predict(features)[0])

            predictions.append({
                "time": future_time.isoformat(),
                "hour": future_time.hour,
                "predicted_temperature": predicted_temp
            })

            lag_temps = [current_temp_val] + lag_temps[:-1]
            current_temp_val = predicted_temp

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
                    matching = raw_data[
                        (raw_data['year'] == year) &
                        (raw_data['month'] == future_time.month) &
                        (raw_data['day'] == future_time.day) &
                        (raw_data['hour'] == future_time.hour)
                    ]
                    if not matching.empty:
                        year_temps.append(float(matching['tmpf'].iloc[0]))
                    else:
                        year_temps.append(None)
                historical_data.append({'year': int(year), 'temperatures': year_temps})
            return historical_data
        except Exception:
            return []

    def get_shap_contributions(self, dt: datetime, temp: float, lag_temps: List[Optional[float]]) -> Dict[str, Any]:
        import shap
        model = self.load_model()
        params = self._load_params()
        feature_cols = params['data_science']['feature_columns']

        features, _ = self._build_features(dt, temp, lag_temps)

        feature_display_names = {
            'ft_month': 'Month', 'ft_day': 'Day', 'ft_hour': 'Hour',
            'ft_days_since_2000': 'Days Since 2000', 'ft_temp': 'Current Temp'
        }
        for i in range(1, 10):
            feature_display_names[f'ft_temp_lag_{i}h'] = f'Temp Lag {i}h'

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(features)

        abs_shap = np.abs(shap_values[0])
        total = abs_shap.sum()
        percentages = (abs_shap / total) * 100 if total > 0 else np.zeros_like(abs_shap)

        contributions = []
        for i, col in enumerate(feature_cols):
            contributions.append({
                'feature': feature_display_names.get(col, col),
                'percentage': float(percentages[i]),
                'shap_value': float(shap_values[0][i])
            })
        contributions.sort(key=lambda x: x['percentage'], reverse=True)

        return {'contributions': contributions, 'base_value': float(explainer.expected_value)}
