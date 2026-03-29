"""Structured database logging helpers for authentication, access, and email events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app import db
from app.models import Log, User

if TYPE_CHECKING:
    from flask import Request

# Headers that must never be persisted in log traces.
_SENSITIVE_HEADERS = frozenset({
    'authorization',
    'cookie',
    'set-cookie',
    'x-api-key',
    'proxy-authorization',
})


def _sanitize_headers(request: Request) -> str:
    """Return a string representation of *request* headers with sensitive values redacted."""
    sanitized = [
        (key, '***REDACTED***' if key.lower() in _SENSITIVE_HEADERS else value)
        for key, value in request.headers.to_wsgi_list()
    ]
    return str(sanitized)


def log_add(
    severity: str,
    module: str,
    msg_type: str,
    msg: str,
    user: User,
    trace: str | None = None,
) -> None:
    """Create a :class:`Log` entry and commit it to the database."""
    if user.is_anonymous:
        user = User.query.filter_by(username='anonymous').first()
    log = Log(severity, module, msg_type, msg, user, trace)
    db.session.add(log)
    db.session.commit()


def log_login(path: str, user: User) -> None:
    """Record a successful login."""
    log_add('INFORMATION', path, 'login successful', f'User {user.username} logs in successfully', user)


def log_login_denied(path: str, username: str) -> None:
    """Record a denied login attempt."""
    user = User.query.filter_by(username='anonymous').first()
    log_add('WARNING', path, 'login denied', f'User with user name {username} tried to log in', user)


def log_logout(path: str, user: User) -> None:
    """Record a successful logout."""
    log_add('INFORMATION', path, 'logout', f'User {user.username} logs out successfully', user)


def log_register(path: str, user: User) -> None:
    """Record a new user registration."""
    log_add('INFORMATION', path, 'register', f'User {user.username} registers', user)


def log_reset_password_request(path: str, user: User) -> None:
    """Record a password-reset request."""
    log_add('INFORMATION', path, 'reset password request', f'User {user.username} requested a password reset', user)


def log_reset_password(path: str, user: User) -> None:
    """Record a completed password reset."""
    log_add('INFORMATION', path, 'reset password', f'User {user.username} reset password', user)


def log_page_access(request: Request, user: User) -> None:
    """Record a successful page access (with sanitised request headers)."""
    log_add(
        'INFORMATION', request.path, 'page access successful',
        f'User {user.username} accessed {request.path} successfully', user,
        _sanitize_headers(request),
    )


def log_page_access_denied(request: Request, user: User) -> None:
    """Record a denied page access attempt (with sanitised request headers)."""
    log_add(
        'WARNING', request.path, 'page access denied',
        f'User {user.username} was denied from accessing {request.path}', user,
        _sanitize_headers(request),
    )


def log_email(email_type: str, subject: str, body: str, recipient: str) -> None:
    """Record an outgoing email."""
    user = User.query.filter_by(username='admin').first()
    log_add('INFORMATION', email_type, 'email sent', f'User {recipient}: {subject}', user, body)


def log_error(request: Request, error_type: str) -> None:
    """Record a page-access error (with sanitised request headers)."""
    user = User.query.filter_by(username='admin').first()
    log_add(
        'ERROR', request.path, 'page access error',
        f'Error {error_type} when accessing page {request.path}', user,
        _sanitize_headers(request),
    )
