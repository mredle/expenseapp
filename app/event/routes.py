# coding=utf-8
"""Event blueprint routes for managing events, expenses, settlements, and users."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app, flash, make_response, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app import db
from app.db_logging import log_page_access, log_page_access_denied
from app.event import bp
from app.event.forms import (
    BankAccountForm,
    EventEditForm,
    EventForm,
    EventUserForm,
    ExpenseAddUserForm,
    ExpenseForm,
    PostForm,
    SelectUserForm,
    SetRateForm,
    SettlementForm,
)
from app.main.forms import ImageForm
from app.models import Currency, Event, EventCurrency, EventUser, Expense, Settlement
from app.services.event_service import (
    add_event_user,
    add_expense_user,
    add_expense_users,
    close_event,
    convert_currencies,
    create_event,
    create_expense,
    create_post,
    create_settlement,
    execute_draft_settlement,
    get_balance,
    get_event,
    get_eventuser_from_cookie,
    list_event_currencies,
    list_event_users,
    list_events,
    list_expense_users,
    list_expenses,
    list_posts,
    list_settlements,
    readd_event_user,
    remove_event_user,
    remove_expense,
    remove_settlement,
    reopen_event,
    request_balance_pdf,
    send_payment_reminders,
    session_can_edit,
    set_currency_rate,
    update_event,
    update_event_picture,
    update_event_user_bank_account,
    update_event_user_picture,
    update_event_user_profile,
    update_expense,
    update_settlement,
)


def _cookie_guid(event: Event) -> str | None:
    """Read the eventuser GUID cookie for *event*."""
    return request.cookies.get(f'{event.guid}.eventuser')


def _can_edit(event: Event, author: EventUser) -> bool:
    """Shortcut to check session edit permission."""
    return session_can_edit(_cookie_guid(event), event, author, current_user)


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

@bp.route('/index')
@login_required
def index() -> str:
    """List all events the current user administers (or all events for admins)."""
    log_page_access(request, current_user)
    page = request.args.get('page', 1, type=int)
    result = list_events(current_user, current_user.is_admin, page)
    next_url = url_for('event.index', page=result.next_num) if result.has_next else None
    prev_url = url_for('event.index', page=result.prev_num) if result.has_prev else None

    return render_template(
        'event/index.html',
        title=_('Hi %(username)s, your events:', username=current_user.username),
        events=result.items,
        next_url=next_url,
        prev_url=prev_url,
    )


# ---------------------------------------------------------------------------
# Event user profile
# ---------------------------------------------------------------------------

@bp.route('/user/<guid>')
def user(guid: str) -> str:
    """Display an event user's profile."""
    log_page_access(request, current_user)
    eventuser = EventUser.get_by_guid_or_404(guid)

    return render_template(
        'event/user.html',
        title=_('User %(username)s', username=eventuser.username),
        eventuser=eventuser,
        can_edit=_can_edit(eventuser.event, eventuser),
    )


# ---------------------------------------------------------------------------
# Select user (cookie-based session)
# ---------------------------------------------------------------------------

@bp.route('/select_user/<event_guid>', methods=['GET', 'POST'])
def select_user(event_guid: str) -> str:
    """Let the visitor select which event user they are (stored in a cookie)."""
    event = get_event(event_guid)
    log_page_access(request, current_user)

    form = SelectUserForm()
    form.user_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        eventuser = db.session.get(EventUser, form.user_id.data)
        flash(_('You selected user %(username)s as context', username=eventuser.username))
        response = make_response(redirect(url_for('event.main', guid=event.guid)))
        response.set_cookie(
            key=f'{event_guid}.eventuser',
            value=str(eventuser.guid),
            max_age=31536000,
            httponly=True,
            samesite='Lax',
        )
        return response

    return render_template('edit_form.html', title=_('Select user'), form=form)


# ---------------------------------------------------------------------------
# Event main page
# ---------------------------------------------------------------------------

