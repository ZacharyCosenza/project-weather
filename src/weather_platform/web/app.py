import logging
from pathlib import Path
from flask import Flask
from .routes import web_bp
from .scheduler import init_scheduler

logger = logging.getLogger(__name__)


def create_app(project_path: str = None, scheduler_interval: int = 60, enable_scheduler: bool = True):
    if project_path is None:
        project_path = Path(__file__).parents[3].absolute()
    else:
        project_path = Path(project_path)

    app = Flask(__name__,
                template_folder=Path(__file__).parent / 'templates',
                static_folder=Path(__file__).parent / 'static')

    app.config['KEDRO_PROJECT_PATH'] = str(project_path)
    app.config['SCHEDULER_INTERVAL'] = scheduler_interval
    app.config['PIPELINE_NAME'] = '__default__'
    app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'

    app.register_blueprint(web_bp)

    if enable_scheduler:
        try:
            scheduler = init_scheduler(app)
            app.scheduler = scheduler
            logger.info("Scheduler initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}", exc_info=True)

    @app.teardown_appcontext
    def shutdown_scheduler(exception=None):
        if hasattr(app, 'scheduler') and app.scheduler.running:
            app.scheduler.shutdown()

    return app
