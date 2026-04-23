# coding=utf-8
"""Event service — business logic for events, expenses, settlements, posts, and event users."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    File,
    Image,
    Post,
    Settlement,
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
class EventResult:
    """Outcome of an event create/update operation."""

    success: bool
    event: Event | None = None
    error: str | None = None


@dataclass
class EventUserResult:
    """Outcome of an event-user operation."""

    success: bool
    eventuser: EventUser | None = None
    error: str | None = None


@dataclass
class ExpenseResult:
    """Outcome of an expense operation."""

    success: bool
    expense: Expense | None = None
    error: str | None = None


@dataclass
class SettlementResult:
    """Outcome of a settlement operation."""

    success: bool
    settlement: Settlement | None = None
    error: str | None = None


@dataclass
class PostResult:
    """Outcome of a post creation."""

    success: bool
    post: Post | None = None
    error: str | None = None


@dataclass
class BalanceResult:
    """Balance calculation result."""

    draft_settlements: list[Any] = field(default_factory=list)
    balances_str: list[Any] = field(default_factory=list)
    total_expenses_str: list[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cookie-based session helpers
# ---------------------------------------------------------------------------

def session_can_edit(cookie_eventuser_guid: str | None, event: Event, author: EventUser, current_user: Any) -> bool:
    """Check if the session grants edit permission for *author*.

    The *cookie_eventuser_guid* should be read from ``request.cookies``
    by the caller.  Returns ``True`` if the cookie-identified event user
    matches *author*, or the current user has admin rights on the event.
    """
    if cookie_eventuser_guid is None:
        return event.can_edit(current_user)
    eventuser_cookie = EventUser.get_by_guid_or_404(cookie_eventuser_guid)
    return (author == eventuser_cookie) or event.can_edit(current_user)


def get_eventuser_from_cookie(event: Event, cookie_eventuser_guid: str | None) -> EventUser | None:
    """Retrieve the ``EventUser`` identified by a cookie value for *event*.

    Returns ``None`` if no cookie value is provided or the user is not
    part of the event.
    """
    if cookie_eventuser_guid is None:
        return None
    eventuser = EventUser.get_by_guid_or_404(cookie_eventuser_guid)
    if eventuser not in event.users:
        return None
    return eventuser


def resolve_eventuser(event: Event, cookie_eventuser_guid: str | None, current_user: Any) -> EventUser | None:
    """Resolve an EventUser for API requests.

    Tries the cookie first, then falls back to matching via the
    ``user_id`` FK if the caller is an authenticated :class:`User`.
    """
    # Try cookie-based resolution first
    eu = get_eventuser_from_cookie(event, cookie_eventuser_guid)
    if eu:
        return eu

    # Fall back to user_id FK
    if current_user and hasattr(current_user, 'id') and current_user.is_authenticated:
        eu = EventUser.query.filter_by(event_id=event.id, user_id=current_user.id).first()
        return eu

    return None


# ---------------------------------------------------------------------------
# Event listing
# ---------------------------------------------------------------------------

def list_events(
    user: Any,
    is_admin: bool,
    page: int,
    per_page: int | None = None,
) -> PaginatedResult:
    """Return a paginated list of events for *user*."""
    if per_page is None:
        per_page = current_app.config['ITEMS_PER_PAGE']

    if is_admin:
        pagination = Event.query.order_by(Event.closed.asc(), Event.date.desc()).paginate(
            page=page, per_page=per_page, error_out=False,
        )
    else:
        pagination = user.events_admin.order_by(Event.closed.asc(), Event.date.desc()).paginate(
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


# ---------------------------------------------------------------------------
# Event CRUD
# ---------------------------------------------------------------------------

def get_event(guid: str) -> Event:
    """Retrieve an event by GUID or raise 404."""
    return Event.get_by_guid_or_404(guid)


def create_event(
    name: str,
    date: datetime,
    admin: User,
    base_currency_id: int,
    currency_ids: list[int],
    exchange_fee: float,
    fileshare_link: str,
    description: str,
    created_by: str,
) -> EventResult:
    """Create a new event with its admin as the first EventUser."""
    base_currency = db.session.get(Currency, base_currency_id)
    currencies = [db.session.get(Currency, cid) for cid in currency_ids]
    event = Event(
        name=name,
        date=date,
        admin=admin,
        base_currency=base_currency,
        currencies=currencies,
        exchange_fee=exchange_fee,
        closed=False,
        fileshare_link=fileshare_link,
        description=description,
        db_created_by=created_by,
    )
    eventuser = EventUser(
        username=admin.username,
        email=admin.email,
        weighting=1.0,
        locale=admin.locale,
        about_me=admin.about_me,
        user_id=admin.id,
        db_created_by=created_by,
    )
    event.add_user(eventuser)
    event.add_currency(base_currency)
    db.session.add(event)
    db.session.commit()
    event.accountant = eventuser
    db.session.commit()
    return EventResult(success=True, event=event)


def update_event(
    guid: str,
    name: str,
    date: datetime,
    fileshare_link: str,
    description: str,
    base_currency_id: int,
    exchange_fee: float,
    accountant_id: int,
    currency_ids: list[int],
) -> EventResult:
    """Update an existing event's details and currencies."""
    event = Event.get_by_guid_or_404(guid)
    event.name = name
    event.date = date
    event.fileshare_link = fileshare_link
    event.description = description
    event.base_currency = db.session.get(Currency, base_currency_id)
    event.exchange_fee = exchange_fee
    event.accountant = db.session.get(EventUser, accountant_id)

    # Add new currencies
    for currency_id in currency_ids:
        currency = db.session.get(Currency, currency_id)
        if currency not in event.currencies:
            event.currencies.append(currency)

    # Remove currencies no longer selected
    for currency in event.currencies:
        if currency.id not in currency_ids:
            eventcurrency = event.eventcurrencies.filter(EventCurrency.currency_id == currency.id).first()
            event.eventcurrencies.remove(eventcurrency)

    event.add_currency(event.base_currency)
    db.session.commit()
    return EventResult(success=True, event=event)


