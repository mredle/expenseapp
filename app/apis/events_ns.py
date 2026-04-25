# coding=utf-8
"""Events REST API namespace: event CRUD, users, currencies, expenses, settlements, posts, and lifecycle."""

from __future__ import annotations

from datetime import datetime

from flask import g, request
from flask_restx import Namespace, Resource, fields
from werkzeug.exceptions import Forbidden

from app import db
from app.apis.auth import token_auth
from app.apis.errors import bad_request
from app.services import event_service

api = Namespace('events', description='Event operations')

# ---------------------------------------------------------------------------
# API models
# ---------------------------------------------------------------------------

event_model = api.model('Event', {
    'guid': fields.String(description='Event GUID'),
    'name': fields.String(description='Event name'),
    'date': fields.String(description='Event date'),
    'closed': fields.Boolean(description='Whether the event is closed'),
    'description': fields.String(description='Event description'),
    'fileshare_link': fields.String(description='File sharing link'),
    'exchange_fee': fields.Float(description='Exchange fee percentage'),
    'base_currency_code': fields.String(description='Base currency code'),
    'admin_username': fields.String(description='Event admin username'),
    'accountant_username': fields.String(description='Event accountant username'),
    'stats': fields.Raw(description='Event statistics'),
    'image_url': fields.String(description='Event cover image URL'),
})

event_list_model = api.model('EventList', {
    'items': fields.List(fields.Nested(event_model), description='Events'),
    'total': fields.Integer(description='Total events'),
    'has_next': fields.Boolean(description='Next page available'),
    'has_prev': fields.Boolean(description='Previous page available'),
})

event_input = api.model('EventInput', {
    'name': fields.String(required=True, description='Event name'),
    'date': fields.String(required=True, description='Event date (ISO 8601)'),
    'base_currency_id': fields.Integer(required=True, description='Base currency ID'),
    'currency_ids': fields.List(fields.Integer, required=True, description='Currency IDs'),
    'exchange_fee': fields.Float(required=True, description='Exchange fee %'),
    'fileshare_link': fields.String(description='File sharing link', default=''),
    'description': fields.String(description='Description', default=''),
})

event_update_input = api.model('EventUpdateInput', {
    'name': fields.String(required=True, description='Event name'),
    'date': fields.String(required=True, description='Event date (ISO 8601)'),
    'base_currency_id': fields.Integer(required=True, description='Base currency ID'),
    'currency_ids': fields.List(fields.Integer, required=True, description='Currency IDs'),
    'exchange_fee': fields.Float(required=True, description='Exchange fee %'),
    'accountant_id': fields.Integer(required=True, description='Accountant EventUser ID'),
    'fileshare_link': fields.String(description='File sharing link', default=''),
    'description': fields.String(description='Description', default=''),
})

eventuser_model = api.model('EventUser', {
    'guid': fields.String(description='EventUser GUID'),
    'id': fields.Integer(description='EventUser ID'),
    'username': fields.String(description='Display name'),
    'email': fields.String(description='Email address'),
    'weighting': fields.Float(description='Cost-sharing weight'),
    'locale': fields.String(description='Locale'),
    'about_me': fields.String(description='About'),
    'avatar': fields.String(description='Avatar URL'),
})

eventuser_input = api.model('EventUserInput', {
    'username': fields.String(required=True, description='Display name'),
    'email': fields.String(required=True, description='Email address'),
    'weighting': fields.Float(required=True, description='Cost-sharing weight'),
    'locale': fields.String(description='Locale', default='en'),
    'about_me': fields.String(description='About', default=''),
})

eventuser_profile_input = api.model('EventUserProfileInput', {
    'username': fields.String(required=True, description='Display name'),
    'email': fields.String(required=True, description='Email'),
    'weighting': fields.Float(required=True, description='Weight'),
    'about_me': fields.String(description='About', default=''),
    'locale': fields.String(description='Locale', default='en'),
})

eventuser_bank_input = api.model('EventUserBankInput', {
    'iban': fields.String(description='IBAN'),
    'bank': fields.String(description='Bank name'),
    'name': fields.String(description='Account holder name'),
    'address': fields.String(description='Address'),
    'address_suffix': fields.String(description='Address line 2'),
    'zip_code': fields.Integer(description='ZIP code'),
    'city': fields.String(description='City'),
    'country': fields.String(description='Country'),
})

paginated_eventuser_model = api.model('EventUserList', {
    'items': fields.List(fields.Nested(eventuser_model), description='Event users'),
    'total': fields.Integer(description='Total users'),
    'has_next': fields.Boolean(description='Next page available'),
    'has_prev': fields.Boolean(description='Previous page available'),
})

eventcurrency_model = api.model('EventCurrency', {
    'currency_code': fields.String(description='Currency code'),
    'currency_name': fields.String(description='Currency name'),
    'inCHF': fields.Float(description='Exchange rate to CHF within this event'),
})

