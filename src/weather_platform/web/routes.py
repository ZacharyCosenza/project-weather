from flask import Blueprint, render_template, request, jsonify, current_app
from .predictor import WeatherPredictor

web_bp = Blueprint('web', __name__)


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


@web_bp.route('/api/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400

        required_fields = ['month', 'day', 'hour', 'temp']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

        month = int(data['month'])
        day = int(data['day'])
        hour = int(data['hour'])
        temp = float(data['temp'])

        predictor = get_predictor()
        result = predictor.predict(month, day, hour, temp)

        return jsonify({
            'success': True,
            'prediction': result['prediction'],
            'input_features': result['input_features'],
            'model_timestamp': result['model_timestamp']
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Prediction failed: {str(e)}'}), 500


@web_bp.route('/api/metrics')
def metrics():
    try:
        predictor = get_predictor()
        metrics_data = predictor.get_metrics()
        return jsonify(metrics_data)
    except Exception as e:
        return jsonify({
            'mse': None,
            'rmse': None,
            'mae': None,
            'last_updated': 'N/A',
            'model_exists': False,
            'error': str(e)
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
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500
