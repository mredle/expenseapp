# coding=utf-8

from flask import request, render_template, flash, redirect, url_for, current_app
from flask_login import current_user, login_user, logout_user
from flask_babel import _
from werkzeug.urls import url_parse

from app import db
from app.auth import bp
from app.auth.forms import LoginForm, RegistrationForm, ResetPasswordRequestForm, ResetPasswordForm
from app.auth.email import send_validate_email, send_password_reset_email, send_newuser_notification
from app.models import User
from app.db_logging import log_login, log_login_denied, log_logout, log_register, log_reset_password_request, log_reset_password
      
# routes for rendered pages
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            log_login_denied(request.path, form.username.data)
            flash(_('Invalid username or password'))
            return redirect(url_for('auth.login'))
        log_login(request.path, user)
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)
    return render_template('auth/login.html', title=_('Sign In'), form=form)


@bp.route('/logout')
def logout():
    log_logout(request.path, current_user)
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    form.timezone.choices = [(x, x) for x in current_app.config['TIMEZONES']]
    if form.validate_on_submit():
        user = User(username=form.username.data, 
                    email=form.email.data,
                    locale=form.locale.data,
                    timezone=form.timezone.data)
        user.set_random_password()
        user.get_token()
        db.session.add(user)
        log_register(request.path, user)
        send_newuser_notification(user)
        send_validate_email(user)
        flash(_('Congratulations, you are now a registered user!'))
        flash(_('Please check your email to activate your account'))
        return redirect(url_for('auth.login'))
    return render_template('edit_form.html', title=_('Register'), form=form)

@bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            send_password_reset_email(user)
        log_reset_password_request(request.path, user)
        flash(_('Check your email for the instructions to reset your password'))
        return redirect(url_for('auth.login'))
    return render_template('edit_form.html', title=_('Reset Password'), form=form)


@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('main.index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        log_reset_password(request.path, user)
        flash(_('Your password has been reset.'))
        return redirect(url_for('auth.login'))
    return render_template('edit_form.html', title=_('Set your password'), form=form)
