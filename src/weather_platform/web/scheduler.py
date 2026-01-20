import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


def update_forecast(app):
    with app.app_context():
        try:
            start_time = datetime.now()
            logger.info("Starting hourly forecast update")

            from .predictor import WeatherPredictor
            from .weather_api import get_current_weather
            from kedro.framework.session import KedroSession
            from kedro.framework.startup import bootstrap_project

            project_path = app.config['KEDRO_PROJECT_PATH']
            bootstrap_project(project_path)

            with KedroSession.create(project_path=project_path) as session:
                context = session.load_context()
                dashboard_config = context.params.get('dashboard', {})
                location_config = dashboard_config.get('location', {})
                lat = location_config.get('latitude')
                lon = location_config.get('longitude')

            if lat is None or lon is None:
                logger.error("Location coordinates not configured")
                return

            weather_data = get_current_weather(lat, lon)
            predictor = WeatherPredictor(project_path)

            current_temp = weather_data['temperature']
            start_time_weather = weather_data['start_time']

            predictor.save_temperature(start_time_weather, current_temp)

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Forecast update completed in {duration:.2f} seconds")

        except Exception as e:
            logger.error(f"Forecast update failed: {str(e)}", exc_info=True)


def init_scheduler(app) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()

    interval_minutes = app.config.get('SCHEDULER_INTERVAL', 60)

    scheduler.add_job(
        func=update_forecast,
        args=[app],
        trigger=IntervalTrigger(minutes=interval_minutes),
        id='forecast_update_job',
        name='Update Forecast',
        misfire_grace_time=60,
        coalesce=True,
        replace_existing=True
    )

    scheduler.start()
    logger.info(f"Scheduler initialized. Forecast will update every {interval_minutes} minutes")

    return scheduler
