# coding=utf-8
"""Main service — business logic for currencies, users, admin, messaging, and profiles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from flask import current_app

from app import db
from app.media.processor import process_and_store_image
from app.models import (
    Currency,
    Event,
    EventCurrency,
    EventUser,
    Expense,
    Image,
    Log,
    Message,
    Notification,
    Post,
    Settlement,
    Task,
    User,
)


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class PaginatedResult:
    """Generic paginated query result."""

    items: list[Any]
    has_next: bool
    has_prev: bool
    next_num: int | None
    prev_num: int | None
    total: int


@dataclass
class CurrencyResult:
    """Outcome of a currency create/update operation."""

    success: bool
    currency: Currency | None = None
    error: str | None = None


@dataclass
class UserResult:
    """Outcome of a user create/update operation."""

    success: bool
    user: User | None = None
    error: str | None = None


@dataclass
class MessageResult:
    """Outcome of sending a message."""

    success: bool
    message: Message | None = None
    error: str | None = None


@dataclass
class TaskResult:
    """Outcome of a task operation."""

    success: bool
    task: Task | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Image operations
# ---------------------------------------------------------------------------

def get_image(guid: str) -> Image:
    """Retrieve an image by GUID or raise 404."""
    return Image.get_by_guid_or_404(guid)


def rotate_image(guid: str, degree: int) -> Image:
    """Rotate an image by *degree* degrees."""
    img = Image.get_by_guid_or_404(guid)
    img.rotate_image(degree)
    return img


# ---------------------------------------------------------------------------
# Currency operations
# ---------------------------------------------------------------------------

def list_currencies(page: int, per_page: int | None = None) -> PaginatedResult:
    """Return a paginated list of currencies, ordered by code."""
    if per_page is None:
        per_page = current_app.config['ITEMS_PER_PAGE']
    pagination = Currency.query.order_by(Currency.code.asc()).paginate(
        page=page, per_page=per_page, error_out=False,
    )
    return PaginatedResult(
        items=pagination.items,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev,
        next_num=pagination.next_num,
        prev_num=pagination.prev_num,
        total=pagination.total,
    )


def create_currency(
    code: str,
    name: str,
    number: int,
    exponent: int,
    inCHF: float,
    description: str,
    created_by: str,
) -> CurrencyResult:
    """Create a new currency and persist it."""
    currency = Currency(
        code=code,
        name=name,
        number=number,
        exponent=exponent,
        inCHF=inCHF,
        description=description,
        db_created_by=created_by,
    )
    db.session.add(currency)
    db.session.commit()
    return CurrencyResult(success=True, currency=currency)


def update_currency(
    guid: str,
    code: str,
    name: str,
    number: int,
    exponent: int,
    inCHF: float,
    description: str,
) -> CurrencyResult:
    """Update an existing currency identified by *guid*."""
    currency = Currency.get_by_guid_or_404(guid)
    currency.code = code
    currency.name = name
    currency.number = number
    currency.exponent = exponent
    currency.inCHF = inCHF
    currency.description = description
    db.session.commit()
    return CurrencyResult(success=True, currency=currency)


def get_currency(guid: str) -> Currency:
    """Retrieve a currency by GUID or raise 404."""
    return Currency.get_by_guid_or_404(guid)


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

def list_users(page: int, per_page: int | None = None) -> PaginatedResult:
    """Return a paginated list of users, ordered by username."""
    if per_page is None:
        per_page = current_app.config['ITEMS_PER_PAGE']
    pagination = User.query.order_by(User.username.asc()).paginate(
        page=page, per_page=per_page, error_out=False,
    )
    return PaginatedResult(
        items=pagination.items,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev,
        next_num=pagination.next_num,
        prev_num=pagination.prev_num,
        total=pagination.total,
    )


def get_user(guid: str) -> User:
    """Retrieve a user by GUID or raise 404."""
    return User.get_by_guid_or_404(guid)


def create_user(
    username: str,
    email: str,
    locale: str,
    about_me: str,
    password: str,
    is_admin: bool = False,
) -> UserResult:
    """Create a new user with a password and API token."""
    user = User(username=username, email=email, locale=locale, about_me=about_me)
    user.is_admin = is_admin
    user.set_password(password)
    user.get_token()
    db.session.add(user)
    db.session.commit()
    return UserResult(success=True, user=user)


def update_user(
    guid: str,
    username: str,
    email: str,
    locale: str,
    about_me: str,
    is_admin: bool,
    password: str | None = None,
) -> UserResult:
    """Update an existing user identified by *guid*.

    Returns an error result if the target is the master admin.
    """
    user = User.get_by_guid_or_404(guid)
    admin = User.query.filter_by(username='admin').first()
    if user == admin:
        return UserResult(success=False, error='Cannot change the master admin')

    user.username = username
    user.email = email
    user.locale = locale
    user.about_me = about_me
    user.is_admin = is_admin
    if password:
        user.set_password(password)
    user.get_token()
    db.session.commit()
    return UserResult(success=True, user=user)


def set_admin(guid: str) -> UserResult:
    """Grant admin privileges to the user identified by *guid*."""
    user = User.get_by_guid_or_404(guid)
    user.is_admin = True
    db.session.commit()
    return UserResult(success=True, user=user)


def revoke_admin(guid: str) -> UserResult:
    """Revoke admin privileges from the user identified by *guid*.

    Returns an error result if the target is the master admin.
    """
    user = User.get_by_guid_or_404(guid)
    admin = User.query.filter_by(username='admin').first()
    if user == admin:
        return UserResult(success=False, user=user, error='Cannot change the master admin')
    user.is_admin = False
    db.session.commit()
    return UserResult(success=True, user=user)


# ---------------------------------------------------------------------------
# Admin / logs / tasks / statistics
# ---------------------------------------------------------------------------

def list_logs(
    page: int,
    severity: str | None = None,
    user: User | None = None,
    is_admin: bool = False,
    per_page: int | None = None,
) -> PaginatedResult:
    """Return a paginated list of log entries with optional filters."""
    if per_page is None:
        per_page = current_app.config['ITEMS_PER_PAGE']
    filters = []
    if severity is not None:
        filters.append(Log.severity == severity.upper())
    if not is_admin and user is not None:
        filters.append(Log.user == user)
    pagination = Log.query.filter(*filters).order_by(Log.date.desc()).paginate(
        page=page, per_page=per_page, error_out=False,
    )
    return PaginatedResult(
        items=pagination.items,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev,
        next_num=pagination.next_num,
        prev_num=pagination.prev_num,
        total=pagination.total,
    )


def get_log_trace(log_id: int) -> Log:
    """Retrieve a single log entry by primary key or raise 404."""
    return Log.query.get_or_404(log_id)


def list_tasks(
    page: int,
    complete: bool | None = None,
    user: User | None = None,
    is_admin: bool = False,
    per_page: int | None = None,
) -> PaginatedResult:
    """Return a paginated list of background tasks with optional filters."""
    if per_page is None:
        per_page = current_app.config['ITEMS_PER_PAGE']
    filters = []
    if complete is not None:
        filters.append(Task.complete == complete)
    if not is_admin and user is not None:
        filters.append(Task.user == user)
    pagination = Task.query.filter(*filters).order_by(Task.db_created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False,
    )
    return PaginatedResult(
        items=pagination.items,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev,
        next_num=pagination.next_num,
        prev_num=pagination.prev_num,
        total=pagination.total,
    )


def remove_task(guid: str) -> TaskResult:
    """Delete a completed task by GUID."""
    task = Task.get_by_guid_or_404(guid)
    db.session.delete(task)
    db.session.commit()
    return TaskResult(success=True, task=task)


def launch_task(user: User, key: str, **kwargs: Any) -> TaskResult:
    """Launch a background task identified by *key* for *user*.

    Supported keys: ``WASTE_TIME``, ``CHECK_CURRENCIES``, ``UPDATE_CURRENCIES``,
    ``TYPE_ERROR``.
    """
    from flask_babel import _

    if key == 'WASTE_TIME':
        amount = kwargs.get('amount', 10)
        task = user.launch_task(
            'consume_time',
            _('Consuming %(amount)s s of time...', amount=amount),
            amount=amount,
        )
    elif key == 'CHECK_CURRENCIES':
        task = user.launch_task('check_rates_yahoo', _('Checking currencies...'))
    elif key == 'UPDATE_CURRENCIES':
        source = kwargs.get('source', 'yahoo')
        if source == 'yahoo':
            task = user.launch_task('update_rates_yahoo', _('Updating currencies...'))
        else:
            return TaskResult(success=False, error=f'Unknown source: {source}')
    elif key == 'TYPE_ERROR':
        amount = kwargs.get('amount', 1)
        task = None
        for count in range(amount):
            task = user.launch_task(
                key.lower(),
                _('Creating %(count)s/%(amount)s errors of type %(error_type)s ...', count=count + 1, amount=amount, error_type=key),
            )
    else:
        return TaskResult(success=False, error=f'Unknown task key: {key}')

    db.session.commit()
    return TaskResult(success=True, task=task)


def get_statistics(user: User, is_admin: bool) -> list[tuple[str, int]]:
    """Return model statistics visible to *user*.

    Admins see all models; regular users see a subset.
    """
    if is_admin:
        classes = [Currency, User, Message, Notification, Image, Log, Task, Event, EventUser, EventCurrency, Expense, Settlement, Post]
    else:
        classes = [Message, Notification, Log, Task, Expense, Settlement, Event, EventUser, EventCurrency, Post]

    stats: list[tuple[str, int]] = []
    for cls in classes:
        stats.extend(cls.get_class_stats(user))
    return stats


# ---------------------------------------------------------------------------
# Profile operations
# ---------------------------------------------------------------------------

def update_profile(user: User, username: str, about_me: str, locale: str) -> None:
    """Update the profile fields of *user*."""
    user.username = username
    user.about_me = about_me
    user.locale = locale
    db.session.commit()


def update_profile_picture(user: User, file_stream: Any, filename: str) -> Image:
    """Process and store a new profile picture for *user*.

    Returns the newly created :class:`Image`.
    Raises on processing failure.
    """
    new_image = process_and_store_image(file_stream, filename)
    user.profile_picture = new_image
    db.session.commit()
    return new_image


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------

def send_message(sender: User, recipient_id: int, body: str) -> MessageResult:
    """Send a direct message from *sender* to the user with *recipient_id*."""
    recipient = db.session.get(User, recipient_id)
    if not recipient:
        return MessageResult(success=False, error='Recipient not found')
    msg = Message(author=sender, recipient=recipient, body=body)
    db.session.add(msg)
    recipient.add_notification('unread_message_count', recipient.new_messages())
    db.session.commit()
    return MessageResult(success=True, message=msg)


def list_messages(user: User, page: int, per_page: int | None = None) -> PaginatedResult:
    """Return a paginated list of messages sent and received by *user*."""
    if per_page is None:
        per_page = current_app.config['ITEMS_PER_PAGE']
    pagination = user.messages_sent.union(user.messages_received).order_by(
        Message.timestamp.desc(),
    ).paginate(page=page, per_page=per_page, error_out=False)
    return PaginatedResult(
        items=pagination.items,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev,
        next_num=pagination.next_num,
        prev_num=pagination.prev_num,
        total=pagination.total,
    )


def mark_messages_read(user: User) -> None:
    """Mark all messages as read for *user*."""
    user.last_message_read_time = datetime.now(timezone.utc)
    user.add_notification('unread_message_count', 0)
    db.session.commit()


def get_notifications(user: User, since: float) -> list[dict[str, Any]]:
    """Return notifications for *user* newer than *since* (POSIX timestamp)."""
    notifs = user.notifications.filter(
        Notification.timestamp > since,
    ).order_by(Notification.timestamp.asc())
    return [
        {'name': n.name, 'data': n.get_data(), 'timestamp': n.timestamp}
        for n in notifs
    ]
