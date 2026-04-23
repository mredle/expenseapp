# coding=utf-8
"""Authentication routes: password login, FIDO2/WebAuthn, registration, and password reset."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from flask import current_app, flash, make_response, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_user, logout_user

from app import limiter
from app.auth import bp
from app.auth.email import send_newuser_notification, send_validate_email
from app.auth.forms import (
    AuthenticatePasswordForm,
    RegisterFIDO2Form,
    RegisterPasswordForm,
    RegistrationForm,
    ResetUserRequestForm,
)
from app.db_logging import (
    log_login,
    log_login_denied,
    log_logout,
    log_register,
    log_reset_password,
    log_reset_password_request,
)
from app.services.auth_service import (
    authenticate_password,
    generate_webauthn_authentication_options,
    generate_webauthn_registration_options,
    get_registration_user,
    register_user,
    request_password_reset,
    set_user_password,
    verify_reset_token,
    verify_webauthn_authentication,
    verify_webauthn_registration,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_safe_url(target: str) -> bool:
    """Return ``True`` if *target* is a same-origin URL (open-redirect guard)."""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


# ---------------------------------------------------------------------------
# Rendered page routes
# ---------------------------------------------------------------------------

@bp.route('/login')
def login():
    """Redirect to the default FIDO2 authentication page."""
    return redirect(url_for('auth.authenticate_fido2'))


@bp.route('/authenticate_fido2', methods=['GET'])
def authenticate_fido2():
    """Show the FIDO2 passwordless sign-in page."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    return render_template('auth/authenticate_fido2.html', title=_('Sign In'))


@bp.route('/authenticate_fido2_error', methods=['GET'])
def authenticate_fido2_error():
    """Flash a FIDO2 login failure and redirect to index."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    flash(_('Login failed'))
    return redirect(url_for('main.index'))


@bp.route('/authenticate_fido2_success', methods=['GET'])
def authenticate_fido2_success():
    """Flash a FIDO2 login success and redirect to index."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    flash(_('Login successful'))
    return redirect(url_for('main.index'))


@bp.route('/authenticate_password', methods=['GET', 'POST'])
@limiter.limit('12 per minute')
def authenticate_password_route():
    """Handle username/password authentication."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = AuthenticatePasswordForm()

    if form.validate_on_submit():
        result = authenticate_password(form.username.data, form.password.data)

        if not result.success:
            log_login_denied(request.path, form.username.data)
            flash(_('Invalid username or password'))
        else:
            log_login(request.path, result.user)
            login_user(result.user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or not is_safe_url(next_page):
                next_page = url_for('main.index')
            return redirect(next_page)

    return render_template('auth/authenticate_password.html', title=_('Sign In'), form=form)


@bp.route('/logout')
def logout():
    """Log the current user out and redirect to index."""
    log_logout(request.path, current_user)
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle new-user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]

    if form.validate_on_submit():
        result = register_user(
            username=form.username.data,
            email=form.email.data,
            locale=form.locale.data,
        )
        log_register(request.path, result.user)
        send_newuser_notification(result.user)
        send_validate_email(result.user)
        flash(_('Please check your email to activate your account'))
        return redirect(url_for('auth.login'))
    return render_template('edit_form.html', title=_('Register'), form=form)


@bp.route('/reset_authentication', methods=['GET', 'POST'])
def reset_authentication():
    """Handle a request to reset authentication credentials."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = ResetUserRequestForm()
    if form.validate_on_submit():
        user = request_password_reset(form.email.data)
        if user:
            send_validate_email(user)
        log_reset_password_request(request.path, user)
        flash(_('Please check your email to activate your account'))
        return redirect(url_for('auth.login'))
    return render_template('edit_form.html', title=_('Reset Login'), form=form)


@bp.route('/register_fido2/<token>', methods=['GET'])
def register_fido2(token: str):
    """Show the FIDO2 device-registration page for a validated token."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = verify_reset_token(token)
    if not user:
        return redirect(url_for('main.index'))
    form = RegisterFIDO2Form()
    form.email.default = user.email
    form.process()  # process choices & default
    if form.validate_on_submit():
        log_reset_password('/register_fido2/<token>', user)
        flash(_('Your device is now registered for passwordless authentication'))
        return redirect(url_for('auth.login'))

    response = make_response(render_template(
        'auth/register_fido2.html',
        title=_('Enable passwordless authentication'),
        form=form,
        token=token,
    ))
    response.set_cookie(
        key='register_fido2.token',
        value=token,
        max_age=3600,
        secure=True,
        httponly=True,
        samesite='Strict',
    )
    return response


@bp.route('/register_password/<token>', methods=['GET', 'POST'])
def register_password(token: str):
    """Allow the user to set a password after token validation."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = verify_reset_token(token)
    if not user:
        return redirect(url_for('main.index'))
    form = RegisterPasswordForm()
    if form.validate_on_submit():
        set_user_password(user, form.password.data)
        log_reset_password('/register_password/<token>', user)
        flash(_('Your password has been set'))
        return redirect(url_for('auth.login'))
    return render_template(
        'auth/register_password.html',
        title=_('Set your password'),
        form=form,
        token=token,
    )


# ---------------------------------------------------------------------------
# WebAuthn JSON API routes
# ---------------------------------------------------------------------------

@bp.route('/generate-registration-options', methods=['GET'])
def handler_generate_registration_options():
    """Return WebAuthn registration options as JSON."""
    token = request.cookies.get('register_fido2.token')
    user = get_registration_user(current_user, token)

    if not user:
        return make_response({'error': 'Unauthorized'}, 401)

    result = generate_webauthn_registration_options(user)

    response = make_response(result.options_json)
    response.set_cookie(
        key='register_fido2.session',
        value=result.challenge_guid,
        max_age=3600,
        secure=True,
        httponly=True,
        samesite='Strict',
    )
    return response


@bp.route('/verify-registration-response', methods=['POST'])
def handler_verify_registration_response():
    """Verify a WebAuthn registration response and store the credential."""
    data = request.get_json()

    token = request.cookies.get('register_fido2.token')
    user = get_registration_user(current_user, token)

    if not user:
        return make_response({'error': 'Unauthorized'}, 401)

    session_id = request.cookies.get('register_fido2.session')
    result = verify_webauthn_registration(user, session_id, data)

    if not result.success:
        return {'verified': False, 'msg': result.error, 'status': 400}

    response = make_response({'verified': True})
    response.set_cookie(
        key='register_fido2.session',
        value='',
        expires=0,
        secure=True,
        httponly=True,
        samesite='Strict',
    )
    return response


@bp.route('/generate-authentication-options', methods=['GET'])
def handler_generate_authentication_options():
    """Return WebAuthn authentication options as JSON."""
    result = generate_webauthn_authentication_options()

    response = make_response(result.options_json)
    response.set_cookie(
        key='authenticate_fido2.session',
        value=result.challenge_guid,
        max_age=3600,
        secure=True,
        httponly=True,
        samesite='Strict',
    )
    return response


@bp.route('/verify-authentication-response', methods=['POST'])
def handler_verify_authentication_response():
    """Verify a WebAuthn authentication response and log the user in."""
    data = request.get_json()

    session_id = request.cookies.get('authenticate_fido2.session')
    result = verify_webauthn_authentication(session_id, data)

    if not result.success:
        return {'verified': False, 'msg': result.error, 'status': 400}

    log_login(request.path, result.user)
    login_user(result.user, remember=True)

    response = make_response({'verified': True})
    response.set_cookie(
        key='authenticate_fido2.session',
        value='',
        expires=0,
        secure=True,
        httponly=True,
        samesite='Strict',
    )
    return response
