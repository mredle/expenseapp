"""ExpenseApp application factory and extension initialization."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler, SMTPHandler

from flask import Flask, current_app, request
from flask_apscheduler import APScheduler
from flask_babel import Babel, lazy_gettext as _l
from flask_bootstrap import Bootstrap5
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import AnonymousUserMixin, LoginManager, current_user
from flask_mail import Mail
from flask_migrate import Migrate
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
from flask_uploads import IMAGES, UploadSet, configure_uploads
from prometheus_client import CollectorRegistry
from prometheus_flask_exporter import PrometheusMetrics
from redis import Redis
import rq

from config import Config


def _is_server_process() -> bool:
    """Return True only for long-lived WSGI server processes.

    Prevents APScheduler from being started inside short-lived ``flask`` CLI
    commands (``db upgrade``, ``dbinit``, ``translate``, …).  Those commands
    load ``expenseapp:app`` via ``FLASK_APP`` just like gunicorn does, but they
    must exit cleanly after finishing their task — a running APScheduler thread
    (plus its RedisJobStore connection) would keep the process alive
    indefinitely (0 % CPU, blocking the startup loop in ``run_as_service.sh``).

    Recognised server processes:

    * **gunicorn / uwsgi** — ``sys.argv[0]`` basename contains ``gunicorn``
      or ``uwsgi``.
    * **``flask run``** — Flask sets ``FLASK_RUN_FROM_CLI=true`` for every
      ``flask`` subcommand, so we additionally require ``'run'`` to appear in
      ``sys.argv``.  When Werkzeug's reloader is active the parent process
      spawns a child with ``WERKZEUG_RUN_MAIN=true``; only that child (or the
      single process when no reloader is used) owns the scheduler to prevent
      duplicate instances.
    """
    prog = os.path.basename(sys.argv[0] if sys.argv else '')
    # gunicorn / uwsgi style servers
    if 'gunicorn' in prog or 'uwsgi' in prog:
        return True
    # `flask run` dev server
    if os.environ.get('FLASK_RUN_FROM_CLI') == 'true' and 'run' in sys.argv:
        werkzeug_main = os.environ.get('WERKZEUG_RUN_MAIN')
        # reloader child → True; reloader parent → False; no reloader → True
        return werkzeug_main in ('true', None)
    return False


class Anonymous(AnonymousUserMixin):
    """Anonymous user stub returned when no user is logged in."""

    def __init__(self) -> None:
        self.username = 'Guest'


db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
login.anonymous_user = Anonymous
login.login_message = _l('Please log in to access this page.')
images = UploadSet('images', IMAGES)
mail = Mail()
bootstrap = Bootstrap5()
moment = Moment()
babel = Babel()
scheduler = APScheduler()
limiter = Limiter(key_func=get_remote_address)


def get_locale() -> str:
    """Return the best-matching locale for the current request."""
    try:
        if current_user.is_authenticated:
            return current_user.locale
        else:
            return request.accept_languages.best_match(current_app.config['LANGUAGES'])
    except Exception:
        return 'en'


def create_app(config_class: type = Config) -> Flask:
    """Application factory: create and configure the Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    configure_uploads(app, images)
    mail.init_app(app)
    bootstrap.init_app(app)
    moment.init_app(app)
    babel.init_app(app, locale_selector=get_locale)
    limiter.init_app(app)
    if app.config['SCHEDULER_ENABLED'] and _is_server_process() and not scheduler.running:
        scheduler.init_app(app)
        scheduler.start()

    PrometheusMetrics(app, registry=CollectorRegistry())

    app.redis = Redis.from_url(app.config['REDIS_URL'])
    app.task_queue = rq.Queue('expenseapp-tasks', connection=app.redis)

    from app.errors import bp as errors_bp
    app.register_blueprint(errors_bp, url_prefix='/error')

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.media import bp as media_bp
    app.register_blueprint(media_bp, url_prefix='/media')

    from app.apis import bp as apis_bp
    app.register_blueprint(apis_bp, url_prefix='/apis')
    CORS(app, resources={r'/apis/*': {'origins': '*'}}, supports_credentials=False)

    from app.event import bp as event_bp
    app.register_blueprint(event_bp, url_prefix='/event')

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.mobile import bp as mobile_bp
    app.register_blueprint(mobile_bp, url_prefix='/mobile')

    if not app.debug and not app.testing:
        if app.config['MAIL_SERVER']:
            auth = None
            if app.config['MAIL_USERNAME'] or app.config['MAIL_PASSWORD']:
                auth = (app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            secure = None
            if app.config['MAIL_USE_TLS'] or app.config['MAIL_USE_SSL']:
                secure = ()
            mail_handler = SMTPHandler(
                mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
                fromaddr=app.config['ADMIN_NOREPLY_SENDER'],
                toaddrs=[app.config['ADMIN_EMAIL']], subject='Failure',
                credentials=auth, secure=secure)
            mail_handler.setLevel(logging.ERROR)
            app.logger.addHandler(mail_handler)

        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/errorlog.log', maxBytes=10240,
                                           backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('App startup')

    return app
