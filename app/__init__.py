# coding=utf-8

import logging
from logging.handlers import SMTPHandler, RotatingFileHandler
from sqlalchemy import event
from sqlalchemy.engine import Engine
from redis import Redis
import rq
import os
import time
import atexit

from flask import Flask, request, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user, AnonymousUserMixin
from flask_mail import Mail
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_babel import Babel, lazy_gettext as _l
from flask_uploads import UploadSet, IMAGES, configure_uploads
from flask_apscheduler import APScheduler
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import CollectorRegistry

from config import Config

class Anonymous(AnonymousUserMixin):
  def __init__(self):
    self.username = 'Guest'


# creating the Flask application
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
login.anonymous_user = Anonymous
login.login_message = _l('Please log in to access this page.')
images = UploadSet('images', IMAGES)
mail = Mail()
bootstrap = Bootstrap()
moment = Moment()
babel = Babel()
scheduler = APScheduler()
#metrics = PrometheusMetrics.for_app_factory()
    
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    configure_uploads(app, images)
    mail.init_app(app)
    bootstrap.init_app(app)
    moment.init_app(app)
    babel.init_app(app)
    #metrics.init_app(app)
    scheduler.init_app(app)
    
    PrometheusMetrics(app, registry=CollectorRegistry())
    
    @app.before_first_request
    def init_scheduler():
        scheduler.start()
        from app import models, tasks
        # Shut down the scheduler when exiting the app
        atexit.register(lambda: scheduler.shutdown())
    
    app.redis = Redis.from_url(app.config['REDIS_URL'])
    app.task_queue = rq.Queue('expenseapp-tasks', connection=app.redis)
    
    from app.errors import bp as errors_bp
    app.register_blueprint(errors_bp, url_prefix='/error')
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.apis import bp as apis_bp
    app.register_blueprint(apis_bp, url_prefix='/apis')
    
    from app.event import bp as event_bp
    app.register_blueprint(event_bp, url_prefix='/event')
    
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
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

@babel.localeselector
def get_locale():
    # if a user is logged in, use the locale from the user settings
    # otherwise try to guess the language from the user accept
    # header the browser transmits. The best match wins.
    try:
        if current_user.is_authenticated:
            return current_user.locale
        else:
            return request.accept_languages.best_match(current_app.config['LANGUAGES'])
    except:
        return 'en'

# logging.basicConfig()
# logger = logging.getLogger("myapp.sqltime")
# logger.setLevel(logging.DEBUG)

# @event.listens_for(Engine, "before_cursor_execute")
# def before_cursor_execute(conn, cursor, statement,
#                         parameters, context, executemany):
#     conn.info.setdefault('query_start_time', []).append(time.time())
#     logger.debug("Start Query: %s", statement)

# @event.listens_for(Engine, "after_cursor_execute")
# def after_cursor_execute(conn, cursor, statement,
#                         parameters, context, executemany):
#     total = time.time() - conn.info['query_start_time'].pop(-1)
#     logger.debug("Query Complete!")
#     logger.debug("Total Time: %f", total)
    
