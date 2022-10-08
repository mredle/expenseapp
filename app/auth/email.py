# -*- coding: utf-8 -*-

from flask import render_template, current_app, url_for
from flask_babel import _, force_locale
from app.email import send_email

def send_newuser_notification(user):
    with force_locale('en'):
        message = _('A new user has registered on ExpenseApp: %(username)s (%(email)s)', username=user.username, email=user.email)
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
    with force_locale(user.locale):
        token = user.get_reset_password_token()
        url = url_for('auth.register_fido2', token=token, _external=True)
        send_email(_('Validate Your Email'),
                   sender=current_app.config['ADMIN_NOREPLY_SENDER'],
                   recipients=[user.email],
                   text_body=render_template('email/validate_email.txt',
                                             username=user.username,
                                             url=url),
                   html_body=render_template('email/validate_email.html',
                                             username=user.username,
                                             url=url))

def send_register_fido2_email(user):
    with force_locale(user.locale):
        token = user.get_reset_password_token()
        url = url_for('auth.register_fido2', token=token, _external=True)
        send_email(_('Reset Your Password'),
                   sender=current_app.config['ADMIN_NOREPLY_SENDER'],
                   recipients=[user.email],
                   text_body=render_template('email/register_fido2.txt',
                                             username=user.username,
                                             url=url),
                   html_body=render_template('email/register_fido2.html',
                                             username=user.username,
                                             url=url))