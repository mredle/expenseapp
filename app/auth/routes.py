# coding=utf-8
import json
import uuid

from flask import request, render_template, make_response, flash, redirect, url_for, current_app
from flask_login import current_user, login_user, logout_user
from flask_babel import _
from werkzeug.urls import url_parse

from app import db
from app.auth import bp
from app.auth.forms import AuthenticatePasswordForm, RegistrationForm, ResetUserRequestForm, RegisterFIDO2Form, RegisterPasswordForm
from app.auth.email import send_validate_email, send_newuser_notification
from app.models import Challenge, User, Credential
from app.db_logging import log_login, log_login_denied, log_logout, log_register, log_reset_password_request, log_reset_password

from flask import Flask, render_template, request
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    RegistrationCredential,
    AuthenticationCredential,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier


# routes for rendered pages
@bp.route('/login')
def login():
    return redirect(url_for('auth.authenticate_fido2'))


@bp.route('/authenticate_fido2', methods=['GET'])
def authenticate_fido2():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    return render_template('auth/authenticate_fido2.html', title=_('Sign In'))


@bp.route('/authenticate_fido2_error', methods=['GET'])
def authenticate_fido2_error():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    flash(_('Login failed'))
    return redirect(url_for('main.index'))


@bp.route('/authenticate_fido2_success', methods=['GET'])
def authenticate_fido2_success():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    flash(_('Login successful'))
    return redirect(url_for('main.index'))


@bp.route('/authenticate_password', methods=['GET', 'POST'])
def authenticate_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = AuthenticatePasswordForm()
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
    return render_template('auth/authenticate_password.html', title=_('Sign In'), form=form)


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
    if form.validate_on_submit():
        user = User(username=form.username.data, 
                    email=form.email.data,
                    locale=form.locale.data)
        user.set_random_password()
        user.get_token()
        db.session.add(user)
        log_register(request.path, user)
        send_newuser_notification(user)
        send_validate_email(user)
        flash(_('Please check your email to activate your account'))
        return redirect(url_for('auth.login'))
    return render_template('edit_form.html', title=_('Register'), form=form)


@bp.route('/reset_authentication', methods=['GET', 'POST'])
def reset_authentication():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = ResetUserRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            send_validate_email(user)
        log_reset_password_request(request.path, user)
        flash(_('Please check your email to activate your account'))
        return redirect(url_for('auth.login'))
    return render_template('edit_form.html', 
                           title=_('Reset Login'), 
                           form=form)


@bp.route('/register_fido2/<token>', methods=['GET'])
def register_fido2(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('main.index'))
    form = RegisterFIDO2Form()
    form.email.default = user.email
    form.process() # process choices & default
    if form.validate_on_submit():
        log_reset_password('/register_fido2/<token>', user)
        flash(_('Your device is now registered for passwordless authentication'))
        return redirect(url_for('auth.login'))

    response = make_response(render_template('auth/register_fido2.html', 
                                             title=_('Enable passwordless authentication'), 
                                             form=form,
                                             token=token))
    response.set_cookie(key = 'register_fido2.token', 
                        value = token,
                        max_age = 3600)
    return response


@bp.route('/register_password/<token>', methods=['GET', 'POST'])
def register_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('main.index'))
    form = RegisterPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        log_reset_password('/register_password/<token>', user)
        flash(_('Your password has been set'))
        return redirect(url_for('auth.login'))
    return render_template('auth/register_password.html', 
                           title=_('Set your password'), 
                           form=form,
                           token=token)


@bp.route('/generate-registration-options', methods=['GET'])
def handler_generate_registration_options():
    token = request.cookies.get('register_fido2.token')
    user = User.verify_reset_password_token(token)
    
    options = generate_registration_options(
        rp_id=current_app.config['RP_ID'],
        rp_name=current_app.config['RP_NAME'],
        user_id=user.guid.hex,
        user_name=user.username,
        exclude_credentials=[
            {'id': cred.id, 'transports': cred.transports, 'type': 'public-key'}
            for cred in user.credentials
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )

    challenge = Challenge(options.challenge)
    challenge.user = user
    db.session.add(challenge)
    db.session.commit()

    response = make_response(options_to_json(options))
    response.set_cookie(key = 'register_fido2.session', 
                        value = str(challenge.guid),
                        max_age = 3600)
    return response


@bp.route('/verify-registration-response', methods=['POST'])
def handler_verify_registration_response():
    body = request.get_data()
    token = request.cookies.get('register_fido2.token')
    user = User.verify_reset_password_token(token)

    session_id = request.cookies.get('register_fido2.session')
    challenge = Challenge.query.filter_by(guid=session_id).first()

    try:
        credential = RegistrationCredential.parse_raw(body)
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=challenge.challenge,
            expected_rp_id=current_app.config['RP_ID'],
            expected_origin=current_app.config['RP_ORIGIN'],
            require_user_verification=True
        )
    except Exception as err:
        print(err)
        return {'verified': False, 'msg': str(err), 'status': 400}
    
    new_credential = Credential(id=verification.credential_id,
                                public_key = verification.credential_public_key,
                                sign_count = verification.sign_count,
                                transports = json.loads(body).get('transports', []),
                                user = user)

    user.credentials.append(new_credential)
    db.session.commit()

    response = make_response({'verified': True})
    response.set_cookie(key = 'register_fido2.session', 
                        value = '',
                        expires=0)
    return response


@bp.route('/generate-authentication-options', methods=['GET'])
def handler_generate_authentication_options():

    options = generate_authentication_options(
        rp_id=current_app.config['RP_ID'],
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    challenge = Challenge(options.challenge)
    db.session.add(challenge)
    db.session.commit()

    response = make_response(options_to_json(options))
    response.set_cookie(key = 'authenticate_fido2.session', 
                        value = str(challenge.guid),
                        max_age = 3600)
    return response


@bp.route('/verify-authentication-response', methods=['POST'])
def handler_verify_authentication_response():
    body = request.get_data()
    
    session_id = request.cookies.get('authenticate_fido2.session')
    challenge = Challenge.query.filter_by(guid=session_id).first()

    try:
        credential = AuthenticationCredential.parse_raw(body)

        # Find the user's corresponding public key
        user_credential = Credential.query.filter_by(id=credential.raw_id).first()
        user = user_credential.user

        if user_credential is None:
            raise Exception('Could not find corresponding public key in DB')
        
        # Verify the assertion
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge.challenge,
            expected_rp_id=current_app.config['RP_ID'],
            expected_origin=current_app.config['RP_ORIGIN'],
            credential_public_key=user_credential.public_key,
            credential_current_sign_count=user_credential.sign_count,
            require_user_verification=True,
        )
    except Exception as err:
        return {'verified': False, 'msg': str(err), 'status': 400}

    # Update our credential's sign count to what the authenticator says it is now
    user_credential.sign_count = verification.new_sign_count
    challenge.user = user
    log_login(request.path, user)
    login_user(user, remember=True)
    db.session.commit()

    response = make_response({'verified': True})
    response.set_cookie(key = 'authenticate_fido2.session', 
                        value = '',
                        expires=0)
    return response
