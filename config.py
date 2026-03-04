# -*- coding: utf-8 -*-

import os
from dotenv import load_dotenv
from apscheduler.jobstores.redis import RedisJobStore

os.environ['TZ']= 'Europe/Zurich'
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    RP_ID = os.environ.get('RP_ID') or 'localhost'
    RP_ORIGIN = os.environ.get('RP_ORIGIN') or 'http://'+RP_ID+':5000'
    RP_NAME = os.environ.get('RP_NAME') or 'Expense App'
    DB_TYPE = os.environ.get('DB_TYPE') or 'mysql'
    DB_HOST = os.environ.get('DB_HOST') or 'localhost'
    DB_PORT = os.environ.get('DB_PORT') or 3306
    DB_USER = os.environ.get('DB_USER') or 'user'
    DB_PW = os.environ.get('DB_PW') or 'pw'
    DB_NAME = os.environ.get('DB_NAME') or 'expenseapp'
    TNS_ADMIN = os.environ.get('TNS_ADMIN') or '/opt/OCIWallet'
    WALLET_PW = os.environ.get('WALLET_PW') or 'pw'

    if os.environ.get('DATABASE_URL'):
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    else:
        if DB_TYPE=='sqlite':
            SQLALCHEMY_DATABASE_URI = 'sqlite:///{}'.format(DB_HOST)
        elif DB_TYPE=='mariadb':
            SQLALCHEMY_DATABASE_URI = 'mariadb+mariadbconnector://{}:{}@{}:{}/{}'.format(DB_USER, DB_PW, DB_HOST, DB_PORT, DB_NAME)
        elif DB_TYPE=='mysql':
            SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://{}:{}@{}:{}/{}?charset=utf8mb4'.format(DB_USER, DB_PW, DB_HOST, DB_PORT, DB_NAME)
        elif DB_TYPE=='postgres':
            SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://{}:{}@{}:{}/{}'.format(DB_USER, DB_PW, DB_HOST, DB_PORT, DB_NAME)
        elif DB_TYPE=='oracle':
            SQLALCHEMY_DATABASE_URI = 'oracle+oracledb://{}:{}@{}:{}/?service_name={}'.format(DB_USER, DB_PW, DB_HOST, DB_PORT, DB_NAME)
        elif DB_TYPE=='oci':
            SQLALCHEMY_DATABASE_URI = 'oracle+oracledb://{}:{}@{}'.format(DB_USER, DB_PW, DB_NAME)
            SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'thick_mode': {
            'config_dir': TNS_ADMIN
            },'connect_args': {
               'user': DB_USER, 
               'password': DB_PW,
               'dsn': DB_NAME,
               'config_dir': TNS_ADMIN,  # directory containing tnsnames.ora
               'wallet_location': TNS_ADMIN,  # directory containing ewallet.pem
               'wallet_password': WALLET_PW  # password for the PEM file
               }
            }
    
    SQLALCHEMY_POOL_RECYCLE = 480
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'localhost'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 1025)
    MAIL_USE_TLS = (os.environ.get('MAIL_USE_TLS') is not None) and (os.environ.get('MAIL_USE_SSL') is None)
    MAIL_USE_SSL = (os.environ.get('MAIL_USE_SSL') is not None) and (os.environ.get('MAIL_USE_TLS') is None)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMIN_NOREPLY_SENDER = os.environ.get('ADMIN_NOREPLY_SENDER') or 'no-reply@expenseapp'
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'pw'
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@expenseapp'
    IMAGE_DEFAULT_FORMAT = os.environ.get('IMAGE_DEFAULT_FORMAT') or 'JPEG'
    IMAGE_ROOT_PATH = os.environ.get('IMAGE_ROOT_PATH') or './app'
    IMAGE_TMP_PATH = os.environ.get('IMAGE_TMP_PATH') or 'static/tmp/'
    IMAGE_IMG_PATH = os.environ.get('IMAGE_IMG_PATH') or 'static/img/'
    IMAGE_TIMG_PATH = os.environ.get('IMAGE_TIMG_PATH') or 'static/timg/'
    UPLOADS_DEFAULT_DEST = os.path.join(IMAGE_ROOT_PATH, IMAGE_TMP_PATH)
    UPLOADED_IMAGES_DEST = os.path.join(IMAGE_ROOT_PATH, IMAGE_TMP_PATH)
    THUMBNAIL_SIZES = [32, 64, 128, 256, 512, 1024, 2048]
    ITEMS_PER_PAGE = 10
    MESSAGES_PER_PAGE = 10
    LANGUAGES = ['en', 'de']
    REDIS_HOST = os.environ.get('REDIS_HOST') or 'localhost'
    REDIS_PORT = os.environ.get('REDIS_PORT') or 6379
    REDIS_DB = os.environ.get('REDIS_DB') or 0
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD') or 'pw'
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://{}{}:{}/{}'.format(':'+REDIS_PASSWORD+'@' if REDIS_PASSWORD is not None else '', REDIS_HOST, REDIS_PORT, REDIS_DB)
    RATELIMIT_STORAGE_URI = REDIS_URL
    SCHEDULER_API_ENABLED = True
    SCHEDULER_JOBSTORES = {
        'default': RedisJobStore(db=REDIS_DB, jobs_key='housekeeping_jobs', run_times_key='housekeeping_jobs_running', host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD)
    }
    
