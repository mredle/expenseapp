"""Application configuration.

All settings are driven by environment variables with sensible development defaults.
Copy ``.env.sample`` to ``.env`` for local overrides.
"""

from __future__ import annotations

import os

from apscheduler.jobstores.redis import RedisJobStore
from dotenv import load_dotenv

os.environ['TZ'] = 'Europe/Zurich'
basedir: str = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    """Central configuration loaded from environment variables."""

    # App Settings
    ITEMS_PER_PAGE: int = 10
    MESSAGES_PER_PAGE: int = 10
    LANGUAGES: list[str] = ['de', 'en']
    SECRET_KEY: str = os.environ.get('SECRET_KEY') or 'this-is-a-very-long-dummy-secret-key-for-testing-purposes'
    RP_ID: str = os.environ.get('RP_ID') or 'localhost'
    RP_ORIGIN: str = os.environ.get('RP_ORIGIN') or f'http://{RP_ID}:5000'
    RP_NAME: str = os.environ.get('RP_NAME') or 'Expense App'

    # Admin settings
    ADMIN_NOREPLY_SENDER: str = os.environ.get('ADMIN_NOREPLY_SENDER') or 'no-reply@expenseapp'
    ADMIN_USERNAME: str = os.environ.get('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD: str = os.environ.get('ADMIN_PASSWORD') or 'pw'
    ADMIN_EMAIL: str = os.environ.get('ADMIN_EMAIL') or 'admin@expenseapp'

    # DB Settings
    DB_TYPE: str = os.environ.get('DB_TYPE') or 'mysql'
    DB_HOST: str = os.environ.get('DB_HOST') or 'localhost'
    DB_PORT: int = int(os.environ.get('DB_PORT') or 3306)
    DB_USER: str = os.environ.get('DB_USER') or 'user'
    DB_PW: str = os.environ.get('DB_PW') or 'pw'
    DB_NAME: str = os.environ.get('DB_NAME') or 'expenseapp'
    TNS_ADMIN: str = os.environ.get('TNS_ADMIN') or '/opt/OCIWallet'
    WALLET_PW: str = os.environ.get('WALLET_PW') or 'pw'

    if os.environ.get('DATABASE_URL'):
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    else:
        if DB_TYPE == 'sqlite':
            SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_HOST}'
        elif DB_TYPE == 'mariadb':
            SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{DB_USER}:{DB_PW}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4'
        elif DB_TYPE == 'mysql':
            SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{DB_USER}:{DB_PW}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4'
        elif DB_TYPE == 'postgres':
            SQLALCHEMY_DATABASE_URI = f'postgresql+psycopg2://{DB_USER}:{DB_PW}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
        elif DB_TYPE == 'oracle':
            SQLALCHEMY_DATABASE_URI = f'oracle+oracledb://{DB_USER}:{DB_PW}@{DB_HOST}:{DB_PORT}/?service_name={DB_NAME}'
        elif DB_TYPE == 'oci':
            SQLALCHEMY_DATABASE_URI = f'oracle+oracledb://{DB_USER}:{DB_PW}@{DB_NAME}'
            SQLALCHEMY_ENGINE_OPTIONS = {
                'pool_pre_ping': True,
                'thick_mode': {
                    'config_dir': TNS_ADMIN
                },
                'connect_args': {
                    'user': DB_USER,
                    'password': DB_PW,
                    'dsn': DB_NAME,
                    'config_dir': TNS_ADMIN,
                    'wallet_location': TNS_ADMIN,
                    'wallet_password': WALLET_PW,
                },
            }

    SQLALCHEMY_POOL_RECYCLE: int = 480

    # Mail settings
    MAIL_SERVER: str = os.environ.get('MAIL_SERVER') or 'localhost'
    MAIL_PORT: int = int(os.environ.get('MAIL_PORT') or 1025)
    MAIL_USE_TLS: bool = (os.environ.get('MAIL_USE_TLS') is not None) and (os.environ.get('MAIL_USE_SSL') is None)
    MAIL_USE_SSL: bool = (os.environ.get('MAIL_USE_SSL') is not None) and (os.environ.get('MAIL_USE_TLS') is None)
    MAIL_USERNAME: str | None = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD: str | None = os.environ.get('MAIL_PASSWORD')

    # Storage Configuration
    STORAGE_DEFAULT_BACKEND: str = os.environ.get('STORAGE_DEFAULT_BACKEND', 'local')
    STORAGE_LOCAL_PATH: str = os.environ.get('STORAGE_LOCAL_PATH', './app')

    # S3 Configuration
    S3_BUCKET_NAME: str = os.environ.get('S3_BUCKET_NAME', 'expenseapp-bucket')
    S3_REGION: str = os.environ.get('S3_REGION', 'eu-central-1')
    S3_ENDPOINT_URL: str | None = os.environ.get('S3_ENDPOINT_URL')

    # Image configuration
    IMAGE_ROOT_PATH: str = STORAGE_LOCAL_PATH
    IMAGE_DEFAULT_FORMAT: str = os.environ.get('IMAGE_DEFAULT_FORMAT') or 'JPEG'
    IMAGE_TMP_PATH: str = os.environ.get('IMAGE_TMP_PATH') or 'static/tmp'
    IMAGE_IMG_PATH: str = os.environ.get('IMAGE_IMG_PATH') or 'static/img'
    IMAGE_TIMG_PATH: str = os.environ.get('IMAGE_TIMG_PATH') or 'static/timg'
    if STORAGE_DEFAULT_BACKEND == 's3':
        IMAGE_TMP_PATH = os.environ.get('IMAGE_TMP_PATH') or 'tmp'
        IMAGE_IMG_PATH = os.environ.get('IMAGE_IMG_PATH') or 'images'
        IMAGE_TIMG_PATH = os.environ.get('IMAGE_TIMG_PATH') or 'thumbnails'
    UPLOADS_DEFAULT_DEST: str = os.path.join(IMAGE_ROOT_PATH, IMAGE_TMP_PATH)
    UPLOADED_IMAGES_DEST: str = os.path.join(IMAGE_ROOT_PATH, IMAGE_TMP_PATH)
    THUMBNAIL_SIZES: list[int] = [32, 64, 128, 256, 512, 1024, 2048]

    # Redis Settings
    REDIS_HOST: str = os.environ.get('REDIS_HOST') or 'localhost'
    REDIS_PORT: int = int(os.environ.get('REDIS_PORT') or 6379)
    REDIS_DB: int = int(os.environ.get('REDIS_DB') or 0)
    REDIS_PASSWORD: str = os.environ.get('REDIS_PASSWORD') or 'pw'
    REDIS_URL: str = os.environ.get('REDIS_URL') or f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    RATELIMIT_STORAGE_URI: str = REDIS_URL

    # Scheduler settings
    SCHEDULER_API_ENABLED: bool = True
    SCHEDULER_JOBSTORES: dict = {
        'default': RedisJobStore(
            db=REDIS_DB,
            jobs_key='housekeeping_jobs',
            run_times_key='housekeeping_jobs_running',
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
        )
    }
