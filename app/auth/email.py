# -*- coding: utf-8 -*-

from flask import render_template, current_app
from flask_babel import _
from app.email import send_email

def send_newuser_notification(user):
    send_email(_('New user has registered on ExpenseApp!'),
               sender=current_app.config['ADMIN_NOREPLY_SENDER'],
               recipients=[current_app.config['ADMIN_EMAIL']],
               text_body=render_template('email/notification_newuser.txt',
                                         user=user),
               html_body=render_template('email/notification_newuser.html',
                                         user=user))

def send_validate_email(user):
    token = user.get_reset_password_token()
    send_email(_('Validate Your Email'),
               sender=current_app.config['ADMIN_NOREPLY_SENDER'],
               recipients=[user.email],
               text_body=render_template('email/validate_email.txt',
                                         user=user, token=token),
               html_body=render_template('email/validate_email.html',
                                         user=user, token=token))

def send_password_reset_email(user):
    token = user.get_reset_password_token()
    send_email(_('Reset Your Password'),
               sender=current_app.config['ADMIN_NOREPLY_SENDER'],
               recipients=[user.email],
               text_body=render_template('email/reset_password.txt',
                                         user=user, token=token),
               html_body=render_template('email/reset_password.html',
                                         user=user, token=token))