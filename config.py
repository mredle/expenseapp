# -*- coding: utf-8 -*-

import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_RECYCLE = 480
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMIN_NOREPLY_SENDER = os.environ.get('ADMIN_NOREPLY_SENDER') or 'no-reply@expenseapp'
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'you-will-never-guess'
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@expenseapp'
    POSTS_PER_PAGE = 10
    MESSAGES_PER_PAGE = 10
    LANGUAGES = ['en', 'de']
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://'
