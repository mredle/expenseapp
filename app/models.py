"""SQLAlchemy models for the ExpenseApp application.

Defines all database entities including users, events, expenses,
settlements, media, authentication credentials, and supporting types.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from hashlib import md5
from time import time
from typing import Any

import jwt
import redis
import rq
from flask import current_app, url_for
from flask_babel import _
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import validates
from sqlalchemy.types import CHAR, String, TypeDecorator
from sqlalchemy_utils.types.uuid import UUIDType
from webauthn.helpers.structs import AuthenticatorTransport
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login
from app.storage import get_storage_provider


# ---------------------------------------------------------------------------
# Custom SQLAlchemy column types
# ---------------------------------------------------------------------------

class FIDO2Transports(TypeDecorator):
    """Store a list of :class:`AuthenticatorTransport` enums as a comma-separated string."""

    impl = String(64)

    def process_bind_param(self, value: list[str] | None, dialect: Any) -> str | None:
        if value is None:
            return value
        if not isinstance(value, list):
            raise TypeError("FIDO2Transports columns support only list values.")
        return ','.join(value)

    def process_result_value(self, value: str | None, dialect: Any) -> list[AuthenticatorTransport] | None:
        return [AuthenticatorTransport(x) for x in value.split(',')] if value else None


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's native UUID type when available, otherwise stores
    as CHAR(32) hex strings.
    """

    impl = CHAR
    cache_ok = True

    def __repr__(self) -> str:
        return self.impl.__repr__()

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value: uuid.UUID | str | None, dialect: Any) -> str | None:
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return str(value)
        if not isinstance(value, uuid.UUID):
            return f"{uuid.UUID(value).int:032x}"
        return f"{value.int:032x}"

    def process_result_value(self, value: str | uuid.UUID | None, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value


# ---------------------------------------------------------------------------
# Mixin classes
# ---------------------------------------------------------------------------

class PaginatedAPIMixin:
    """Mixin providing paginated collection serialisation for REST APIs."""

    @staticmethod
    def to_collection_dict(query: Any, page: int, per_page: int, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Return a paginated dict with ``items``, ``_meta`` and ``_links``."""
        resources = query.paginate(page=page, per_page=per_page, error_out=False)
        data: dict[str, Any] = {
            'items': [item.to_dict() for item in resources.items],
            '_meta': {
                'page': page,
                'per_page': per_page,
                'total_pages': resources.pages,
                'total_items': resources.total,
            },
            '_links': {
                'self': url_for(endpoint, page=page, per_page=per_page, **kwargs),
                'next': url_for(endpoint, page=page + 1, per_page=per_page,
                                **kwargs) if resources.has_next else None,
                'prev': url_for(endpoint, page=page - 1, per_page=per_page,
                                **kwargs) if resources.has_prev else None,
            },
        }
        return data


class Entity:
    """Base mixin providing audit columns and GUID lookup for all domain models."""

    db_created_at = db.Column(db.DateTime)
    db_updated_at = db.Column(db.DateTime)
    db_created_by = db.Column(db.String(64))
    db_updated_by = db.Column(db.String(64))
    guid = db.Column(UUIDType(binary=False), default=uuid.uuid4, index=True, unique=True)

    def __init__(self, db_created_by: str = 'SYSTEM') -> None:
        self.db_created_at = datetime.now(timezone.utc)
        self.db_updated_at = datetime.now(timezone.utc)
        self.db_created_by = db_created_by
        self.db_updated_by = db_created_by

    @classmethod
    def get_by_guid_or_404(cls, guid: uuid.UUID | str) -> Any:
        """Look up a record by its GUID or abort with 404."""
        return cls.query.filter(cls.guid == guid).first_or_404()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Log(db.Model):
    """Structured application log stored in the database."""

    __tablename__ = 'log'
    id = db.Column(db.Integer, db.Identity(), primary_key=True)

    severity = db.Column(db.String(32))
    module = db.Column(db.String(128))
    msg_type = db.Column(db.String(128))
    msg = db.Column(db.String(256))
    trace = db.Column(db.String(4096))
    date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User', back_populates='logs')

    def __init__(self, severity: str, module: str, msg_type: str, msg: str,
                 user: User, trace: str | None = None) -> None:
        self.severity = severity
        self.module = module
        self.msg_type = msg_type
        self.msg = msg
        self.trace = trace
        self.user = user

    def __repr__(self) -> str:
        username = self.user.username if self.user else 'unknown'
        return f'<{self.severity} log from {username} at {self.date}: {self.msg}>'

    def can_view(self, user: User) -> bool:
        """Return whether *user* is allowed to view this log entry."""
        return (user.is_admin or user == self.user) if user.is_authenticated else False

    @classmethod
    def get_class_stats(cls, user: User | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        description = _('Log entries')
        filters: list[Any] = []
        if not (user is None or user.is_admin):
            filters.append(cls.user == user)
        number = cls.query.filter(*filters).count()
        return [(description, number)]


class File(Entity, db.Model):
    """Metadata record for a file stored via :class:`~app.storage.StorageProvider`."""

    __tablename__ = 'files'
    id = db.Column(db.Integer, db.Identity(), primary_key=True)

    original_filename = db.Column(db.String(256))
    storage_backend = db.Column(db.String(32), default='local', index=True)
    storage_key = db.Column(db.String(512), unique=True, index=True)
    mime_type = db.Column(db.String(128))
    file_size = db.Column(db.Integer)
    file_hash = db.Column(db.String(128), index=True)
    hash_algorithm = db.Column(db.String(32), default='sha256')

    def __init__(self, original_filename: str, storage_backend: str, storage_key: str,
                 mime_type: str, file_size: int = 0, file_hash: str | None = None,
                 hash_algorithm: str = 'sha256', db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.original_filename = original_filename
        self.storage_backend = storage_backend
        self.storage_key = storage_key
        self.mime_type = mime_type
        self.file_size = file_size
        self.file_hash = file_hash
        self.hash_algorithm = hash_algorithm

    def __repr__(self) -> str:
        return f'<File {self.storage_key} on {self.storage_backend} (Hash: {self.file_hash})>'

    @classmethod
    def get_class_stats(cls, user: User | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        description = _('Files')
        number = cls.query.count()
        return [(description, number)]

    def get_provider(self) -> Any:
        """Return the appropriate :class:`~app.storage.StorageProvider` for this file."""
        return get_storage_provider(self.storage_backend)

    def get_url(self) -> str:
        """Return the internal Flask route to securely serve this file."""
        return url_for('media.serve_file', file_id=self.id)

    def get_local_path(self) -> str:
        """Return the local filesystem path (useful for image processing)."""
        return self.get_provider().get_local_path(self.storage_key)

    def delete_from_storage(self) -> None:
        """Delete the actual file from the underlying storage backend."""
        self.get_provider().delete(self.storage_key)


class Thumbnail(Entity, db.Model):
    """A sized thumbnail variant of an :class:`Image`."""

    __tablename__ = 'thumbnails'
    id = db.Column(db.Integer, db.Identity(), primary_key=True)

    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), index=True)
    file = db.relationship('File')
    size = db.Column(db.Integer)
    format = db.Column(db.String(8))
    mode = db.Column(db.String(8))
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'), index=True)
    image = db.relationship('Image', foreign_keys=image_id, back_populates='thumbnails')

    def __init__(self, image: Image, size: int, file_obj: File,
                 db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.image = image
        self.size = size
        self.file = file_obj

    def __repr__(self) -> str:
        return f'<Thumbnail {self.size}x{self.size}px>'

    @classmethod
    def get_class_stats(cls, user: User | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        description = _('Thumbnails')
        number = cls.query.count()
        return [(description, number)]

    def get_url(self) -> str:
        """Proxy the URL request to the underlying :class:`File`."""
        if self.file:
            return self.file.get_url()
        return ''


class Image(Entity, db.Model):
    """An uploaded image with associated :class:`Thumbnail` variants."""

    __tablename__ = 'images'
    id = db.Column(db.Integer, db.Identity(), primary_key=True)

    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), index=True)
    file = db.relationship('File')
    is_vector = db.Column(db.Boolean)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    rotate = db.Column(db.Integer)
    format = db.Column(db.String(8))
    mode = db.Column(db.String(8))
    description = db.Column(db.String(256))
    thumbnails = db.relationship('Thumbnail', foreign_keys='Thumbnail.image_id',
                                 back_populates='image', lazy='dynamic')

    def __init__(self, file_obj: File, is_vector: bool = False, width: int = 0,
                 height: int = 0, format: str = '', mode: str = '',
                 description: str = '', db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.file = file_obj
        self.is_vector = is_vector
        self.width = width
        self.height = height
        self.format = format
        self.mode = mode
        self.rotate = 0
        self.description = description

    def __repr__(self) -> str:
        return f'<Image {self.width}x{self.height}px>'

    @classmethod
    def get_class_stats(cls, user: User | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        description = _('Images')
        number = cls.query.count()
        return [(description, number)]

    def rotate_image(self, degree: int) -> None:
        """Rotate the image by *degree* degrees (cumulative, mod 360)."""
        self.rotate = (self.rotate + degree) % 360

    def get_html_scale(self) -> float:
        """Return the CSS scale factor needed when the image is rotated."""
        if self.rotate in (90, 270) and self.width > self.height:
            return self.height / self.width
        elif self.rotate in (90, 270) and self.width < self.height:
            return self.width / self.height
        return 1.0

    def get_url(self) -> str:
        """Proxy the URL request to the underlying :class:`File`."""
        if self.file:
            return self.file.get_url()
        return ''

    def get_thumbnail(self, desired_size: int) -> Thumbnail | None:
        """Return the smallest thumbnail larger than *desired_size*, or ``None``."""
        thumbnails = self.thumbnails.order_by(Thumbnail.size.asc()).all()
        if not self.is_vector:
            for thumbnail in thumbnails:
                if thumbnail.size > desired_size:
                    return thumbnail
        return None

    def get_thumbnail_url(self, desired_size: int) -> str:
        """Return the URL for the best-matching thumbnail, falling back to the full image."""
        thumbnail = self.get_thumbnail(desired_size)
        if thumbnail:
            return thumbnail.get_url()
        return self.get_url()


class EventCurrency(db.Model):
    """Association between an :class:`Event` and a :class:`Currency` with a snapshot exchange rate."""

    __tablename__ = 'event_currencies'

    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), primary_key=True)
    event = db.relationship('Event', back_populates='eventcurrencies')
    currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'), primary_key=True)
    currency = db.relationship('Currency', back_populates='eventcurrencies')
    inCHF = db.Column(db.Float)

    def __init__(self, currency: Currency) -> None:
        self.currency = currency
        self.inCHF = currency.inCHF

    def __repr__(self) -> str:
        return f'<EventCurrency {self.currency.code}>'

    @classmethod
    def get_class_stats(cls, user: User | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        description = _('Event currencies')
        filters: list[Any] = []
        if not (user is None or user.is_admin):
            events = Event.query.filter(Event.admin == user).all()
            filters.append(cls.event_id.in_([e.id for e in events]))
        number = cls.query.filter(*filters).count()
        return [(description, number)]

    def get_amount_in(self, amount: float, eventcurrency: EventCurrency,
                      exchange_fee: float) -> float:
        """Convert *amount* from this currency into *eventcurrency*, applying *exchange_fee* %."""
        if self == eventcurrency:
            return amount
        return (1 + exchange_fee / 100) * amount * self.inCHF / eventcurrency.inCHF

    def get_amount_as_str(self, amount: float) -> str:
        """Format *amount* as a string with the correct decimal precision."""
        exponent = self.currency.exponent
        return f'{self.currency.code} {amount:.{exponent}f}'

    def get_amount_as_str_in(self, amount: float, eventcurrency: EventCurrency,
                             exchange_fee: float) -> str:
        """Format *amount* converted into *eventcurrency* as a string."""
        converted = self.get_amount_in(amount, eventcurrency, exchange_fee)
        exponent = eventcurrency.currency.exponent
        return f'{eventcurrency.currency.code} {converted:.{exponent}f}'


class Currency(Entity, db.Model):
    """A real-world currency with its exchange rate to CHF."""

    __tablename__ = 'currencies'
    id = db.Column(db.Integer, db.Identity(), primary_key=True)

    code = db.Column(db.String(3), index=True)
    name = db.Column(db.String(64))
    number = db.Column(db.Integer)
    exponent = db.Column(db.Integer)
    inCHF = db.Column(db.Float)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    image = db.relationship('Image', foreign_keys=image_id)
    source = db.Column(db.String(32))
    description = db.Column(db.String(256))
    expenses = db.relationship('Expense', back_populates='currency', lazy='dynamic')
    settlements = db.relationship('Settlement', back_populates='currency', lazy='dynamic')
    eventcurrencies = db.relationship('EventCurrency', back_populates='currency',
                                      lazy='dynamic', cascade='all, delete-orphan')
    events = association_proxy('eventcurrencies', 'event')
    events_base_currency = db.relationship('Event', foreign_keys='Event.base_currency_id',
                                           back_populates='base_currency', lazy='dynamic')

    def __init__(self, code: str, name: str, number: int, exponent: int,
                 inCHF: float, description: str = '', db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.code = code
        self.name = name
        self.number = number
        self.exponent = exponent
        self.inCHF = inCHF
        self.description = description

    def __repr__(self) -> str:
        return f'<Currency {self.code}>'

    @classmethod
    def get_class_stats(cls, user: User | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        description = _('Currencies')
        number = cls.query.count()
        return [(description, number)]

    def can_edit(self, user: User) -> bool:
        """Return whether *user* may edit this currency."""
        return user.is_admin

    def avatar(self, size: int) -> str:
        """Return the URL for this currency's flag thumbnail."""
        if self.image:
            return self.image.get_thumbnail_url(size)
        return ''


class Event(Entity, db.Model):
    """A shared-expense event grouping users, expenses and settlements."""

    __tablename__ = 'events'
    id = db.Column(db.Integer, db.Identity(), primary_key=True)

    name = db.Column(db.String(64))
    date = db.Column(db.DateTime, index=True, default=lambda: datetime.now(timezone.utc))
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    admin = db.relationship('User', foreign_keys=admin_id, back_populates='events_admin')
    accountant_id = db.Column(db.Integer, db.ForeignKey('eventusers.id'))
    accountant = db.relationship('EventUser', foreign_keys=accountant_id,
                                 back_populates='events_accountant')
    base_currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'))
    base_currency = db.relationship('Currency', foreign_keys=base_currency_id,
                                    back_populates='events_base_currency')
    base_eventcurrency = db.relationship(
        'EventCurrency',
        primaryjoin='and_(foreign(Event.id)==remote(EventCurrency.event_id), '
                    'foreign(Event.base_currency_id)==remote(EventCurrency.currency_id))',
        viewonly=True,
    )
    exchange_fee = db.Column(db.Float)
    users = db.relationship('EventUser', foreign_keys='EventUser.event_id',
                            back_populates='event', lazy='dynamic')
    eventcurrencies = db.relationship('EventCurrency', back_populates='event',
                                      lazy='dynamic', cascade='all, delete-orphan')
    currencies = association_proxy('eventcurrencies', 'currency')
    closed = db.Column(db.Boolean)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    image = db.relationship('Image', foreign_keys=image_id)
    description = db.Column(db.String(256))
    fileshare_link = db.Column(db.String(256))
    expenses = db.relationship('Expense', back_populates='event', lazy='dynamic')
    settlements = db.relationship('Settlement', back_populates='event', lazy='dynamic')
    posts = db.relationship('Post', back_populates='event', lazy='dynamic')

    def __init__(self, name: str, date: datetime, admin: User, base_currency: Currency,
                 currencies: list[Currency], exchange_fee: float, fileshare_link: str,
                 closed: bool = False, description: str = '',
                 db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.name = name
        self.date = date
        self.admin = admin
        self.base_currency = base_currency
        self.eventcurrencies = [EventCurrency(c) for c in currencies]
        self.exchange_fee = exchange_fee
        self.closed = closed
        self.fileshare_link = fileshare_link
        self.description = description

    def __repr__(self) -> str:
        return f'<Event {self.name}>'

    @classmethod
    def get_class_stats(cls, user: User | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        description = _('Events')
        filters: list[Any] = []
        if not (user is None or user.is_admin):
            filters.append(cls.admin == user)
        number = cls.query.filter(*filters).count()
        return [(description, number)]

    def can_edit(self, user: User) -> bool:
        """Return whether *user* may edit this event."""
        return (user.is_admin or user == self.admin) if user.is_authenticated else False

    def avatar(self, size: int) -> str:
        """Return the URL for this event's thumbnail."""
        if self.image:
            return self.image.get_thumbnail_url(size)
        return ''

    def get_stats(self) -> dict[str, int]:
        """Return counts of users, posts, expenses and confirmed settlements."""
        return {
            'users': self.users.count(),
            'posts': self.posts.count(),
            'expenses': self.expenses.count(),
            'settlements': self.settlements.filter_by(draft=False).count(),
        }

    def has_user(self, user: EventUser) -> bool:
        """Return whether *user* is a participant in this event."""
        return user in self.users

    def add_user(self, user: EventUser) -> None:
        """Add *user* to this event if not already present."""
        if not self.has_user(user):
            self.users.append(user)

    def remove_user(self, user: EventUser) -> int:
        """Remove *user* from this event. Returns 0 on success, 1 if blocked."""
        blocked_users = set(
            [x.user for x in self.expenses]
            + [x.sender for x in self.settlements]
            + [x.recipient for x in self.settlements]
        )
        if self.has_user(user) and user not in blocked_users:
            self.users.remove(user)
            return 0
        return 1

    def has_currency(self, currency: Currency) -> bool:
        """Return whether *currency* is assigned to this event."""
        return currency in self.currencies

    def add_currency(self, currency: Currency) -> None:
        """Add *currency* to this event if not already present."""
        if not self.has_currency(currency):
            self.currencies.append(currency)

    def remove_currency(self, currency: Currency) -> int:
        """Remove *currency* from this event. Returns 0 on success, 1 if blocked."""
        blocked_currencies = set(
            [x.currency for x in self.expenses]
            + [x.currency for x in self.settlements]
            + [self.base_currency]
        )
        if self.has_currency(currency) and currency not in blocked_currencies:
            self.currencies.remove(currency)
            return 0
        return 1

    def convert_currencies_to_base(self) -> None:
        """Convert all expenses and settlements to the base currency in-place."""
        with db.session.no_autoflush:
            expenses = self.expenses.all()
            settlements = self.settlements.all()

        for x in expenses:
            x.amount = x.eventcurrency.get_amount_in(
                x.amount, self.base_eventcurrency, self.exchange_fee)
            x.currency = self.base_currency

        for x in settlements:
            x.amount = x.eventcurrency.get_amount_in(
                x.amount, self.base_eventcurrency, self.exchange_fee)
            x.currency = self.base_currency

    def get_currencies_str(self) -> str:
        """Return a comma-separated string of sorted currency codes."""
        currency_codes = sorted(c.code for c in self.currencies)
        return ', '.join(currency_codes)

    def get_total_expenses(self) -> float:
        """Return the total expenses converted to the base currency."""
        with db.session.no_autoflush:
            expenses = self.expenses.all()
        return sum(x.get_amount() for x in expenses)

    def get_amount_paid(self, user: EventUser) -> float:
        """Return the total amount *user* has paid."""
        with db.session.no_autoflush:
            expenses = self.expenses.filter_by(user=user).all()
        return sum(x.get_amount() for x in expenses)

    def get_amount_spent(self, user: EventUser) -> float:
        """Return the total amount attributable to *user* based on weighting."""
        with db.session.no_autoflush:
            expenses = self.expenses.all()
            return sum(
                user.weighting * x.get_amount() / sum(u.weighting for u in x.affected_users.all())
                for x in expenses if user in x.affected_users
            )

    def get_amount_sent(self, user: EventUser) -> float:
        """Return the total amount *user* has sent in confirmed settlements."""
        with db.session.no_autoflush:
            settlements = self.settlements.filter_by(sender=user, draft=False).all()
        return sum(x.get_amount() for x in settlements)

    def get_amount_received(self, user: EventUser) -> float:
        """Return the total amount *user* has received in confirmed settlements."""
        with db.session.no_autoflush:
            settlements = self.settlements.filter_by(recipient=user, draft=False).all()
        return sum(x.get_amount() for x in settlements)

    def get_user_balance(self, user: EventUser) -> tuple[EventUser, float, float, float, float, float]:
        """Return *(user, paid, spent, sent, received, balance)* for *user*."""
        amount_paid = self.get_amount_paid(user)
        amount_spent = self.get_amount_spent(user)
        amount_sent = self.get_amount_sent(user)
        amount_received = self.get_amount_received(user)
        balance = amount_paid - amount_spent + amount_sent - amount_received
        return (user, amount_paid, amount_spent, amount_sent, amount_received, balance)

    def get_compensation_settlements_accountant(self) -> list[Settlement]:
        """Generate draft settlements that zero out all balances via the accountant."""
        with db.session.no_autoflush:
            users = [u for u in self.users if u != self.accountant]
        settlements: list[Settlement] = []
        tolerance = 10 ** -self.base_currency.exponent

        for user in users:
            balance_item = self.get_user_balance(user)
            balance = balance_item[5]
            if balance < -tolerance:
                settlements.append(Settlement(
                    sender=user, recipient=self.accountant, event=self,
                    currency=self.base_currency, amount=-balance, draft=True,
                    date=datetime.now(timezone.utc)))
            elif balance > tolerance:
                settlements.append(Settlement(
                    sender=self.accountant, recipient=user, event=self,
                    currency=self.base_currency, amount=balance, draft=True,
                    date=datetime.now(timezone.utc)))

        return settlements

    def calculate_balance(self) -> list[Settlement]:
        """Delete existing drafts and recalculate compensation settlements."""
        self.settlements.filter_by(draft=True).delete()
        draft_settlements = self.get_compensation_settlements_accountant()
        db.session.add_all(draft_settlements)
        db.session.commit()
        return draft_settlements

    def get_balance(self) -> tuple[list[Any], str]:
        """Return *(formatted_balances, total_expenses_str)*."""
        balances = [self.get_user_balance(u) for u in self.users]
        balances_str = [
            (
                x[0],
                self.base_eventcurrency.get_amount_as_str(x[1]),
                self.base_eventcurrency.get_amount_as_str(x[2]),
                self.base_eventcurrency.get_amount_as_str(x[3]),
                self.base_eventcurrency.get_amount_as_str(x[4]),
                self.base_eventcurrency.get_amount_as_str(x[5]),
            )
            for x in balances
        ]
        total_expenses = self.get_total_expenses()
        total_expenses_str = self.base_eventcurrency.get_amount_as_str(total_expenses)
        return (balances_str, total_expenses_str)


expense_affected_users = db.Table(
    'expense_affected_users',
    db.Column('expense_id', db.Integer, db.ForeignKey('expenses.id')),
    db.Column('user_id', db.Integer, db.ForeignKey('eventusers.id')),
    db.PrimaryKeyConstraint('expense_id', 'user_id'),
)


class Expense(Entity, db.Model):
    """A single expense within an :class:`Event`."""

    __tablename__ = 'expenses'
    id = db.Column(db.Integer, db.Identity(), primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('eventusers.id'), index=True)
    user = db.relationship('EventUser', back_populates='expenses')
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), index=True)
    event = db.relationship('Event', back_populates='expenses')
    currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'))
    currency = db.relationship('Currency', back_populates='expenses')
    eventcurrency = db.relationship(
        'EventCurrency',
        primaryjoin='and_(foreign(Expense.event_id)==remote(EventCurrency.event_id), '
                    'foreign(Expense.currency_id)==remote(EventCurrency.currency_id))',
        viewonly=True,
    )
    amount = db.Column(db.Float)
    affected_users = db.relationship('EventUser', secondary=expense_affected_users,
                                     back_populates='affected_by_expenses', lazy='dynamic')
    date = db.Column(db.DateTime, index=True)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    image = db.relationship('Image', foreign_keys=image_id)
    description = db.Column(db.String(256))

    def __init__(self, user: EventUser, event: Event, currency: Currency,
                 amount: float, affected_users: list[EventUser], date: datetime,
                 description: str = '', db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.user = user
        self.event = event
        self.currency = currency
        self.amount = amount
        self.affected_users = affected_users
        self.date = date
        self.description = description

    def __repr__(self) -> str:
        return f'<Expense {self.amount}{self.currency.code}>'

    @classmethod
    def get_class_stats(cls, user: EventUser | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        description = _('Expenses')
        filters: list[Any] = []
        if not (user is None or user.is_admin):
            filters.append(cls.user == user)
        number = cls.query.filter(*filters).count()
        return [(description, number)]

    def avatar(self, size: int) -> str:
        """Return the URL for this expense's receipt thumbnail."""
        if self.image:
            return self.image.get_thumbnail_url(size)
        return ''

    def can_edit(self, user: User, eventuser: EventUser | None) -> bool:
        """Return whether *user*/*eventuser* may edit this expense."""
        is_admin = user.is_authenticated and user == self.event.admin
        is_owner = eventuser is not None and eventuser == self.user and not self.event.closed
        return is_admin or is_owner

    def has_user(self, user: EventUser) -> bool:
        """Return whether *user* is among the affected users."""
        return user in self.affected_users

    def add_user(self, user: EventUser) -> None:
        """Add *user* to the affected users if not already present."""
        if not self.has_user(user):
            self.affected_users.append(user)

    def add_users(self, users: list[EventUser]) -> None:
        """Add multiple users to the affected users."""
        for user in users:
            self.add_user(user)

    def remove_user(self, user: EventUser) -> int:
        """Remove *user* from affected users. Returns 0 on success, 1 if not found."""
        if self.has_user(user):
            self.affected_users.remove(user)
            return 0
        return 1

    def get_amount(self) -> float:
        """Return the expense amount converted to the event's base currency."""
        return self.eventcurrency.get_amount_in(
            self.amount, self.event.base_eventcurrency, self.event.exchange_fee)

    def get_amount_str(self) -> str:
        """Return a formatted string of the amount, with conversion if applicable."""
        amount_str = self.eventcurrency.get_amount_as_str(self.amount)
        if self.currency == self.event.base_currency:
            return amount_str
        amount_str_in = self.eventcurrency.get_amount_as_str_in(
            self.amount, self.event.base_eventcurrency, self.event.exchange_fee)
        return f'{amount_str} ({amount_str_in})'


class Settlement(Entity, db.Model):
    """A payment settlement between two :class:`EventUser` participants."""

    __tablename__ = 'settlements'
    id = db.Column(db.Integer, db.Identity(), primary_key=True)

    sender_id = db.Column(db.Integer, db.ForeignKey('eventusers.id'), index=True)
    sender = db.relationship('EventUser', foreign_keys=sender_id,
                             back_populates='settlements_sender')
    recipient_id = db.Column(db.Integer, db.ForeignKey('eventusers.id'), index=True)
    recipient = db.relationship('EventUser', foreign_keys=recipient_id,
                                back_populates='settlements_recipient')
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), index=True)
    event = db.relationship('Event', back_populates='settlements')
    currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'))
    currency = db.relationship('Currency', back_populates='settlements')
    eventcurrency = db.relationship(
        'EventCurrency',
        primaryjoin='and_(foreign(Settlement.event_id)==remote(EventCurrency.event_id), '
                    'foreign(Settlement.currency_id)==remote(EventCurrency.currency_id))',
        viewonly=True,
    )
    amount = db.Column(db.Float)
    draft = db.Column(db.Boolean)
    date = db.Column(db.DateTime, index=True)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    image = db.relationship('Image', foreign_keys=image_id)
    description = db.Column(db.String(256))

    def __init__(self, sender: EventUser, recipient: EventUser, event: Event,
                 currency: Currency, amount: float, draft: bool, date: datetime,
                 description: str = '', db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.sender = sender
        self.recipient = recipient
        self.event = event
        self.currency = currency
        self.amount = amount
        self.draft = draft
        self.date = date
        self.description = description

    def __repr__(self) -> str:
        return f'<Settlement {self.amount}{self.currency.code}>'

    @classmethod
    def get_class_stats(cls, user: EventUser | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        filters: list[Any] = []
        if not (user is None or user.is_admin):
            filters.append(cls.sender == user)
        number_s = cls.query.filter(*filters).count()
        filters = []
        if not (user is None or user.is_admin):
            filters.append(cls.recipient == user)
        number_r = cls.query.filter(*filters).count()
        return [(_('Settlements as sender'), number_s), (_('Settlements as recipient'), number_r)]

    def avatar(self, size: int) -> str:
        """Return the URL for this settlement's receipt thumbnail."""
        if self.image:
            return self.image.get_thumbnail_url(size)
        return ''

    def can_edit(self, user: User, eventuser: EventUser | None) -> bool:
        """Return whether *user*/*eventuser* may edit this settlement."""
        is_admin = user.is_authenticated and user == self.event.admin
        is_recipient = eventuser is not None and eventuser == self.recipient and not self.event.closed
        return is_admin or is_recipient

    def get_amount(self) -> float:
        """Return the settlement amount converted to the event's base currency."""
        return self.eventcurrency.get_amount_in(
            self.amount, self.event.base_eventcurrency, self.event.exchange_fee)

    def get_amount_str(self) -> str:
        """Return a formatted string of the amount, with conversion if applicable."""
        amount_str = self.eventcurrency.get_amount_as_str(self.amount)
        if self.currency == self.event.base_currency:
            return amount_str
        amount_str_in = self.eventcurrency.get_amount_as_str_in(
            self.amount, self.event.base_eventcurrency, self.event.exchange_fee)
        return f'{amount_str} ({amount_str_in})'


class Post(Entity, db.Model):
    """A text post / comment within an :class:`Event`."""

    __tablename__ = 'posts'
    id = db.Column(db.Integer, db.Identity(), primary_key=True)

    body = db.Column(db.String(256))
    timestamp = db.Column(db.DateTime, index=True, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('eventusers.id'), index=True)
    author = db.relationship('EventUser', back_populates='posts')
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), index=True)
    event = db.relationship('Event', back_populates='posts')

    def __init__(self, body: str, timestamp: datetime, author: EventUser,
                 event: Event, db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.body = body
        self.timestamp = timestamp
        self.author = author
        self.event = event

    def __repr__(self) -> str:
        return f'<Post {self.body}>'

    @classmethod
    def get_class_stats(cls, user: EventUser | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        description = _('Posts')
        filters: list[Any] = []
        if not (user is None or user.is_admin):
            filters.append(cls.author == user)
        number = cls.query.filter(*filters).count()
        return [(description, number)]


class Message(Entity, db.Model):
    """A private message between two :class:`User` accounts."""

    __tablename__ = 'messages'
    id = db.Column(db.Integer, db.Identity(), primary_key=True)

    body = db.Column(db.String(256))
    timestamp = db.Column(db.DateTime, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    author = db.relationship('User', foreign_keys=sender_id, back_populates='messages_sent')
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    recipient = db.relationship('User', foreign_keys=recipient_id,
                                back_populates='messages_received')

    def __init__(self, body: str, author: User, recipient: User,
                 db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.body = body
        self.timestamp = datetime.now(timezone.utc)
        self.author = author
        self.recipient = recipient

    def __repr__(self) -> str:
        return f'<Message {self.body}>'

    @classmethod
    def get_class_stats(cls, user: User | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        filters: list[Any] = []
        if not (user is None or user.is_admin):
            filters.append(cls.author == user)
        number_s = cls.query.filter(*filters).count()
        filters = []
        if not (user is None or user.is_admin):
            filters.append(cls.recipient == user)
        number_r = cls.query.filter(*filters).count()
        return [(_('Messages sent'), number_s), (_('Messages received'), number_r)]


class Notification(Entity, db.Model):
    """A user notification with a JSON payload."""

    __tablename__ = 'notifications'
    id = db.Column(db.Integer, db.Identity(), primary_key=True)

    name = db.Column(db.String(128), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User', back_populates='notifications')
    timestamp = db.Column(db.Float, index=True)
    payload_json = db.Column(db.Text)

    def __init__(self, name: str, user: User, payload_json: str,
                 db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.name = name
        self.user = user
        self.timestamp = datetime.now(timezone.utc).timestamp()
        self.payload_json = payload_json

    def __repr__(self) -> str:
        return f'<Notification {self.name}>'

    @classmethod
    def get_class_stats(cls, user: User | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        description = _('Notifications')
        filters: list[Any] = []
        if not (user is None or user.is_admin):
            filters.append(cls.user == user)
        number = cls.query.filter(*filters).count()
        return [(description, number)]

    def get_data(self) -> Any:
        """Deserialise the JSON payload."""
        return json.loads(str(self.payload_json))


class Task(Entity, db.Model):
    """An RQ background task linked to a :class:`User`."""

    __tablename__ = 'tasks'
    id = db.Column(db.String(36), primary_key=True)

    name = db.Column(db.String(128), index=True)
    description = db.Column(db.String(128))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User', back_populates='tasks')
    complete = db.Column(db.Boolean, default=False)

    def __init__(self, id: str, name: str, description: str, user: User,
                 complete: bool = False, db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.id = id
        self.name = name
        self.description = description
        self.user = user
        self.complete = complete

    def __repr__(self) -> str:
        status = 'Done' if self.complete else 'Unfinished'
        username = self.user.username if self.user else 'unknown'
        return f'<Task {self.id} from {username}: {status}>'

    @classmethod
    def get_class_stats(cls, user: User | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        description = _('Tasks')
        filters: list[Any] = []
        if not (user is None or user.is_admin):
            filters.append(cls.user == user)
        number = cls.query.filter(*filters).count()
        return [(description, number)]

    def can_edit(self, user: User) -> bool:
        """Return whether *user* may edit this task."""
        return not self.complete and ((user.is_admin or user == self.user) if user.is_authenticated else False)

    def get_rq_job(self) -> rq.job.Job | None:
        """Fetch the RQ job object from Redis, or ``None`` if unavailable."""
        try:
            rq_job = rq.job.Job.fetch(self.id, connection=current_app.redis)
        except (redis.exceptions.RedisError, rq.exceptions.NoSuchJobError):
            return None
        return rq_job

    def get_progress(self) -> int:
        """Return the current progress percentage (0–100)."""
        job = self.get_rq_job()
        return job.meta.get('progress', 0) if job is not None else 100


class Credential(Entity, db.Model):
    """A WebAuthn/FIDO2 credential registered by a :class:`User`."""

    __tablename__ = 'credential'
    pk = db.Column(db.Integer, db.Identity(), primary_key=True)
    id = db.Column(db.LargeBinary)
    public_key = db.Column(db.LargeBinary)
    sign_count = db.Column(db.Integer)
    transports = db.Column(FIDO2Transports)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    user = db.relationship('User', back_populates='credentials')

    def __init__(self, id: bytes, public_key: bytes, sign_count: int,
                 transports: list[str], user: User,
                 db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.id = id
        self.public_key = public_key
        self.sign_count = sign_count
        self.transports = transports
        self.user = user

    def __repr__(self) -> str:
        return f'<Credential: {self.id}>'


class Challenge(Entity, db.Model):
    """A WebAuthn challenge associated with a :class:`User`."""

    __tablename__ = 'challenge'
    pk = db.Column(db.Integer, db.Identity(), primary_key=True)
    challenge = db.Column(db.LargeBinary)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    user = db.relationship('User', back_populates='challenges')

    def __init__(self, challenge: bytes) -> None:
        Entity.__init__(self)
        self.challenge = challenge

    def __repr__(self) -> str:
        return f'<Challenge: {self.challenge}>'


class User(PaginatedAPIMixin, UserMixin, Entity, db.Model):
    """A registered application user."""

    __tablename__ = 'users'
    id = db.Column(db.Integer, db.Identity(), primary_key=True)

    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(128), index=True, unique=True)
    locale = db.Column(db.String(32))
    password_hash = db.Column(db.String(256))
    token = db.Column(db.String(32), index=True, unique=True)
    token_expiration = db.Column(db.DateTime)
    profile_picture_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    profile_picture = db.relationship('Image', foreign_keys=profile_picture_id)
    events_admin = db.relationship('Event', foreign_keys='Event.admin_id',
                                   back_populates='admin', lazy='dynamic')
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id',
                                    back_populates='author', lazy='dynamic')
    messages_received = db.relationship('Message', foreign_keys='Message.recipient_id',
                                        back_populates='recipient', lazy='dynamic')
    last_message_read_time = db.Column(db.DateTime)
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic')
    tasks = db.relationship('Task', foreign_keys='Task.user_id',
                            back_populates='user', lazy='dynamic')
    logs = db.relationship('Log', foreign_keys='Log.user_id',
                           back_populates='user', lazy='dynamic')
    credentials = db.relationship('Credential', back_populates='user')
    challenges = db.relationship('Challenge', back_populates='user')

    is_admin = db.Column(db.Boolean)
    about_me = db.Column(db.String(256))
    last_seen = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @validates('email')
    def convert_lower(self, field: str, value: str) -> str:
        """Normalise e-mail addresses to lowercase on assignment."""
        if isinstance(value, str):
            return value.lower()
        return value

    def __init__(self, username: str, email: str, locale: str,
                 about_me: str = '', db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.username = username
        self.email = email
        self.locale = locale
        self.password_hash = ''
        self.token = uuid.uuid4().hex
        self.token_expiration = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.last_message_read_time = datetime.now(timezone.utc)
        self.is_admin = False
        self.about_me = about_me
        self.last_seen = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f'<User {self.username}>'

    @classmethod
    def get_class_stats(cls, user: User | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        description = _('Users')
        number = cls.query.count()
        return [(description, number)]

    def to_dict(self, include_email: bool = False) -> dict[str, Any]:
        """Serialise this user to a dictionary for the REST API."""
        eventusers = EventUser.query.filter_by(email=self.email).all()
        post_count = sum(eu.posts.count() for eu in eventusers)

        data: dict[str, Any] = {
            'id': self.id,
            'username': self.username,
            'last_seen': f'{self.last_seen.isoformat()}Z',
            'about_me': self.about_me,
            'post_count': post_count,
            '_links': {
                'self': url_for('apis.users_api_user', id=self.id),
                'avatar': self.avatar(128),
            },
        }
        if include_email:
            data['email'] = self.email
        return data

    def from_dict(self, data: dict[str, Any], new_user: bool = False) -> None:
        """Update this user from a dictionary (REST API input)."""
        for field in ['username', 'email', 'about_me']:
            if field in data:
                setattr(self, field, data[field])
        if new_user and 'password' in data:
            self.set_password(data['password'])

    def set_password(self, password: str) -> None:
        """Hash and store *password*."""
        self.password_hash = generate_password_hash(password)

    def set_random_password(self) -> None:
        """Generate and store a cryptographically random password."""
        password_tmp = base64.b64encode(os.urandom(24)).decode('utf-8')
        self.password_hash = generate_password_hash(password_tmp)

    def check_password(self, password: str) -> bool:
        """Verify *password* against the stored hash."""
        return check_password_hash(self.password_hash, password)

    def get_reset_password_token(self, expires_in: int = 600) -> str:
        """Return a JWT token for password reset."""
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            current_app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_reset_password_token(token: str) -> User | None:
        """Decode a password-reset JWT and return the corresponding user, or ``None``."""
        try:
            user_id = jwt.decode(token, current_app.config['SECRET_KEY'],
                                 algorithms=['HS256'])['reset_password']
        except Exception:
            return None
        return db.session.get(User, user_id)

    def avatar(self, size: int) -> str:
        """Return the URL for this user's avatar at *size* pixels."""
        if self.profile_picture:
            return self.profile_picture.get_thumbnail_url(size)
        return self.gravatar(size)

    def gravatar(self, size: int) -> str:
        """Return a Gravatar URL for this user's email."""
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'

    def new_messages(self) -> int:
        """Return the count of unread messages."""
        last_read_time = self.last_message_read_time or datetime(1900, 1, 1)
        return Message.query.filter_by(recipient=self).filter(
            Message.timestamp > last_read_time).count()

    def add_notification(self, name: str, data: Any) -> Notification:
        """Replace any existing notification with *name* and create a new one."""
        self.notifications.filter_by(name=name).delete()
        n = Notification(name=name, payload_json=json.dumps(data), user=self)
        db.session.add(n)
        return n

    def launch_task(self, name: str, description: str, *args: Any, **kwargs: Any) -> Task:
        """Enqueue a background task and record it in the database."""
        rq_job = current_app.task_queue.enqueue(f'app.tasks.{name}', self.guid,
                                                *args, **kwargs)
        task = Task(id=rq_job.id, name=name, description=description, user=self)
        db.session.add(task)
        return task

    def get_tasks_in_progress(self) -> list[Task]:
        """Return all incomplete tasks for this user."""
        return Task.query.filter_by(user=self, complete=False).all()

    def get_task_in_progress(self, name: str) -> Task | None:
        """Return the first incomplete task with *name*, or ``None``."""
        return Task.query.filter_by(name=name, user=self, complete=False).first()

    def get_token(self, expires_in: int = 3600) -> str:
        """Return the current API token, refreshing it if expired."""
        now = datetime.now(timezone.utc)

        # Attach UTC timezone if the database loaded a naive datetime.
        if self.token_expiration and self.token_expiration.tzinfo is None:
            self.token_expiration = self.token_expiration.replace(tzinfo=timezone.utc)

        if self.token and self.token_expiration and self.token_expiration > now + timedelta(seconds=60):
            return self.token

        self.token = uuid.uuid4().hex
        self.token_expiration = now + timedelta(seconds=expires_in)
        db.session.add(self)
        return self.token

    def revoke_token(self) -> None:
        """Immediately expire the current API token."""
        self.token_expiration = datetime.now(timezone.utc) - timedelta(seconds=1)

    @staticmethod
    def check_token(token: str) -> User | None:
        """Return the user for *token*, or ``None`` if invalid/expired."""
        user = User.query.filter_by(token=token).first()
        if user is None or user.token_expiration < datetime.now(timezone.utc):
            return None
        return user


class EventUser(Entity, db.Model):
    """A participant within a specific :class:`Event` (may or may not have a :class:`User` account)."""

    __tablename__ = 'eventusers'
    id = db.Column(db.Integer, db.Identity(), primary_key=True)

    # user data
    username = db.Column(db.String(64), index=True)
    email = db.Column(db.String(128), index=True)
    weighting = db.Column(db.Float)
    locale = db.Column(db.String(32))
    about_me = db.Column(db.String(256))

    # bank account data
    iban = db.Column(db.String(34))
    bank = db.Column(db.String(64))
    name = db.Column(db.String(64))
    address = db.Column(db.String(128))
    address_suffix = db.Column(db.String(128))
    zip_code = db.Column(db.Integer)
    city = db.Column(db.String(64))
    country = db.Column(db.String(64))

    # relationships
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), index=True)
    event = db.relationship('Event', foreign_keys=event_id, back_populates='users')
    events_accountant = db.relationship('Event', foreign_keys='Event.accountant_id',
                                        back_populates='accountant', lazy='dynamic')
    profile_picture_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    profile_picture = db.relationship('Image', foreign_keys=profile_picture_id)
    expenses = db.relationship('Expense', back_populates='user', lazy='dynamic')
    settlements_sender = db.relationship('Settlement', foreign_keys='Settlement.sender_id',
                                         back_populates='sender', lazy='dynamic')
    settlements_recipient = db.relationship('Settlement', foreign_keys='Settlement.recipient_id',
                                            back_populates='recipient', lazy='dynamic')
    affected_by_expenses = db.relationship('Expense', secondary=expense_affected_users,
                                           back_populates='affected_users', lazy='dynamic')
    posts = db.relationship('Post', back_populates='author', lazy='dynamic')

    @validates('email')
    def convert_lower(self, field: str, value: str) -> str:
        """Normalise e-mail addresses to lowercase on assignment."""
        if isinstance(value, str):
            return value.lower()
        return value

    def __init__(self, username: str, email: str, weighting: float,
                 locale: str, about_me: str = '',
                 db_created_by: str = 'SYSTEM') -> None:
        Entity.__init__(self, db_created_by)
        self.username = username
        self.email = email
        self.weighting = weighting
        self.locale = locale
        self.about_me = about_me

    def __repr__(self) -> str:
        return f'<EventUser {self.username}>'

    @classmethod
    def get_class_stats(cls, user: User | None = None) -> list[tuple[str, int]]:
        """Return aggregate statistics for the admin dashboard."""
        description = _('Event users')
        filters: list[Any] = []
        if not (user is None or user.is_admin):
            events = Event.query.filter(Event.admin == user).all()
            filters.append(cls.event_id.in_([e.id for e in events]))
        number = cls.query.filter(*filters).count()
        return [(description, number)]

    def avatar(self, size: int) -> str:
        """Return the URL for this participant's avatar at *size* pixels."""
        if self.profile_picture:
            return self.profile_picture.get_thumbnail_url(size)
        return self.gravatar(size)

    def gravatar(self, size: int) -> str:
        """Return a Gravatar URL for this participant's email."""
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'


@login.user_loader
def load_user(id: str) -> User | None:
    """Flask-Login callback to load a user by their primary key."""
    return db.session.get(User, int(id))
