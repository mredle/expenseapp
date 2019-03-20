# -*- coding: utf-8 -*-

from flask import render_template, current_app, url_for
from flask_babel import _
from app.email import send_email

def send_newuser_notification(user):
    message = 'A new user has registered on ExpenseApp: {} ({})'.format(user.username, user.email)
    send_email(_('New user has registered on ExpenseApp!'),
               sender=current_app.config['ADMIN_NOREPLY_SENDER'],
               recipients=[current_app.config['ADMIN_EMAIL']],
               text_body=render_template('email/simple_email.txt',
                                         username=user.username,
                                         message=message),
               html_body=render_template('email/simple_email.html',
                                         username=user.username,
                                         message=message))

def send_validate_email(user):
    token = user.get_reset_password_token()
    url = url_for('auth.reset_password', token=token, _external=True)
    send_email(_('Validate Your Email'),
               sender=current_app.config['ADMIN_NOREPLY_SENDER'],
               recipients=[user.email],
               text_body=render_template('email/validate_email.txt',
                                         username=user.username,
                                         url=url),
               html_body=render_template('email/validate_email.html',
                                         username=user.username,
                                         url=url))

def send_password_reset_email(user):
    token = user.get_reset_password_token()
    url = url_for('auth.reset_password', token=token, _external=True)
    send_email(_('Reset Your Password'),
               sender=current_app.config['ADMIN_NOREPLY_SENDER'],
               recipients=[user.email],
               text_body=render_template('email/simple_email.txt',
                                         username=user.username,
                                         url=url),
               html_body=render_template('email/simple_email.html',
                                         username=user.username,
                                         url=url))