@bp.route('/main/<guid>', methods=['GET', 'POST'])
def main(guid: str) -> str:
    """Display the event main page with posts and stats."""
    event = get_event(guid)
    log_page_access(request, current_user)
    eventuser = get_eventuser_from_cookie(event, _cookie_guid(event))
    if eventuser is None:
        return redirect(url_for('event.select_user', event_guid=guid))

    form = PostForm()
    if form.validate_on_submit():
        create_post(guid, form.post.data, eventuser)
        flash(_('Your post is now live!'))
        return redirect(url_for('event.main', guid=guid))

    page = request.args.get('page', 1, type=int)
    posts_result = list_posts(event, page)
    next_url = url_for('event.main', guid=event.guid, page=posts_result.next_num) if posts_result.has_next else None
    prev_url = url_for('event.main', guid=event.guid, page=posts_result.prev_num) if posts_result.has_prev else None
    return render_template(
        'event/main.html',
        form=form,
        event=event,
        eventuser=eventuser,
        stats=event.get_stats(),
        posts=posts_result.items,
        next_url=next_url,
        prev_url=prev_url,
    )


# ---------------------------------------------------------------------------
# Currencies
# ---------------------------------------------------------------------------

@bp.route('/currencies/<guid>')
def currencies(guid: str) -> str:
    """List the allowed currencies for an event."""
    event = get_event(guid)
    log_page_access(request, current_user)
    page = request.args.get('page', 1, type=int)
    result = list_event_currencies(event, page)
    next_url = url_for('event.currencies', page=result.next_num) if result.has_next else None
    prev_url = url_for('event.currencies', page=result.prev_num) if result.has_prev else None
    return render_template(
        'event/eventcurrencies.html',
        title=_('Allowed currencies'),
        event=event,
        eventcurrencies=result.items,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route('/set_rate/<guid>/<currency_guid>', methods=['GET', 'POST'])
@login_required
def set_rate(guid: str, currency_guid: str) -> str:
    """Set the exchange rate for a currency within an event."""
    event = get_event(guid)
    currency = Currency.get_by_guid_or_404(currency_guid)
    eventcurrency = EventCurrency.query.filter_by(currency_id=currency.id, event_id=event.id).first_or_404()
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.currencies', guid=event.guid))
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))

    form = SetRateForm()
    if form.validate_on_submit():
        set_currency_rate(guid, currency_guid, form.inCHF.data)
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.currencies', guid=event.guid))
    elif request.method == 'GET':
        form.inCHF.data = eventcurrency.inCHF
    return render_template('edit_form.html', title=_('Set rate'), form=form)


# ---------------------------------------------------------------------------
# Create / edit event
# ---------------------------------------------------------------------------

@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new() -> str:
    """Create a new event."""
    log_page_access(request, current_user)
    form = EventForm()
    form.base_currency_id.choices = [(c.id, c.code) for c in Currency.query.order_by(Currency.code.asc())]
    form.currency_id.choices = form.base_currency_id.choices
    if form.validate_on_submit():
        result = create_event(
            name=form.name.data,
            date=form.date.data,
            admin=current_user,
            base_currency_id=form.base_currency_id.data,
            currency_ids=form.currency_id.data,
            exchange_fee=form.exchange_fee.data,
            fileshare_link=form.fileshare_link.data,
            description=form.description.data,
            created_by=current_user.username,
        )
        flash(_('Your new event has been added.'))
        return redirect(url_for('event.main', guid=result.event.guid))

    CHF = Currency.query.filter_by(code='CHF').first()
    form.base_currency_id.data = CHF.id
    form.currency_id.data = [CHF.id]
    form.date.data = datetime.now(timezone.utc)
    return render_template('edit_form.html', title=_('New Event'), form=form)


@bp.route('/edit/<guid>', methods=['GET', 'POST'])
@login_required
def edit(guid: str) -> str:
    """Edit an existing event's details and currencies."""
    event = get_event(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=event.guid))
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    form = EventEditForm()
    form.base_currency_id.choices = [(c.id, c.code) for c in event.currencies]
    form.currency_id.choices = [(c.id, c.code) for c in Currency.query.order_by(Currency.code.asc())]
    form.accountant_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        update_event(
            guid=guid,
            name=form.name.data,
            date=form.date.data,
            fileshare_link=form.fileshare_link.data,
            description=form.description.data,
            base_currency_id=form.base_currency_id.data,
            exchange_fee=form.exchange_fee.data,
            accountant_id=form.accountant_id.data,
            currency_ids=form.currency_id.data,
        )
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.main', guid=guid))
    elif request.method == 'GET':
        form.name.data = event.name
        form.date.data = event.date
        form.fileshare_link.data = event.fileshare_link
        form.description.data = event.description
        form.base_currency_id.data = event.base_currency_id
        form.currency_id.data = [c.id for c in event.currencies]
        form.exchange_fee.data = event.exchange_fee
        form.accountant_id.data = event.accountant_id
    return render_template('edit_form.html', title=_('Edit Event'), form=form)


