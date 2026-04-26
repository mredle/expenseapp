# coding=utf-8
"""Auth service — business logic for authentication, registration, and WebAuthn."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from flask import current_app

from app import db
from app.models import Challenge, Credential, User
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import (
    parse_authentication_credential_json,
    parse_registration_credential_json,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class AuthResult:
    """Outcome of an authentication attempt."""

    success: bool
    user: User | None = None
    error: str | None = None


@dataclass
class RegistrationResult:
    """Outcome of a user registration attempt."""

    success: bool
    user: User | None = None
    error: str | None = None


@dataclass
class WebAuthnRegistrationOptionsResult:
    """Result of generating WebAuthn registration options."""

    success: bool
    options_json: str | None = None
    challenge_guid: str | None = None
    error: str | None = None


@dataclass
class WebAuthnVerificationResult:
    """Result of verifying a WebAuthn response."""

    success: bool
    user: User | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Password authentication
# ---------------------------------------------------------------------------

def authenticate_password(username: str, password: str) -> AuthResult:
    """Validate username/password credentials.

    Returns an :class:`AuthResult` with ``success=True`` and the
    :class:`User` if credentials are valid, otherwise ``success=False``.
    Performs a dummy hash check on failure to equalise response time.
    """
    user = User.query.filter_by(username=username).first()

    if user is None:
        # Equalise response time so attackers cannot enumerate usernames
        User('dummy', 'dummy@example.com', 'en').check_password('dummy')
        return AuthResult(success=False, error='Invalid username or password')

    if not user.check_password(password):
        return AuthResult(success=False, error='Invalid username or password')

    return AuthResult(success=True, user=user)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_user(username: str, email: str, locale: str, password: str | None = None) -> RegistrationResult:
    """Create a new user account and API token.

    If *password* is provided it is set directly; otherwise a random password
    is generated.  Returns a :class:`RegistrationResult` with the newly
    created user.  The caller is responsible for sending notification/validation
    emails.
    """
    user = User(username=username, email=email, locale=locale)
    if password:
        user.set_password(password)
    else:
        user.set_random_password()
    user.get_token()
    db.session.add(user)
    return RegistrationResult(success=True, user=user)


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

def request_password_reset(email: str) -> User | None:
    """Look up a user by email for password reset.

    Returns the :class:`User` if found, ``None`` otherwise.
    The caller is responsible for sending the reset email.
    """
    return User.query.filter_by(email=email.lower()).first()


def verify_reset_token(token: str) -> User | None:
    """Validate a password-reset JWT and return the user, or ``None``."""
    return User.verify_reset_password_token(token)


def set_user_password(user: User, password: str) -> None:
    """Set a new password for *user*."""
    user.set_password(password)


# ---------------------------------------------------------------------------
# WebAuthn registration
# ---------------------------------------------------------------------------

def get_registration_user(current_user_obj: Any, token: str | None) -> User | None:
    """Resolve the user for a WebAuthn registration flow.

    Uses the authenticated user if available, otherwise falls back to
    the reset-password token from the cookie.
    """
    if current_user_obj and hasattr(current_user_obj, 'is_authenticated') and current_user_obj.is_authenticated:
        return current_user_obj._get_current_object()
    if token:
        return User.verify_reset_password_token(token)
    return None


def generate_webauthn_registration_options(user: User) -> WebAuthnRegistrationOptionsResult:
    """Generate WebAuthn registration options for *user*.

    Creates a :class:`Challenge` in the database and returns the JSON
    options string along with the challenge GUID.
    """
    options = generate_registration_options(
        rp_id=current_app.config['RP_ID'],
        rp_name=current_app.config['RP_NAME'],
        user_id=user.guid.hex.encode('utf-8'),
        user_name=user.username,
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=cred.id, transports=cred.transports)
            for cred in user.credentials
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED,
            resident_key=ResidentKeyRequirement.REQUIRED,
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

    return WebAuthnRegistrationOptionsResult(
        success=True,
        options_json=options_to_json(options),
        challenge_guid=str(challenge.guid),
    )


def verify_webauthn_registration(
    user: User,
    session_id: str,
    credential_json: Any,
) -> WebAuthnVerificationResult:
    """Verify a WebAuthn registration response and persist the credential.

    Returns a :class:`WebAuthnVerificationResult` indicating success or failure.
    """
    challenge = Challenge.query.filter_by(guid=session_id).first()
    if not challenge:
        return WebAuthnVerificationResult(success=False, error='Invalid session')

    try:
        credential = parse_registration_credential_json(credential_json)
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=challenge.challenge,
            expected_rp_id=current_app.config['RP_ID'],
            expected_origin=current_app.config['RP_ORIGIN'],
            require_user_verification=False,
        )
    except Exception as err:
        current_app.logger.error(f'WebAuthn Error: {err}')
        return WebAuthnVerificationResult(
            success=False,
            error='Invalid credential or server error',
        )

    new_credential = Credential(
        id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        transports=credential_json.get('response', {}).get('transports', []),
        user=user,
    )
    user.credentials.append(new_credential)
    db.session.commit()

    return WebAuthnVerificationResult(success=True, user=user)


# ---------------------------------------------------------------------------
# WebAuthn authentication
# ---------------------------------------------------------------------------

def generate_webauthn_authentication_options() -> WebAuthnRegistrationOptionsResult:
    """Generate WebAuthn authentication options (discoverable credential flow).

    Returns the JSON options string and challenge GUID.
    """
    options = generate_authentication_options(
        rp_id=current_app.config['RP_ID'],
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    challenge = Challenge(options.challenge)
    db.session.add(challenge)
    db.session.commit()

    return WebAuthnRegistrationOptionsResult(
        success=True,
        options_json=options_to_json(options),
        challenge_guid=str(challenge.guid),
    )


def verify_webauthn_authentication(
    session_id: str,
    credential_json: Any,
) -> WebAuthnVerificationResult:
    """Verify a WebAuthn authentication response.

    Resolves the user from the resident-key user handle, verifies the
    assertion, updates the sign count, and returns the authenticated user.
    """
    challenge = Challenge.query.filter_by(guid=session_id).first()
    if not challenge:
        return WebAuthnVerificationResult(success=False, error='Invalid session')

    try:
        credential = parse_authentication_credential_json(credential_json)

        if not credential.response.user_handle:
            raise Exception('No user handle returned. Resident key required.')

        user_guid_hex = credential.response.user_handle.decode('utf-8')
        user = User.query.filter_by(guid=uuid.UUID(user_guid_hex)).first()

        if not user:
            raise Exception('User associated with this credential not found.')

        # Find matching credential in memory to bypass Oracle BLOB limitation
        user_credential = None
        for cred in user.credentials:
            if cred.id == credential.raw_id:
                user_credential = cred
                break

        if user_credential is None:
            raise Exception('Could not find corresponding public key in DB')

        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge.challenge,
            expected_rp_id=current_app.config['RP_ID'],
            expected_origin=current_app.config['RP_ORIGIN'],
            credential_public_key=user_credential.public_key,
            credential_current_sign_count=user_credential.sign_count,
            require_user_verification=False,
        )
    except Exception as err:
        current_app.logger.error(f'WebAuthn Error: {err}')
        return WebAuthnVerificationResult(
            success=False,
            error='Invalid credential or server error',
        )

    # Update sign count and link challenge to user
    user_credential.sign_count = verification.new_sign_count
    challenge.user = user
    db.session.commit()

    return WebAuthnVerificationResult(success=True, user=user)