eventcurrency_list_model = api.model('EventCurrencyList', {
    'items': fields.List(fields.Nested(eventcurrency_model), description='Event currencies'),
    'total': fields.Integer(description='Total currencies'),
})

rate_input = api.model('RateInput', {
    'rate': fields.Float(required=True, description='Exchange rate to CHF'),
})

expense_model = api.model('Expense', {
    'guid': fields.String(description='Expense GUID'),
    'amount': fields.Float(description='Amount in original currency'),
    'amount_str': fields.String(description='Formatted amount string'),
    'currency_code': fields.String(description='Currency code'),
    'date': fields.String(description='Expense date'),
    'description': fields.String(description='Description'),
    'user_username': fields.String(description='Who paid'),
    'image_url': fields.String(description='Receipt image URL'),
})

expense_input = api.model('ExpenseInput', {
    'currency_id': fields.Integer(required=True, description='Currency ID'),
    'amount': fields.Float(required=True, description='Amount'),
    'affected_user_ids': fields.List(fields.Integer, required=True, description='Affected user IDs'),
    'date': fields.String(required=True, description='Expense date (ISO 8601)'),
    'description': fields.String(description='Description', default=''),
})

expense_list_model = api.model('ExpenseList', {
    'items': fields.List(fields.Nested(expense_model), description='Expenses'),
    'total': fields.Integer(description='Total expenses'),
    'has_next': fields.Boolean(description='Next page available'),
    'has_prev': fields.Boolean(description='Previous page available'),
})

settlement_model = api.model('Settlement', {
    'guid': fields.String(description='Settlement GUID'),
    'amount': fields.Float(description='Amount'),
    'amount_str': fields.String(description='Formatted amount'),
    'currency_code': fields.String(description='Currency code'),
    'sender_username': fields.String(description='Sender'),
    'recipient_username': fields.String(description='Recipient'),
    'draft': fields.Boolean(description='Is draft'),
    'date': fields.String(description='Settlement date'),
    'description': fields.String(description='Description'),
})

settlement_input = api.model('SettlementInput', {
    'recipient_id': fields.Integer(required=True, description='Recipient EventUser ID'),
    'currency_id': fields.Integer(required=True, description='Currency ID'),
    'amount': fields.Float(required=True, description='Amount'),
    'description': fields.String(description='Description', default=''),
})

settlement_list_model = api.model('SettlementList', {
    'items': fields.List(fields.Nested(settlement_model), description='Settlements'),
    'total': fields.Integer(description='Total settlements'),
    'has_next': fields.Boolean(description='Next page available'),
    'has_prev': fields.Boolean(description='Previous page available'),
})

post_model = api.model('Post', {
    'guid': fields.String(description='Post GUID'),
    'body': fields.String(description='Post body'),
    'timestamp': fields.String(description='Post timestamp'),
    'author_username': fields.String(description='Author display name'),
})

post_input = api.model('PostInput', {
    'body': fields.String(required=True, description='Post body'),
})

post_list_model = api.model('PostList', {
    'items': fields.List(fields.Nested(post_model), description='Posts'),
    'total': fields.Integer(description='Total posts'),
    'has_next': fields.Boolean(description='Next page available'),
    'has_prev': fields.Boolean(description='Previous page available'),
})

balance_user_model = api.model('BalanceUser', {
    'username': fields.String(description='EventUser name'),
    'paid': fields.String(description='Amount paid'),
    'spent': fields.String(description='Amount spent'),
    'sent': fields.String(description='Amount sent in settlements'),
    'received': fields.String(description='Amount received in settlements'),
    'balance': fields.String(description='Net balance'),
})

balance_model = api.model('Balance', {
    'balances': fields.List(fields.Nested(balance_user_model), description='Per-user balances'),
    'total_expenses': fields.String(description='Total expenses formatted'),
    'draft_settlements': fields.List(fields.Nested(settlement_model), description='Draft settlements'),
})