@bp.route('/edit_picture/<guid>', methods=['GET', 'POST'])
@login_required
def edit_picture(guid: str) -> str:
    """Upload or replace the event cover picture."""
    event = get_event(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=event.guid))
    log_page_access(request, current_user)

    form = ImageForm()
    if form.validate_on_submit():
        if 'image' not in request.files or request.files['image'].filename == '':
            flash(_('Invalid or empty image.'))
            return redirect(url_for('event.main', guid=guid))

        file_obj = request.files['image']
        try:
            update_event_picture(guid, file_obj.stream, file_obj.filename)
            flash(_('Your changes have been saved.'))
        except Exception as e:
            current_app.logger.error(f"Failed to upload event picture: {e}")
            flash(_('An error occurred while uploading your image.'))

        return redirect(url_for('event.main', guid=guid))
    return render_template('edit_form.html', title=_('Event Picture'), form=form)


# ---------------------------------------------------------------------------
# Event users
# ---------------------------------------------------------------------------

@bp.route('/users/<guid>', methods=['GET', 'POST'])
def users(guid: str) -> str:
    """List event users and add new ones."""
    event = get_event(guid)
    log_page_access(request, current_user)
    form = EventUserForm()
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', guid=event.guid))
        add_event_user(
            event=event,
            username=form.username.data,
            email=form.email.data,
            weighting=form.weighting.data,
            locale=form.locale.data,
            about_me=form.about_me.data,
        )
        flash(_('User %(username)s has been added to event %(event_name)s.', username=form.username.data, event_name=event.name))
        return redirect(url_for('event.users', guid=guid))

    page = request.args.get('page', 1, type=int)
    result = list_event_users(event, page)
    next_url = url_for('event.users', guid=guid, page=result.next_num) if result.has_next else None
    prev_url = url_for('event.users', guid=guid, page=result.prev_num) if result.has_prev else None
    return render_template(
        'event/users.html',
        form=form,
        event=event,
        can_edit=event.can_edit(current_user),
        users=result.items,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route('/add_user/<guid>/<user_guid>')
@login_required
def add_user(guid: str, user_guid: str) -> str:
    """Add an existing event user back to the event."""
    event = get_event(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.users', guid=event.guid))
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('main.event', guid=event.guid))
    result = readd_event_user(event, user_guid)
    flash(_('User %(username)s has been added to event %(event_name)s.', username=result.eventuser.username, event_name=event.name))
    return redirect(url_for('event.users', guid=guid))


@bp.route('/remove_user/<guid>/<user_guid>')
@login_required
def remove_user(guid: str, user_guid: str) -> str:
    """Remove a user from the event."""
    event = get_event(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.users', guid=event.guid))
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    result = remove_event_user(event, user_guid)
    if not result.success:
        flash(_('User %(username)s cannot be removed from event %(event_name)s.', username=result.eventuser.username, event_name=event.name))
        return redirect(url_for('event.users', guid=guid))
    flash(_('User %(username)s has been removed from event %(event_name)s.', username=result.eventuser.username, event_name=event.name))
    return redirect(url_for('event.users', guid=guid))


@bp.route('/edit_profile/<guid>', methods=['GET', 'POST'])
def edit_profile(guid: str) -> str:
    """Edit an event user's profile details."""
    eventuser = EventUser.get_by_guid_or_404(guid)
    if not _can_edit(eventuser.event, eventuser):
        flash(_('Your are only allowed to edit your own user!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=eventuser.event.guid))
    log_page_access(request, current_user)

    form = EventUserForm()
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    if form.validate_on_submit():
        update_event_user_profile(
            guid=guid,
            username=form.username.data,
            email=form.email.data,
            weighting=form.weighting.data,
            about_me=form.about_me.data,
            locale=form.locale.data,
        )
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.user', guid=eventuser.guid))
    elif request.method == 'GET':
        form.username.data = eventuser.username
        form.email.data = eventuser.email
        form.weighting.data = eventuser.weighting
        form.about_me.data = eventuser.about_me
        form.locale.data = eventuser.locale
    return render_template('edit_form.html', title=_('Edit Profile'), form=form)


@bp.route('/edit_bank_account/<guid>', methods=['GET', 'POST'])
def edit_bank_account(guid: str) -> str:
    """Edit an event user's bank account details."""
    eventuser = EventUser.get_by_guid_or_404(guid)
    if not _can_edit(eventuser.event, eventuser):
        flash(_('Your are only allowed to edit your own user!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=eventuser.event.guid))
    log_page_access(request, current_user)

    form = BankAccountForm()
    if form.validate_on_submit():
        update_event_user_bank_account(
            guid=guid,
            iban=form.iban.data,
            bank=form.bank.data,
            name=form.name.data,
            address=form.address.data,
            address_suffix=form.address_suffix.data,
            zip_code=form.zip_code.data,
            city=form.city.data,
            country=form.country.data,
        )
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.user', guid=eventuser.guid))
    elif request.method == 'GET':
        form.iban.data = eventuser.iban
        form.bank.data = eventuser.bank
        form.name.data = eventuser.name
        form.address.data = eventuser.address
        form.address_suffix.data = eventuser.address_suffix
        form.zip_code.data = eventuser.zip_code
        form.city.data = eventuser.city
        form.country.data = eventuser.country
    return render_template('edit_form.html', title=_('Edit Bank Account'), form=form)


@bp.route('/edit_profile_picture/<guid>', methods=['GET', 'POST'])
def edit_profile_picture(guid: str) -> str:
    """Upload or replace an event user's profile picture."""
    eventuser = EventUser.get_by_guid_or_404(guid)
    if not _can_edit(eventuser.event, eventuser):
        flash(_('Your are only allowed to edit your own user!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=eventuser.event.guid))
    log_page_access(request, current_user)

    form = ImageForm()
    if form.validate_on_submit():
        if 'image' not in request.files or request.files['image'].filename == '':
            flash(_('Invalid or empty image.'))
            return redirect(url_for('event.user', guid=eventuser.guid))

        file_obj = request.files['image']
        try:
            update_event_user_picture(guid, file_obj.stream, file_obj.filename)
            flash(_('Your changes have been saved.'))
        except Exception as e:
            current_app.logger.error(f"Failed to upload user profile picture: {e}")
            flash(_('An error occurred while uploading your image.'))

        return redirect(url_for('event.user', guid=eventuser.guid))
    return render_template('edit_form.html', title=_('Profile Picture'), form=form)


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------

@bp.route('/balance/<guid>', methods=['GET'])
def balance(guid: str) -> str:
    """Display the event balance sheet and draft settlements."""
    event = get_event(guid)
    log_page_access(request, current_user)
    eventuser = get_eventuser_from_cookie(event, _cookie_guid(event))

    result = get_balance(guid)
    return render_template(
        'event/balance.html',
        event=event,
        eventuser=eventuser,
        draft_settlements=result.draft_settlements,
        balances_str=result.balances_str,
        total_expenses_str=result.total_expenses_str,
    )


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

@bp.route('/expenses/<guid>', methods=['GET', 'POST'])
def expenses(guid: str) -> str:
    """List expenses for an event and allow adding new ones."""
    event = get_event(guid)
    log_page_access(request, current_user)
    eventuser = get_eventuser_from_cookie(event, _cookie_guid(event))
    if eventuser is None:
        return redirect(url_for('event.select_user', event_guid=guid))

    form = ExpenseForm()
    form.currency_id.choices = [(c.id, c.code) for c in event.currencies]
    form.affected_users_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', guid=event.guid))
        create_expense(
            event=event,
            eventuser=eventuser,
            currency_id=form.currency_id.data,
            amount=form.amount.data,
            affected_user_ids=form.affected_users_id.data,
            date=form.date.data,
            description=form.description.data,
            created_by=current_user.username if current_user.is_authenticated else 'anonymous',
        )
        flash(_('Your new expense has been added to event %(event_name)s.', event_name=event.name))
        return redirect(url_for('event.expenses', guid=guid))

    form.currency_id.data = event.base_currency.id
    form.date.data = datetime.now(timezone.utc)
    form.affected_users_id.data = [u.id for u in event.users]
    page = request.args.get('page', 1, type=int)

    filter_eventuser = request.args.get('filter', '', type=str)
    filter_own = filter_eventuser.upper() == 'OWN'

    result = list_expenses(event, page, eventuser=eventuser, filter_own=filter_own)
    next_url = url_for('event.expenses', guid=event.guid, filter=filter_eventuser, page=result.next_num) if result.has_next else None
    prev_url = url_for('event.expenses', guid=event.guid, filter=filter_eventuser, page=result.prev_num) if result.has_prev else None
    return render_template(
        'event/expenses.html',
        form=form,
        event=event,
        eventuser=eventuser,
        expenses=result.items,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route('/add_receipt/<guid>', methods=['GET', 'POST'])
def add_receipt(guid: str) -> str:
    """Upload a receipt image for an expense."""
    expense = Expense.get_by_guid_or_404(guid)
    event = expense.event
    log_page_access(request, current_user)
    if expense.event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=expense.event.guid))
    if not _can_edit(event, expense.user):
        flash(_('Your are only allowed to edit your own expense!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.expenses', guid=expense.event.guid))

    form = ImageForm()
    if form.validate_on_submit():
        if 'image' not in request.files or request.files['image'].filename == '':
            flash(_('Invalid or empty image.'))
            return redirect(url_for('event.expenses', guid=expense.event.guid))

        file_obj = request.files['image']
        try:
            from app.services.event_service import add_receipt as svc_add_receipt
            svc_add_receipt(guid, file_obj.stream, file_obj.filename)
            flash(_('Your changes have been saved.'))
        except Exception as e:
            current_app.logger.error(f"Failed to upload receipt: {e}")
            flash(_('An error occurred while uploading your image.'))

        return redirect(url_for('event.expenses', guid=expense.event.guid))
    return render_template('edit_form.html', title=_('Add Receipt'), form=form)


@bp.route('/edit_expense/<guid>', methods=['GET', 'POST'])
def edit_expense(guid: str) -> str:
    """Edit an existing expense."""
    expense = Expense.get_by_guid_or_404(guid)
    event = expense.event
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    if not _can_edit(event, expense.user):
        flash(_('Your are only allowed to edit your own expense!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.expenses', guid=expense.event.guid))

    form = ExpenseForm()
    form.currency_id.choices = [(c.id, c.code) for c in event.currencies]
    form.affected_users_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        update_expense(
            guid=guid,
            currency_id=form.currency_id.data,
            amount=form.amount.data,
            affected_user_ids=form.affected_users_id.data,
            date=form.date.data,
            description=form.description.data,
        )
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.expenses', guid=event.guid))
    elif request.method == 'GET':
        form.currency_id.data = expense.currency.id
        form.amount.data = expense.amount
        form.affected_users_id.data = [u.id for u in expense.affected_users]
        form.date.data = expense.date
        form.description.data = expense.description
    return render_template('edit_form.html', title=_('Edit Expense'), form=form)


@bp.route('/remove_expense/<guid>')
def remove_expense_route(guid: str) -> str:
    """Remove an expense from an event."""
    expense = Expense.get_by_guid_or_404(guid)
    event = expense.event
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    if not _can_edit(event, expense.user):
        flash(_('Your are only allowed to edit your own expense!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.expenses', guid=expense.event.guid))

    amount_str = expense.get_amount_str()
    remove_expense(guid)
    flash(_('Expense over %(amount_str)s has been removed from event %(event_name)s.', amount_str=amount_str, event_name=event.name))
    return redirect(url_for('event.expenses', guid=event.guid))


@bp.route('/expense_users/<guid>', methods=['GET', 'POST'])
def expense_users(guid: str) -> str:
    """Manage the users affected by an expense."""
    expense = Expense.get_by_guid_or_404(guid)
    event = expense.event
    log_page_access(request, current_user)

    form = ExpenseAddUserForm()
    form.user_id.choices = [(u.id, u.username) for u in event.users.order_by(EventUser.username.asc()) if u not in expense.affected_users]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', guid=event.guid))
        if not _can_edit(event, expense.user):
            flash(_('Your are only allowed to edit your own expense!'))
            log_page_access_denied(request, current_user)
            return redirect(url_for('event.expenses', guid=expense.event.guid))

        added_users = add_expense_users(expense, form.user_id.data)
        flash(_('User %(username)s has been added to the expense.', username=' and '.join([u.username for u in added_users])))
        return redirect(url_for('event.expense_users', guid=guid))

    page = request.args.get('page', 1, type=int)
    result = list_expense_users(expense, page)
    next_url = url_for('event.expense_users', guid=guid, page=result.next_num) if result.has_next else None
    prev_url = url_for('event.expense_users', guid=guid, page=result.prev_num) if result.has_prev else None
    return render_template(
        'event/expense_users.html',
        form=form,
        expense=expense,
        can_edit=_can_edit(event, expense.user),
        users=result.items,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route('/expense_add_user/<guid>/<user_guid>')
def expense_add_user_route(guid: str, user_guid: str) -> str:
    """Add a single user to an expense's affected users list."""
    expense = Expense.get_by_guid_or_404(guid)
    event = expense.event
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    if not _can_edit(event, expense.user):
        flash(_('Your are only allowed to edit your own expense!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.expenses', guid=expense.event.guid))

    added_user = add_expense_user(guid, user_guid)
    flash(_('User %(username)s has been added to the expense.', username=added_user.username))
    return redirect(url_for('event.expense_users', guid=guid))


@bp.route('/expense_remove_user/<guid>/<user_guid>')
def expense_remove_user(guid: str, user_guid: str) -> str:
    """Remove a user from an expense's affected users list."""
    expense = Expense.get_by_guid_or_404(guid)
    event = expense.event
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    if not _can_edit(event, expense.user):
        flash(_('Your are only allowed to edit your own expense!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.expenses', guid=expense.event.guid))

    from app.services.event_service import remove_expense_user as svc_remove_expense_user
    result = svc_remove_expense_user(guid, user_guid)
    if not result.success:
        flash(_('User %(username)s cannot be removed from the expense.', username=result.eventuser.username))
        return redirect(url_for('event.expense_users', guid=guid))
    flash(_('User %(username)s has been removed from the expense.', username=result.eventuser.username))
    return redirect(url_for('event.expense_users', guid=guid))


# ---------------------------------------------------------------------------
# Settlements
# ---------------------------------------------------------------------------

@bp.route('/settlements/<guid>', methods=['GET', 'POST'])
def settlements(guid: str) -> str:
    """List settlements for an event and allow adding new ones."""
    event = get_event(guid)
    log_page_access(request, current_user)
    eventuser = get_eventuser_from_cookie(event, _cookie_guid(event))
    if eventuser is None:
        return redirect(url_for('event.select_user', event_guid=guid))

    form = SettlementForm()
    form.currency_id.choices = [(c.id, c.code) for c in event.currencies]
    form.recipient_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', guid=event.guid))
        create_settlement(
            event=event,
            sender=eventuser,
            recipient_id=form.recipient_id.data,
            currency_id=form.currency_id.data,
            amount=form.amount.data,
            description=form.description.data,
            created_by=current_user.username if current_user.is_authenticated else 'anonymous',
        )
        flash(_('Your new settlement has been added to event %(event_name)s.', event_name=event.name))
        return redirect(url_for('event.settlements', guid=guid))

    form.currency_id.data = event.base_currency.id
    page = request.args.get('page', 1, type=int)
    result = list_settlements(event, page)
    next_url = url_for('event.settlements', guid=event.guid, page=result.next_num) if result.has_next else None
    prev_url = url_for('event.settlements', guid=event.guid, page=result.prev_num) if result.has_prev else None
    return render_template(
        'event/settlements.html',
        form=form,
        event=event,
        eventuser=eventuser,
        settlements=result.items,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route('/edit_settlement/<guid>', methods=['GET', 'POST'])
def edit_settlement(guid: str) -> str:
    """Edit an existing settlement."""
    settlement = Settlement.get_by_guid_or_404(guid)
    event = settlement.event
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    if not _can_edit(event, settlement.sender):
        flash(_('Your are only allowed to edit your own settlements!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.settlements', guid=settlement.event.guid))

    form = SettlementForm()
    form.currency_id.choices = [(c.id, c.code) for c in event.currencies]
    form.recipient_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        update_settlement(
            guid=guid,
            currency_id=form.currency_id.data,
            amount=form.amount.data,
            recipient_id=form.recipient_id.data,
            description=form.description.data,
        )
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.settlements', guid=event.guid))
    elif request.method == 'GET':
        form.currency_id.data = settlement.currency.id
        form.amount.data = settlement.amount
        form.recipient_id.data = settlement.recipient.id
        form.description.data = settlement.description
    return render_template('edit_form.html', title=_('Edit Settlement'), form=form)


@bp.route('/balance/pay/<guid>', methods=['GET'])
def settlement_execute(guid: str) -> str:
    """Confirm a draft settlement (mark as non-draft)."""
    settlement = Settlement.get_by_guid_or_404(guid)
    event = settlement.event
    if not _can_edit(event, settlement.recipient):
        flash(_('Your are only allowed to confirm a settlement directed to you!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.settlements', guid=settlement.event.guid))
    log_page_access(request, current_user)
    eventuser = get_eventuser_from_cookie(event, _cookie_guid(event))
    execute_draft_settlement(guid, eventuser.username)
    return redirect(url_for('event.balance', guid=event.guid))


@bp.route('/remove_settlement/<guid>')
def remove_settlement_route(guid: str) -> str:
    """Remove a settlement from an event."""
    settlement = Settlement.get_by_guid_or_404(guid)
    event = settlement.event
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    if not _can_edit(event, settlement.sender):
        flash(_('Your are only allowed to edit your own settlements!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.settlements', guid=settlement.event.guid))

    amount_str = settlement.get_amount_str()
    remove_settlement(guid)
    flash(_('Settlement over %(amount_str)s has been removed from event %(event_name)s.', amount_str=amount_str, event_name=event.name))
    return redirect(url_for('event.settlements', guid=event.guid))


# ---------------------------------------------------------------------------
# Event actions (reminders, balance, currency conversion, open/close)
# ---------------------------------------------------------------------------

@bp.route('/send_payment_reminders/<guid>')
@login_required
def send_payment_reminders_route(guid: str) -> str:
    """Send payment reminder emails to all event users."""
    event = get_event(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to send payment reminders of your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=event.guid))
    log_page_access(request, current_user)
    send_payment_reminders(guid)
    flash(_('All users have been reminded of their duties!'))
    return redirect(url_for('event.main', guid=event.guid))


@bp.route('/request_balance/<guid>')
def request_balance(guid: str) -> str:
    """Request a balance report email for the current event user."""
    event = get_event(guid)
    log_page_access(request, current_user)
    eventuser_guid = request.cookies.get(f'{guid}.eventuser')
    request_balance_pdf(guid, eventuser_guid)
    flash(_('The balance has been sent to your email'))
    return redirect(url_for('event.main', guid=event.guid))


@bp.route('/convert_currencies/<guid>')
@login_required
def convert_currencies_route(guid: str) -> str:
    """Convert all event transactions to the base currency."""
    event = get_event(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to convert currencies of your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=event.guid))
    log_page_access(request, current_user)
    convert_currencies(guid)
    flash(_('All transaction of this event have been converted to %(code)s.', code=event.base_currency.code))
    return redirect(url_for('event.main', guid=event.guid))


@bp.route('/reopen/<guid>')
@login_required
def reopen(guid: str) -> str:
    """Reopen a closed event."""
    event = get_event(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to reopen your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=event.guid))
    log_page_access(request, current_user)
    reopen_event(guid)
    flash(_('Event has been reopened.'))
    return redirect(url_for('event.main', guid=event.guid))


@bp.route('/close/<guid>')
@login_required
def close(guid: str) -> str:
    """Close an event if no open liabilities remain."""
    event = get_event(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to close your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=event.guid))
    log_page_access(request, current_user)
    result = close_event(guid)
    if not result.success:
        flash(_('Your are only allowed to close an event with no open liabilities!'))
        return redirect(url_for('event.main', guid=event.guid))
    flash(_('Event has been closed.'))
    return redirect(url_for('event.main', guid=event.guid))
