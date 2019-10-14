# -*- coding: utf-8 -*-

import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
    MYSQL_PORT = os.environ.get('MYSQL_PORT') or 3306
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'user'
    MYSQL_PW = os.environ.get('MYSQL_PW') or 'pw'
    MYSQL_DB = os.environ.get('MYSQL_DB') or 'expenseapp'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://{}:{}@{}:{}/{}?charset=utf8mb4'.format(MYSQL_USER, MYSQL_PW, MYSQL_HOST, MYSQL_PORT, MYSQL_DB)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_RECYCLE = 480
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'localhost'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 1025)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL') is not None
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
    THUMBNAIL_SIZES = [32, 64, 128, 256, 512, 1024]
    ITEMS_PER_PAGE = 10
    MESSAGES_PER_PAGE = 10
    LANGUAGES = ['en', 'de']
    TIMEZONES = ['Etc/UTC', 'Europe/Zurich']
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