message_response = api.model('EventMessageResponse', {
    'message': fields.String(description='Status message'),
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_eventuser_guid() -> str | None:
    """Read the X-EventUser-GUID header."""
    return request.headers.get('X-EventUser-GUID')


def _event_to_dict(event: object) -> dict:
    """Serialise an Event model to a dict."""
    return {
        'guid': str(event.guid),
        'name': event.name,
        'date': event.date.isoformat() if event.date else None,
        'closed': event.closed,
        'description': event.description or '',
        'fileshare_link': event.fileshare_link or '',
        'exchange_fee': event.exchange_fee,
        'base_currency_code': event.base_currency.code if event.base_currency else None,
        'admin_username': event.admin.username if event.admin else None,
        'accountant_username': event.accountant.username if event.accountant else None,
        'stats': event.get_stats(),
        'image_url': event.avatar(256),
    }


def _eventuser_to_dict(eu: object) -> dict:
    """Serialise an EventUser model to a dict."""
    return {
        'guid': str(eu.guid),
        'id': eu.id,
        'username': eu.username,
        'email': eu.email,
        'weighting': eu.weighting,
        'locale': eu.locale,
        'about_me': eu.about_me or '',
        'avatar': eu.avatar(128),
    }


def _expense_to_dict(expense: object) -> dict:
    """Serialise an Expense model to a dict."""
    return {
        'guid': str(expense.guid),
        'amount': expense.amount,
        'amount_str': expense.get_amount_str(),
        'currency_code': expense.currency.code if expense.currency else None,
        'date': expense.date.isoformat() if expense.date else None,
        'description': expense.description or '',
        'user_username': expense.user.username if expense.user else None,
        'image_url': expense.avatar(256),
    }


def _settlement_to_dict(settlement: object) -> dict:
    """Serialise a Settlement model to a dict."""
    return {
        'guid': str(settlement.guid),
        'amount': settlement.amount,
        'amount_str': settlement.get_amount_str(),
        'currency_code': settlement.currency.code if settlement.currency else None,
        'sender_username': settlement.sender.username if settlement.sender else None,
        'recipient_username': settlement.recipient.username if settlement.recipient else None,
        'draft': settlement.draft,
        'date': settlement.date.isoformat() if settlement.date else None,
        'description': settlement.description or '',
    }


def _post_to_dict(post: object) -> dict:
    """Serialise a Post model to a dict."""
    return {
        'guid': str(post.guid),
        'body': post.body,
        'timestamp': post.timestamp.isoformat() if post.timestamp else None,
        'author_username': post.author.username if post.author else None,
    }


def _eventcurrency_to_dict(ec: object) -> dict:
    """Serialise an EventCurrency to a dict."""
    return {
        'currency_code': ec.currency.code if ec.currency else None,
        'currency_name': ec.currency.name if ec.currency else None,
        'inCHF': ec.inCHF,
    }


def _resolve_or_401(event: object) -> object:
    """Resolve the EventUser for the current request, or abort 401."""
    eu_guid = _get_eventuser_guid()
    user = getattr(g, 'current_user', None)
    eu = event_service.resolve_eventuser(event, eu_guid, user)
    if eu is None:
        api.abort(401, 'Cannot resolve EventUser for this event')
    return eu


# ---------------------------------------------------------------------------
# Event CRUD
# ---------------------------------------------------------------------------

@api.route('/')
class EventList(Resource):
    """List events or create a new one."""

    @token_auth.login_required
    @api.marshal_with(event_list_model)
    def get(self) -> dict:
        """Return a paginated list of events for the authenticated user."""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        result = event_service.list_events(
            user=g.current_user,
            is_admin=g.current_user.is_admin,
            page=page,
            per_page=per_page,
        )
        return {
            'items': [_event_to_dict(e) for e in result.items],
            'total': result.total,
            'has_next': result.has_next,
            'has_prev': result.has_prev,
        }

    @token_auth.login_required
    @api.expect(event_input)
    @api.marshal_with(event_model, code=201)
    @api.response(400, 'Validation error')
    def post(self) -> tuple:
        """Create a new event."""
        data = request.get_json() or {}
        for field in ('name', 'date', 'base_currency_id', 'currency_ids', 'exchange_fee'):
            if field not in data:
                return bad_request(f'{field} is required')

        try:
            event_date = datetime.fromisoformat(data['date'])
        except (ValueError, TypeError):
            return bad_request('Invalid date format. Use ISO 8601.')

        result = event_service.create_event(
            name=data['name'],
            date=event_date,
            admin=g.current_user,
            base_currency_id=data['base_currency_id'],
            currency_ids=data['currency_ids'],
            exchange_fee=data['exchange_fee'],
            fileshare_link=data.get('fileshare_link', ''),
            description=data.get('description', ''),
            created_by=g.current_user.username,
        )
        return _event_to_dict(result.event), 201


@api.route('/<guid>')
class EventDetail(Resource):
    """Read or update a single event."""

    @token_auth.login_required
    @api.marshal_with(event_model)
    def get(self, guid: str) -> dict:
        """Return a single event."""
        event = event_service.get_event(guid)
        return _event_to_dict(event)

    @token_auth.login_required
    @api.expect(event_update_input)
    @api.marshal_with(event_model)
    @api.response(400, 'Validation error')
    @api.response(403, 'Permission denied')
    def put(self, guid: str) -> dict | tuple:
        """Update an existing event (admin only)."""
        event = event_service.get_event(guid)
        if not event.can_edit(g.current_user):
            return {'error': 'Permission denied'}, 403

        data = request.get_json() or {}
        for field in ('name', 'date', 'base_currency_id', 'currency_ids', 'exchange_fee', 'accountant_id'):
            if field not in data:
                return bad_request(f'{field} is required')

        try:
            event_date = datetime.fromisoformat(data['date'])
        except (ValueError, TypeError):
            return bad_request('Invalid date format. Use ISO 8601.')

        result = event_service.update_event(
            guid=guid,
            name=data['name'],
            date=event_date,
            fileshare_link=data.get('fileshare_link', ''),
            description=data.get('description', ''),
            base_currency_id=data['base_currency_id'],
            exchange_fee=data['exchange_fee'],
            accountant_id=data['accountant_id'],
            currency_ids=data['currency_ids'],
        )
        return _event_to_dict(result.event)


# ---------------------------------------------------------------------------
# Event Users
# ---------------------------------------------------------------------------

@api.route('/<guid>/users')
class EventUserList(Resource):
    """List or add users to an event."""

    @token_auth.login_required
    @api.marshal_with(paginated_eventuser_model)
    def get(self, guid: str) -> dict:
        """Return a paginated list of event users."""
        event = event_service.get_event(guid)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        result = event_service.list_event_users(event, page, per_page)
        return {
            'items': [_eventuser_to_dict(eu) for eu in result.items],
            'total': result.total,
            'has_next': result.has_next,
            'has_prev': result.has_prev,
        }

    @token_auth.login_required
    @api.expect(eventuser_input)
    @api.marshal_with(eventuser_model, code=201)
    @api.response(400, 'Validation error')
    @api.response(403, 'Permission denied')
    def post(self, guid: str) -> tuple:
        """Add a new user to the event (admin only)."""
        event = event_service.get_event(guid)
        if not event.can_edit(g.current_user):
            return {'error': 'Permission denied'}, 403

        data = request.get_json() or {}
        for field in ('username', 'email', 'weighting'):
            if field not in data:
                return bad_request(f'{field} is required')

        result = event_service.add_event_user(
            event=event,
            username=data['username'],
            email=data['email'],
            weighting=data['weighting'],
            locale=data.get('locale', 'en'),
            about_me=data.get('about_me', ''),
        )
        return _eventuser_to_dict(result.eventuser), 201


@api.route('/<guid>/users/<user_guid>')
class EventUserDetail(Resource):
    """Manage a single event user."""

    @token_auth.login_required
    @api.marshal_with(eventuser_model)
    def get(self, guid: str, user_guid: str) -> dict:
        """Return a single event user."""
        from app.models import EventUser
        eu = EventUser.get_by_guid_or_404(user_guid)
        return _eventuser_to_dict(eu)

    @token_auth.login_required
    @api.marshal_with(message_response)
    @api.response(400, 'Cannot remove user')
    @api.response(403, 'Permission denied')
    def delete(self, guid: str, user_guid: str) -> dict | tuple:
        """Remove a user from the event (admin only)."""
        event = event_service.get_event(guid)
        if not event.can_edit(g.current_user):
            return {'error': 'Permission denied'}, 403

        result = event_service.remove_event_user(event, user_guid)
        if not result.success:
            return bad_request(result.error or 'Cannot remove user')
        return {'message': 'User removed'}


@api.route('/<guid>/users/<user_guid>/readd')
class EventUserReadd(Resource):
    """Re-add a previously removed user to an event."""

    @token_auth.login_required
    @api.marshal_with(eventuser_model)
    @api.response(403, 'Permission denied')
    def post(self, guid: str, user_guid: str) -> dict | tuple:
        """Re-add a user to the event."""
        event = event_service.get_event(guid)
        if not event.can_edit(g.current_user):
            return {'error': 'Permission denied'}, 403

        result = event_service.readd_event_user(event, user_guid)
        return _eventuser_to_dict(result.eventuser)


@api.route('/<guid>/users/<user_guid>/profile')
class EventUserProfile(Resource):
    """Update an event user's profile."""

    @token_auth.login_required
    @api.expect(eventuser_profile_input)
    @api.marshal_with(eventuser_model)
    def put(self, guid: str, user_guid: str) -> dict | tuple:
        """Update event user profile fields."""
        data = request.get_json() or {}
        for field in ('username', 'email', 'weighting'):
            if field not in data:
                return bad_request(f'{field} is required')

        result = event_service.update_event_user_profile(
            guid=user_guid,
            username=data['username'],
            email=data['email'],
            weighting=data['weighting'],
            about_me=data.get('about_me', ''),
            locale=data.get('locale', 'en'),
        )
        return _eventuser_to_dict(result.eventuser)


@api.route('/<guid>/users/<user_guid>/bank')
class EventUserBank(Resource):
    """Update an event user's bank account."""

    @token_auth.login_required
    @api.expect(eventuser_bank_input)
    @api.marshal_with(eventuser_model)
    def put(self, guid: str, user_guid: str) -> dict | tuple:
        """Update event user bank account details."""
        data = request.get_json() or {}
        result = event_service.update_event_user_bank_account(
            guid=user_guid,
            iban=data.get('iban', ''),
            bank=data.get('bank', ''),
            name=data.get('name', ''),
            address=data.get('address', ''),
            address_suffix=data.get('address_suffix', ''),
            zip_code=data.get('zip_code', 0),
            city=data.get('city', ''),
            country=data.get('country', ''),
        )
        return _eventuser_to_dict(result.eventuser)


# ---------------------------------------------------------------------------
# Event Currencies
# ---------------------------------------------------------------------------

@api.route('/<guid>/currencies')
class EventCurrencyList(Resource):
    """List currencies for an event."""

    @token_auth.login_required
    @api.marshal_with(eventcurrency_list_model)
    def get(self, guid: str) -> dict:
        """Return a paginated list of currencies for the event."""
        event = event_service.get_event(guid)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        result = event_service.list_event_currencies(event, page, per_page)
        return {
            'items': [_eventcurrency_to_dict(ec) for ec in result.items],
            'total': result.total,
        }


@api.route('/<guid>/currencies/<currency_guid>/rate')
class EventCurrencyRate(Resource):
    """Set the exchange rate for a currency within an event."""

    @token_auth.login_required
    @api.expect(rate_input)
    @api.marshal_with(message_response)
    @api.response(403, 'Permission denied')
    def put(self, guid: str, currency_guid: str) -> dict | tuple:
        """Set the exchange rate for a currency within the event."""
        event = event_service.get_event(guid)
        if not event.can_edit(g.current_user):
            return {'error': 'Permission denied'}, 403

        data = request.get_json() or {}
        rate = data.get('rate')
        if rate is None:
            return bad_request('rate is required')

        event_service.set_currency_rate(guid, currency_guid, rate)
        return {'message': 'Rate updated'}


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

@api.route('/<guid>/expenses')
class ExpenseList(Resource):
    """List or create expenses for an event."""

    @token_auth.login_required
    @api.marshal_with(expense_list_model)
    def get(self, guid: str) -> dict:
        """Return a paginated list of expenses.

        Query params: ``page``, ``per_page``, ``own`` (true to filter own expenses).
        """
        event = event_service.get_event(guid)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        filter_own = request.args.get('own', 'false').lower() == 'true'

        eu_guid = _get_eventuser_guid()
        eventuser = event_service.resolve_eventuser(event, eu_guid, g.current_user)

        result = event_service.list_expenses(
            event=event,
            page=page,
            eventuser=eventuser,
            filter_own=filter_own,
            per_page=per_page,
        )
        return {
            'items': [_expense_to_dict(e) for e in result.items],
            'total': result.total,
            'has_next': result.has_next,
            'has_prev': result.has_prev,
        }

    @token_auth.login_required
    @api.expect(expense_input)
    @api.marshal_with(expense_model, code=201)
    @api.response(400, 'Validation error')
    @api.response(401, 'Cannot resolve EventUser')
    def post(self, guid: str) -> tuple:
        """Create a new expense on the event."""
        event = event_service.get_event(guid)
        eventuser = _resolve_or_401(event)

        data = request.get_json() or {}
        for field in ('currency_id', 'amount', 'affected_user_ids', 'date'):
            if field not in data:
                return bad_request(f'{field} is required')

        try:
            expense_date = datetime.fromisoformat(data['date'])
        except (ValueError, TypeError):
            return bad_request('Invalid date format. Use ISO 8601.')

        result = event_service.create_expense(
            event=event,
            eventuser=eventuser,
            currency_id=data['currency_id'],
            amount=data['amount'],
            affected_user_ids=data['affected_user_ids'],
            date=expense_date,
            description=data.get('description', ''),
            created_by=eventuser.username,
        )
        return _expense_to_dict(result.expense), 201


@api.route('/<guid>/expenses/<expense_guid>')
class ExpenseDetail(Resource):
    """Read, update, or delete a single expense."""

    @token_auth.login_required
    @api.marshal_with(expense_model)
    def get(self, guid: str, expense_guid: str) -> dict:
        """Return a single expense."""
        from app.models import Expense
        expense = Expense.get_by_guid_or_404(expense_guid)
        return _expense_to_dict(expense)

    @token_auth.login_required
    @api.expect(expense_input)
    @api.marshal_with(expense_model)
    @api.response(403, 'Permission denied')
    def put(self, guid: str, expense_guid: str) -> dict | tuple:
        """Update an existing expense."""
        from app.models import Expense
        expense = Expense.get_by_guid_or_404(expense_guid)

        eu_guid = _get_eventuser_guid()
        eventuser = event_service.resolve_eventuser(expense.event, eu_guid, g.current_user)
        if not expense.can_edit(g.current_user, eventuser):
            return {'error': 'Permission denied'}, 403

        data = request.get_json() or {}
        for field in ('currency_id', 'amount', 'affected_user_ids', 'date'):
            if field not in data:
                return bad_request(f'{field} is required')

        try:
            expense_date = datetime.fromisoformat(data['date'])
        except (ValueError, TypeError):
            return bad_request('Invalid date format. Use ISO 8601.')

        result = event_service.update_expense(
            guid=expense_guid,
            currency_id=data['currency_id'],
            amount=data['amount'],
            affected_user_ids=data['affected_user_ids'],
            date=expense_date,
            description=data.get('description', ''),
        )
        return _expense_to_dict(result.expense)

    @token_auth.login_required
    @api.marshal_with(message_response)
    @api.response(403, 'Permission denied')
    def delete(self, guid: str, expense_guid: str) -> dict | tuple:
        """Remove an expense."""
        from app.models import Expense
        expense = Expense.get_by_guid_or_404(expense_guid)

        eu_guid = _get_eventuser_guid()
        eventuser = event_service.resolve_eventuser(expense.event, eu_guid, g.current_user)
        if not expense.can_edit(g.current_user, eventuser):
            return {'error': 'Permission denied'}, 403

        event_service.remove_expense(expense_guid)
        return {'message': 'Expense removed'}


@api.route('/<guid>/expenses/<expense_guid>/users')
class ExpenseUserList(Resource):
    """List or add affected users to an expense."""

    @token_auth.login_required
    @api.marshal_with(paginated_eventuser_model)
    def get(self, guid: str, expense_guid: str) -> dict:
        """Return the list of users affected by this expense."""
        from app.models import Expense
        expense = Expense.get_by_guid_or_404(expense_guid)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        result = event_service.list_expense_users(expense, page, per_page)
        return {
            'items': [_eventuser_to_dict(eu) for eu in result.items],
            'total': result.total,
            'has_next': result.has_next,
            'has_prev': result.has_prev,
        }


@api.route('/<guid>/expenses/<expense_guid>/users/<user_guid>')
class ExpenseUserDetail(Resource):
    """Add or remove a single user from an expense's affected list."""

    @token_auth.login_required
    @api.marshal_with(eventuser_model, code=201)
    def post(self, guid: str, expense_guid: str, user_guid: str) -> tuple:
        """Add a user to the expense's affected list."""
        user = event_service.add_expense_user(expense_guid, user_guid)
        return _eventuser_to_dict(user), 201

    @token_auth.login_required
    @api.marshal_with(message_response)
    @api.response(400, 'Cannot remove user')
    def delete(self, guid: str, expense_guid: str, user_guid: str) -> dict | tuple:
        """Remove a user from the expense's affected list."""
        result = event_service.remove_expense_user(expense_guid, user_guid)
        if not result.success:
            return bad_request(result.error or 'Cannot remove user')
        return {'message': 'User removed from expense'}


# ---------------------------------------------------------------------------
# Settlements
# ---------------------------------------------------------------------------

@api.route('/<guid>/settlements')
class SettlementList(Resource):
    """List or create settlements for an event."""

    @token_auth.login_required
    @api.marshal_with(settlement_list_model)
    def get(self, guid: str) -> dict:
        """Return a paginated list of settlements.

        Query params: ``page``, ``per_page``, ``draft`` (true/false).
        """
        event = event_service.get_event(guid)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        draft_str = request.args.get('draft', 'false')
        draft = draft_str.lower() == 'true'

        result = event_service.list_settlements(event, page, draft=draft, per_page=per_page)
        return {
            'items': [_settlement_to_dict(s) for s in result.items],
            'total': result.total,
            'has_next': result.has_next,
            'has_prev': result.has_prev,
        }

    @token_auth.login_required
    @api.expect(settlement_input)
    @api.marshal_with(settlement_model, code=201)
    @api.response(401, 'Cannot resolve EventUser')
    def post(self, guid: str) -> tuple:
        """Create a new settlement on the event."""
        event = event_service.get_event(guid)
        eventuser = _resolve_or_401(event)

        data = request.get_json() or {}
        for field in ('recipient_id', 'currency_id', 'amount'):
            if field not in data:
                return bad_request(f'{field} is required')

        result = event_service.create_settlement(
            event=event,
            sender=eventuser,
            recipient_id=data['recipient_id'],
            currency_id=data['currency_id'],
            amount=data['amount'],
            description=data.get('description', ''),
            created_by=eventuser.username,
        )
        return _settlement_to_dict(result.settlement), 201


@api.route('/<guid>/settlements/<settlement_guid>')
class SettlementDetail(Resource):
    """Read, update, or delete a single settlement."""

    @token_auth.login_required
    @api.marshal_with(settlement_model)
    def get(self, guid: str, settlement_guid: str) -> dict:
        """Return a single settlement."""
        from app.models import Settlement
        settlement = Settlement.get_by_guid_or_404(settlement_guid)
        return _settlement_to_dict(settlement)

    @token_auth.login_required
    @api.expect(settlement_input)
    @api.marshal_with(settlement_model)
    @api.response(403, 'Permission denied')
    def put(self, guid: str, settlement_guid: str) -> dict | tuple:
        """Update an existing settlement."""
        from app.models import Settlement
        settlement = Settlement.get_by_guid_or_404(settlement_guid)

        eu_guid = _get_eventuser_guid()
        eventuser = event_service.resolve_eventuser(settlement.event, eu_guid, g.current_user)
        if not settlement.can_edit(g.current_user, eventuser):
            return {'error': 'Permission denied'}, 403

        data = request.get_json() or {}
        for field in ('recipient_id', 'currency_id', 'amount'):
            if field not in data:
                return bad_request(f'{field} is required')

        result = event_service.update_settlement(
            guid=settlement_guid,
            currency_id=data['currency_id'],
            amount=data['amount'],
            recipient_id=data['recipient_id'],
            description=data.get('description', ''),
        )
        return _settlement_to_dict(result.settlement)

    @token_auth.login_required
    @api.marshal_with(message_response)
    @api.response(403, 'Permission denied')
    def delete(self, guid: str, settlement_guid: str) -> dict | tuple:
        """Remove a settlement."""
        from app.models import Settlement
        settlement = Settlement.get_by_guid_or_404(settlement_guid)

        eu_guid = _get_eventuser_guid()
        eventuser = event_service.resolve_eventuser(settlement.event, eu_guid, g.current_user)
        if not settlement.can_edit(g.current_user, eventuser):
            return {'error': 'Permission denied'}, 403

        event_service.remove_settlement(settlement_guid)
        return {'message': 'Settlement removed'}


@api.route('/<guid>/settlements/<settlement_guid>/confirm')
class SettlementConfirm(Resource):
    """Confirm a draft settlement."""

    @token_auth.login_required
    @api.marshal_with(settlement_model)
    @api.response(401, 'Cannot resolve EventUser')
    def post(self, guid: str, settlement_guid: str) -> dict | tuple:
        """Confirm a draft settlement (mark as executed)."""
        event = event_service.get_event(guid)
        eventuser = _resolve_or_401(event)

        result = event_service.execute_draft_settlement(settlement_guid, eventuser.username)
        return _settlement_to_dict(result.settlement)


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

@api.route('/<guid>/posts')
class PostList(Resource):
    """List or create posts for an event."""

    @token_auth.login_required
    @api.marshal_with(post_list_model)
    def get(self, guid: str) -> dict:
        """Return a paginated list of posts."""
        event = event_service.get_event(guid)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        result = event_service.list_posts(event, page, per_page)
        return {
            'items': [_post_to_dict(p) for p in result.items],
            'total': result.total,
            'has_next': result.has_next,
            'has_prev': result.has_prev,
        }

    @token_auth.login_required
    @api.expect(post_input)
    @api.marshal_with(post_model, code=201)
    @api.response(401, 'Cannot resolve EventUser')
    def post(self, guid: str) -> tuple:
        """Create a new post on the event."""
        event = event_service.get_event(guid)
        eventuser = _resolve_or_401(event)

        data = request.get_json() or {}
        body = data.get('body', '')
        if not body:
            return bad_request('body is required')

        result = event_service.create_post(str(event.guid), body, eventuser)
        return _post_to_dict(result.post), 201


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------

@api.route('/<guid>/balance')
class EventBalance(Resource):
    """Calculate and return the event balance."""

    @token_auth.login_required
    @api.marshal_with(balance_model)
    def get(self, guid: str) -> dict:
        """Recalculate the balance and return per-user balances and draft settlements."""
        result = event_service.get_balance(guid)
        balances = []
        for row in result.balances_str:
            balances.append({
                'username': row[0].username if hasattr(row[0], 'username') else str(row[0]),
                'paid': row[1],
                'spent': row[2],
                'sent': row[3],
                'received': row[4],
                'balance': row[5],
            })
        return {
            'balances': balances,
            'total_expenses': result.total_expenses_str,
            'draft_settlements': [_settlement_to_dict(s) for s in result.draft_settlements],
        }


# ---------------------------------------------------------------------------
# Event lifecycle
# ---------------------------------------------------------------------------

@api.route('/<guid>/convert-currencies')
class ConvertCurrencies(Resource):
    """Convert all event transactions to the base currency."""

    @token_auth.login_required
    @api.marshal_with(message_response)
    @api.response(403, 'Permission denied')
    def post(self, guid: str) -> dict | tuple:
        """Convert all expenses and settlements to the base currency."""
        event = event_service.get_event(guid)
        if not event.can_edit(g.current_user):
            return {'error': 'Permission denied'}, 403

        event_service.convert_currencies(guid)
        return {'message': 'Currencies converted'}


@api.route('/<guid>/close')
class CloseEvent(Resource):
    """Close an event."""

    @token_auth.login_required
    @api.marshal_with(message_response)
    @api.response(400, 'Event has open liabilities')
    @api.response(403, 'Permission denied')
    def post(self, guid: str) -> dict | tuple:
        """Close the event (requires no open draft settlements)."""
        event = event_service.get_event(guid)
        if not event.can_edit(g.current_user):
            return {'error': 'Permission denied'}, 403

        result = event_service.close_event(guid)
        if not result.success:
            return bad_request(result.error or 'Cannot close event')
        return {'message': 'Event closed'}


@api.route('/<guid>/reopen')
class ReopenEvent(Resource):
    """Reopen a closed event."""

    @token_auth.login_required
    @api.marshal_with(message_response)
    @api.response(403, 'Permission denied')
    def post(self, guid: str) -> dict | tuple:
        """Reopen the event."""
        event = event_service.get_event(guid)
        if not event.can_edit(g.current_user):
            return {'error': 'Permission denied'}, 403

        event_service.reopen_event(guid)
        return {'message': 'Event reopened'}


@api.route('/<guid>/send-reminders')
class SendReminders(Resource):
    """Send payment reminder emails."""

    @token_auth.login_required
    @api.marshal_with(message_response)
    @api.response(403, 'Permission denied')
    def post(self, guid: str) -> dict | tuple:
        """Launch a background task to send payment reminders."""
        event = event_service.get_event(guid)
        if not event.can_edit(g.current_user):
            return {'error': 'Permission denied'}, 403

        event_service.send_payment_reminders(guid)
        return {'message': 'Payment reminders queued'}


@api.route('/<guid>/request-balance')
class RequestBalance(Resource):
    """Request a balance report PDF by email."""

    @token_auth.login_required
    @api.marshal_with(message_response)
    def post(self, guid: str) -> dict:
        """Launch a background task to email a balance report.

        Optionally pass ``eventuser_guid`` in the JSON body to target
        a specific participant.
        """
        data = request.get_json() or {}
        eventuser_guid = data.get('eventuser_guid')
        event_service.request_balance_pdf(guid, eventuser_guid)
        return {'message': 'Balance report queued'}


# ---------------------------------------------------------------------------
# Image upload endpoints
# ---------------------------------------------------------------------------

event_image_model = api.model('EventImage', {
    'guid': fields.String(description='Image GUID'),
    'url': fields.String(description='Image URL'),
    'width': fields.Integer(description='Width'),
    'height': fields.Integer(description='Height'),
})


@api.route('/<guid>/picture')
class EventPicture(Resource):
    """Upload a cover picture for an event."""

    @token_auth.login_required
    @api.marshal_with(event_image_model, code=201)
    def post(self, guid: str) -> tuple:
        """Upload event cover picture (multipart/form-data, field: image). Admin only."""
        from app.models import Event
        event = Event.get_by_guid_or_404(guid)
        if event.admin_id != g.current_user.id and not g.current_user.is_admin:
            raise Forbidden('Only the event admin can upload a cover picture')
        if 'image' not in request.files or request.files['image'].filename == '':
            return bad_request('No image file provided')
        file_obj = request.files['image']
        image = event_service.update_event_picture(guid, file_obj.stream, file_obj.filename)
        return {'guid': image.guid, 'url': image.get_url(), 'width': image.width, 'height': image.height}, 201


@api.route('/<guid>/users/<user_guid>/picture')
class EventUserPicture(Resource):
    """Upload a profile picture for an event user."""

    @token_auth.login_required
    @api.marshal_with(event_image_model, code=201)
    def post(self, guid: str, user_guid: str) -> tuple:
        """Upload event user profile picture (multipart/form-data, field: image)."""
        if 'image' not in request.files or request.files['image'].filename == '':
            return bad_request('No image file provided')
        file_obj = request.files['image']
        image = event_service.update_event_user_picture(user_guid, file_obj.stream, file_obj.filename)
        return {'guid': image.guid, 'url': image.get_url(), 'width': image.width, 'height': image.height}, 201


@api.route('/<guid>/expenses/<expense_guid>/receipt')
class ExpenseReceipt(Resource):
    """Upload a receipt image for an expense."""

    @token_auth.login_required
    @api.marshal_with(event_image_model, code=201)
    def post(self, guid: str, expense_guid: str) -> tuple:
        """Upload expense receipt (multipart/form-data, field: image)."""
        if 'image' not in request.files or request.files['image'].filename == '':
            return bad_request('No image file provided')
        file_obj = request.files['image']
        image = event_service.add_receipt(expense_guid, file_obj.stream, file_obj.filename)
        return {'guid': image.guid, 'url': image.get_url(), 'width': image.width, 'height': image.height}, 201