def update_event_picture(guid: str, file_stream: Any, filename: str) -> Image:
    """Upload or replace the event cover picture.

    Returns the newly created :class:`Image`.
    """
    event = Event.get_by_guid_or_404(guid)
    new_image = process_and_store_image(file_stream, filename)
    event.image = new_image
    db.session.commit()
    return new_image


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

def create_post(event_guid: str, body: str, author: EventUser) -> PostResult:
    """Create a new post on the event."""
    event = Event.get_by_guid_or_404(event_guid)
    post = Post(
        body=body,
        author=author,
        timestamp=datetime.now(timezone.utc),
        event=event,
    )
    db.session.add(post)
    db.session.commit()
    return PostResult(success=True, post=post)


def list_posts(event: Event, page: int, per_page: int | None = None) -> PaginatedResult:
    """Return a paginated list of posts for *event*."""
    if per_page is None:
        per_page = current_app.config['ITEMS_PER_PAGE']
    pagination = event.posts.order_by(Post.timestamp.desc()).paginate(
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


# ---------------------------------------------------------------------------
# Event currencies
# ---------------------------------------------------------------------------

def list_event_currencies(event: Event, page: int, per_page: int | None = None) -> PaginatedResult:
    """Return a paginated list of currencies for *event*."""
    if per_page is None:
        per_page = current_app.config['ITEMS_PER_PAGE']
    pagination = event.eventcurrencies.paginate(
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


def set_currency_rate(event_guid: str, currency_guid: str, rate: float) -> None:
    """Set the exchange rate for a currency within an event."""
    event = Event.get_by_guid_or_404(event_guid)
    currency = Currency.get_by_guid_or_404(currency_guid)
    eventcurrency = EventCurrency.query.filter_by(
        currency_id=currency.id, event_id=event.id,
    ).first_or_404()
    eventcurrency.inCHF = rate
    db.session.commit()


# ---------------------------------------------------------------------------
# Event users
# ---------------------------------------------------------------------------

def list_event_users(event: Event, page: int, per_page: int | None = None) -> PaginatedResult:
    """Return a paginated list of event users."""
    if per_page is None:
        per_page = current_app.config['ITEMS_PER_PAGE']
    pagination = event.users.order_by(EventUser.username.asc()).paginate(
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


def add_event_user(
    event: Event,
    username: str,
    email: str,
    weighting: float,
    locale: str,
    about_me: str = '',
    user_id: int | None = None,
) -> EventUserResult:
    """Add a new user to an event."""
    eventuser = EventUser(
        username=username,
        email=email,
        weighting=weighting,
        locale=locale,
        about_me=about_me,
        user_id=user_id,
    )
    event.add_user(eventuser)
    db.session.commit()
    return EventUserResult(success=True, eventuser=eventuser)


def readd_event_user(event: Event, user_guid: str) -> EventUserResult:
    """Re-add an existing event user back to the event."""
    eventuser = EventUser.get_by_guid_or_404(user_guid)
    event.add_user(eventuser)
    db.session.commit()
    return EventUserResult(success=True, eventuser=eventuser)


def remove_event_user(event: Event, user_guid: str) -> EventUserResult:
    """Remove a user from an event.

    Returns ``success=False`` if the user cannot be removed (e.g. has expenses).
    """
    eventuser = EventUser.get_by_guid_or_404(user_guid)
    if event.remove_user(eventuser):
        return EventUserResult(success=False, eventuser=eventuser, error='Cannot remove user')
    db.session.commit()
    return EventUserResult(success=True, eventuser=eventuser)


def update_event_user_profile(
    guid: str,
    username: str,
    email: str,
    weighting: float,
    about_me: str,
    locale: str,
) -> EventUserResult:
    """Update an event user's profile."""
    eventuser = EventUser.get_by_guid_or_404(guid)
    eventuser.username = username
    eventuser.email = email
    eventuser.weighting = weighting
    eventuser.about_me = about_me
    eventuser.locale = locale
    db.session.commit()
    return EventUserResult(success=True, eventuser=eventuser)


def update_event_user_bank_account(
    guid: str,
    iban: str,
    bank: str,
    name: str,
    address: str,
    address_suffix: str,
    zip_code: int,
    city: str,
    country: str,
) -> EventUserResult:
    """Update an event user's bank account details."""
    eventuser = EventUser.get_by_guid_or_404(guid)
    eventuser.iban = iban
    eventuser.bank = bank
    eventuser.name = name
    eventuser.address = address
    eventuser.address_suffix = address_suffix
    eventuser.zip_code = zip_code
    eventuser.city = city
    eventuser.country = country
    db.session.commit()
    return EventUserResult(success=True, eventuser=eventuser)


def update_event_user_picture(guid: str, file_stream: Any, filename: str) -> Image:
    """Upload or replace an event user's profile picture."""
    eventuser = EventUser.get_by_guid_or_404(guid)
    new_image = process_and_store_image(file_stream, filename)
    eventuser.profile_picture = new_image
    db.session.commit()
    return new_image


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------

def get_balance(event_guid: str) -> BalanceResult:
    """Calculate the event balance, including draft settlements."""
    event = Event.get_by_guid_or_404(event_guid)
    draft_settlements = event.calculate_balance()
    balances_str, total_expenses_str = event.get_balance()
    return BalanceResult(
        draft_settlements=draft_settlements,
        balances_str=balances_str,
        total_expenses_str=total_expenses_str,
    )


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

def list_expenses(
    event: Event,
    page: int,
    eventuser: EventUser | None = None,
    filter_own: bool = False,
    per_page: int | None = None,
) -> PaginatedResult:
    """Return a paginated list of expenses for *event*."""
    if per_page is None:
        per_page = current_app.config['ITEMS_PER_PAGE']
    filters = []
    if filter_own and eventuser:
        filters.append(Expense.user == eventuser)
    pagination = event.expenses.filter(*filters).order_by(Expense.date.desc()).paginate(
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


def create_expense(
    event: Event,
    eventuser: EventUser,
    currency_id: int,
    amount: float,
    affected_user_ids: list[int],
    date: datetime,
    description: str,
    created_by: str,
) -> ExpenseResult:
    """Create a new expense on an event."""
    expense = Expense(
        user=eventuser,
        event=event,
        currency=db.session.get(Currency, currency_id),
        amount=amount,
        affected_users=[db.session.get(EventUser, uid) for uid in affected_user_ids],
        date=date,
        description=description,
        db_created_by=created_by,
    )

    with db.session.no_autoflush:
        image = Image.query.join(File).filter(File.original_filename.like('expense%')).first()

    if image:
        expense.image = image
    db.session.add(expense)
    db.session.commit()
    return ExpenseResult(success=True, expense=expense)


def update_expense(
    guid: str,
    currency_id: int,
    amount: float,
    affected_user_ids: list[int],
    date: datetime,
    description: str,
) -> ExpenseResult:
    """Update an existing expense."""
    expense = Expense.get_by_guid_or_404(guid)
    expense.currency = db.session.get(Currency, currency_id)
    expense.amount = amount
    expense.affected_users = [db.session.get(EventUser, uid) for uid in affected_user_ids]
    expense.date = date
    expense.description = description
    db.session.commit()
    return ExpenseResult(success=True, expense=expense)


def remove_expense(guid: str) -> ExpenseResult:
    """Remove an expense from its event."""
    expense = Expense.get_by_guid_or_404(guid)
    event = expense.event
    amount_str = expense.get_amount_str()
    if expense in event.expenses:
        event.expenses.remove(expense)
        db.session.commit()
    return ExpenseResult(success=True, expense=expense)


def add_receipt(expense_guid: str, file_stream: Any, filename: str) -> Image:
    """Upload a receipt image for an expense."""
    expense = Expense.get_by_guid_or_404(expense_guid)
    new_image = process_and_store_image(file_stream, filename)
    expense.image = new_image
    db.session.commit()
    return new_image


# ---------------------------------------------------------------------------
# Expense users
# ---------------------------------------------------------------------------

def list_expense_users(
    expense: Expense,
    page: int,
    per_page: int | None = None,
) -> PaginatedResult:
    """Return a paginated list of users affected by *expense*."""
    if per_page is None:
        per_page = current_app.config['ITEMS_PER_PAGE']
    pagination = expense.affected_users.order_by(EventUser.username.asc()).paginate(
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


def add_expense_users(expense: Expense, user_ids: list[int]) -> list[EventUser]:
    """Add users to an expense's affected list."""
    users = [db.session.get(EventUser, uid) for uid in user_ids]
    expense.add_users(users)
    db.session.commit()
    return users


def add_expense_user(expense_guid: str, user_guid: str) -> EventUser:
    """Add a single user to an expense's affected list."""
    expense = Expense.get_by_guid_or_404(expense_guid)
    user = EventUser.get_by_guid_or_404(user_guid)
    expense.add_user(user)
    db.session.commit()
    return user


def remove_expense_user(expense_guid: str, user_guid: str) -> EventUserResult:
    """Remove a user from an expense's affected list.

    Returns ``success=False`` if the user cannot be removed.
    """
    expense = Expense.get_by_guid_or_404(expense_guid)
    user = EventUser.get_by_guid_or_404(user_guid)
    if expense.remove_user(user):
        return EventUserResult(success=False, eventuser=user, error='Cannot remove user')
    db.session.commit()
    return EventUserResult(success=True, eventuser=user)


# ---------------------------------------------------------------------------
# Settlements
# ---------------------------------------------------------------------------

def list_settlements(
    event: Event,
    page: int,
    draft: bool = False,
    per_page: int | None = None,
) -> PaginatedResult:
    """Return a paginated list of settlements for *event*."""
    if per_page is None:
        per_page = current_app.config['ITEMS_PER_PAGE']
    pagination = event.settlements.filter_by(draft=draft).order_by(
        Settlement.date.desc(),
    ).paginate(page=page, per_page=per_page, error_out=False)
    return PaginatedResult(
        items=pagination.items,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev,
        next_num=pagination.next_num,
        prev_num=pagination.prev_num,
        total=pagination.total,
    )


def create_settlement(
    event: Event,
    sender: EventUser,
    recipient_id: int,
    currency_id: int,
    amount: float,
    description: str,
    created_by: str,
    draft: bool = False,
) -> SettlementResult:
    """Create a new settlement on an event."""
    settlement = Settlement(
        sender=sender,
        recipient=db.session.get(EventUser, recipient_id),
        event=event,
        currency=db.session.get(Currency, currency_id),
        amount=amount,
        draft=draft,
        date=datetime.now(timezone.utc),
        description=description,
        db_created_by=created_by,
    )

    with db.session.no_autoflush:
        image = Image.query.join(File).filter(File.original_filename.like('settlement%')).first()

    if image:
        settlement.image = image
    db.session.add(settlement)
    db.session.commit()
    return SettlementResult(success=True, settlement=settlement)


def update_settlement(
    guid: str,
    currency_id: int,
    amount: float,
    recipient_id: int,
    description: str,
) -> SettlementResult:
    """Update an existing settlement."""
    settlement = Settlement.get_by_guid_or_404(guid)
    settlement.currency = db.session.get(Currency, currency_id)
    settlement.amount = amount
    settlement.recipient = db.session.get(EventUser, recipient_id)
    settlement.description = description
    db.session.commit()
    return SettlementResult(success=True, settlement=settlement)


def execute_draft_settlement(guid: str, confirming_username: str) -> SettlementResult:
    """Confirm a draft settlement (mark it as non-draft)."""
    from flask_babel import _

    settlement = Settlement.get_by_guid_or_404(guid)
    settlement.draft = False
    settlement.description = _('Confirmed by user %(username)s', username=confirming_username)
    db.session.commit()
    return SettlementResult(success=True, settlement=settlement)


def remove_settlement(guid: str) -> SettlementResult:
    """Remove a settlement from its event."""
    settlement = Settlement.get_by_guid_or_404(guid)
    event = settlement.event
    if settlement in event.settlements:
        event.settlements.remove(settlement)
        db.session.commit()
    return SettlementResult(success=True, settlement=settlement)


# ---------------------------------------------------------------------------
# Event lifecycle
# ---------------------------------------------------------------------------

def convert_currencies(event_guid: str) -> Event:
    """Convert all event transactions to the base currency."""
    event = Event.get_by_guid_or_404(event_guid)
    event.convert_currencies()
    db.session.commit()
    return event


def close_event(event_guid: str) -> EventResult:
    """Close an event if no open liabilities remain."""
    event = Event.get_by_guid_or_404(event_guid)
    if event.settlements.filter_by(draft=True).all():
        return EventResult(success=False, event=event, error='Event has open liabilities')
    event.closed = True
    db.session.commit()
    return EventResult(success=True, event=event)


def reopen_event(event_guid: str) -> EventResult:
    """Reopen a closed event."""
    event = Event.get_by_guid_or_404(event_guid)
    event.closed = False
    db.session.commit()
    return EventResult(success=True, event=event)


def send_payment_reminders(event_guid: str) -> None:
    """Launch a background task to send payment reminder emails."""
    from flask_babel import _

    event = Event.get_by_guid_or_404(event_guid)
    event.admin.launch_task('send_reminders', _('Sending balance reports...'), event_guid=event_guid)
    db.session.commit()


def request_balance_pdf(event_guid: str, eventuser_guid: str | None) -> None:
    """Launch a background task to send a balance report email."""
    from flask_babel import _

    event = Event.get_by_guid_or_404(event_guid)
    event.admin.launch_task(
        'request_balance',
        _('Sending balance reports...'),
        event_guid=event_guid,
        eventuser_guid=eventuser_guid,
    )
    db.session.commit()
