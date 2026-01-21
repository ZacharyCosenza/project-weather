from pathlib import Path
from flask import Blueprint, render_template, jsonify, current_app
from kedro.framework.session import KedroSession
from kedro.framework.startup import bootstrap_project
from .predictor import WeatherPredictor
from .weather_api import get_current_weather
from . import weather_bot

web_bp = Blueprint('web', __name__)
_bootstrapped = False


def ensure_bootstrap(project_path):
    global _bootstrapped
    if not _bootstrapped:
        bootstrap_project(project_path)
        _bootstrapped = True


def get_predictor():
    if not hasattr(current_app, 'predictor'):
        current_app.predictor = WeatherPredictor(current_app.config['KEDRO_PROJECT_PATH'])
    return current_app.predictor


@web_bp.route('/')
def index():
    predictor = get_predictor()
    try:
        initial_metrics = predictor.get_metrics()
    except Exception:
        initial_metrics = {'model_exists': False}
    return render_template('index.html', metrics=initial_metrics)


@web_bp.route('/api/forecast')
def forecast():
    try:
        ensure_bootstrap(current_app.config['KEDRO_PROJECT_PATH'])
        with KedroSession.create(project_path=current_app.config['KEDRO_PROJECT_PATH']) as session:
            context = session.load_context()
            dashboard_config = context.params.get('dashboard', {})
            location_config = dashboard_config.get('location', {})
            lat = location_config.get('latitude')
            lon = location_config.get('longitude')
            location_name = location_config.get('name', 'Unknown')

            if lat is None or lon is None:
                return jsonify({
                    'success': False,
                    'error': 'Location coordinates not configured in parameters.yml'
                }), 500

        weather_data = get_current_weather(lat, lon)
        predictor = get_predictor()
        start_time = weather_data['start_time']
        current_temp = weather_data['temperature']

        predictor.save_temperature(start_time, current_temp)
        lag_temps = predictor.get_lag_temperatures(start_time)
        predictions = predictor.predict_24h(start_time=start_time, current_temp=current_temp)
        historical = predictor.get_historical_temperatures(start_time=start_time, num_years=5)
        shap_data = predictor.get_shap_contributions(dt=start_time, temp=current_temp, lag_temps=lag_temps)

        project_path = current_app.config['KEDRO_PROJECT_PATH']
        ai_config = context.params.get('ai', {})
        model_path = ai_config.get('model_path', 'data/05_ai/tinyllama')
        model_name = ai_config.get('model_name', 'TinyLlama')
        weather_bot.load_model(str(Path(project_path) / model_path))
        bot_summary = weather_bot.generate_forecast_summary(predictions, current_temp, location_name)

        data_science_config = context.params.get('data_science', {})
        feature_columns = data_science_config.get('feature_columns', [])
        data_engineering_config = context.params.get('data_engineering', {})
        num_lags = data_engineering_config.get('num_lags', 3)

        return jsonify({
            'success': True,
            'current_weather': {
                'temperature': current_temp,
                'time': start_time.isoformat(),
                'forecast': weather_data['short_forecast'],
                'forecast_name': weather_data['forecast_name']
            },
            'predictions': predictions,
            'historical': historical,
            'shap': shap_data,
            'location': location_name,
            'lag_temperatures': lag_temps,
            'weather_bot': {
                'summary': bot_summary,
                'model_name': model_name
            },
            'technical': {
                'feature_columns': feature_columns,
                'num_lags': num_lags,
                'llm_model': model_name
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@web_bp.route('/api/metrics')
def metrics():
    try:
        predictor = get_predictor()
        metrics_data = predictor.get_metrics()
        return jsonify(metrics_data)
    except Exception as e:
        return jsonify({
            'mse': None, 'rmse': None, 'mae': None,
            'last_updated': 'N/A', 'model_exists': False, 'error': str(e)
        }), 500


@web_bp.route('/health')
def health():
    try:
        predictor = get_predictor()
        metrics_data = predictor.get_metrics()
        scheduler_running = hasattr(current_app, 'scheduler') and current_app.scheduler.running

        return jsonify({
            'status': 'healthy',
            'model_exists': metrics_data.get('model_exists', False),
            'scheduler_running': scheduler_running,
            'last_metrics_update': metrics_data.get('last_updated', 'Unknown')
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500
