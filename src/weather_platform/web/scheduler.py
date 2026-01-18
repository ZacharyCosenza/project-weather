import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from kedro.framework.session import KedroSession

logger = logging.getLogger(__name__)


def run_kedro_pipeline(project_path: str, pipeline_name: str = "__default__"):
    try:
        start_time = datetime.now()
        logger.info(f"Starting Kedro pipeline run: {pipeline_name}")

        with KedroSession.create(project_path=project_path) as session:
            session.run(pipeline_name=pipeline_name)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Pipeline completed successfully in {duration:.2f} seconds")

    except Exception as e:
        logger.error(f"Pipeline run failed: {str(e)}", exc_info=True)


def init_scheduler(app) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()

    interval_minutes = app.config.get('SCHEDULER_INTERVAL', 60)
    project_path = app.config.get('KEDRO_PROJECT_PATH')
    pipeline_name = app.config.get('PIPELINE_NAME', '__default__')

    scheduler.add_job(
        func=run_kedro_pipeline,
        args=[project_path, pipeline_name],
        trigger=IntervalTrigger(minutes=interval_minutes),
        id='kedro_pipeline_job',
        name='Run Kedro Pipeline',
        misfire_grace_time=60,
        coalesce=True,
        replace_existing=True
    )

    scheduler.start()
    logger.info(f"Scheduler initialized. Pipeline will run every {interval_minutes} minutes")

    return scheduler
