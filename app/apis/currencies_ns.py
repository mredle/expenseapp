# coding=utf-8
"""Currencies REST API namespace: list, create, read, and update currencies."""

from __future__ import annotations

from flask import g, request
from flask_restx import Namespace, Resource, fields

from app.apis.auth import token_auth
from app.apis.errors import bad_request
from app.services import main_service

api = Namespace('currencies', description='Currency operations')

# ---------------------------------------------------------------------------
# API models
# ---------------------------------------------------------------------------

currency_model = api.model('Currency', {
    'id': fields.Integer(description='Currency database ID'),
    'guid': fields.String(description='Currency GUID'),
    'code': fields.String(required=True, description='ISO 4217 code (e.g. CHF)'),
    'name': fields.String(required=True, description='Currency name'),
    'number': fields.Integer(required=True, description='ISO 4217 numeric code'),
    'exponent': fields.Integer(required=True, description='Decimal exponent'),
    'inCHF': fields.Float(required=True, description='Exchange rate to CHF'),
    'description': fields.String(description='Description'),
})

currency_input = api.model('CurrencyInput', {
    'code': fields.String(required=True, description='ISO 4217 code'),
    'name': fields.String(required=True, description='Currency name'),
    'number': fields.Integer(required=True, description='ISO 4217 numeric code'),
    'exponent': fields.Integer(required=True, description='Decimal exponent'),
    'inCHF': fields.Float(required=True, description='Exchange rate to CHF'),
    'description': fields.String(description='Description', default=''),
})

currency_list_model = api.model('CurrencyList', {
    'items': fields.List(fields.Nested(currency_model), description='List of currencies'),
    'total': fields.Integer(description='Total number of currencies'),
    'has_next': fields.Boolean(description='Whether there is a next page'),
    'has_prev': fields.Boolean(description='Whether there is a previous page'),
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _currency_to_dict(currency: object) -> dict:
    """Serialise a Currency model to a dict."""
    return {
        'id': currency.id,
        'guid': str(currency.guid),
        'code': currency.code,
        'name': currency.name,
        'number': currency.number,
        'exponent': currency.exponent,
        'inCHF': currency.inCHF,
        'description': currency.description or '',
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@api.route('/')
class CurrencyList(Resource):
    """List all currencies or create a new one."""

    @token_auth.login_required
    @api.marshal_with(currency_list_model)
    def get(self) -> dict:
        """Return a paginated list of currencies."""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        result = main_service.list_currencies(page, per_page)
        return {
            'items': [_currency_to_dict(c) for c in result.items],
            'total': result.total,
            'has_next': result.has_next,
            'has_prev': result.has_prev,
        }

    @token_auth.login_required
    @api.expect(currency_input)
    @api.marshal_with(currency_model, code=201)
    @api.response(400, 'Validation error')
    @api.response(403, 'Admin required')
    def post(self) -> tuple:
        """Create a new currency (admin only)."""
        if not g.current_user.is_admin:
            return {'error': 'Admin privileges required'}, 403

        data = request.get_json() or {}
        for field in ('code', 'name', 'number', 'exponent', 'inCHF'):
            if field not in data:
                return bad_request(f'{field} is required')

        result = main_service.create_currency(
            code=data['code'],
            name=data['name'],
            number=data['number'],
            exponent=data['exponent'],
            inCHF=data['inCHF'],
            description=data.get('description', ''),
            created_by=g.current_user.username,
        )
        return _currency_to_dict(result.currency), 201


@api.route('/<guid>')
class CurrencyDetail(Resource):
    """Read or update a single currency by GUID."""

    @token_auth.login_required
    @api.marshal_with(currency_model)
    def get(self, guid: str) -> dict:
        """Return a single currency."""
        currency = main_service.get_currency(guid)
        return _currency_to_dict(currency)

    @token_auth.login_required
    @api.expect(currency_input)
    @api.marshal_with(currency_model)
    @api.response(403, 'Admin required')
    def put(self, guid: str) -> dict | tuple:
        """Update an existing currency (admin only)."""
        if not g.current_user.is_admin:
            return {'error': 'Admin privileges required'}, 403

        data = request.get_json() or {}
        for field in ('code', 'name', 'number', 'exponent', 'inCHF'):
            if field not in data:
                return bad_request(f'{field} is required')

        result = main_service.update_currency(
            guid=guid,
            code=data['code'],
            name=data['name'],
            number=data['number'],
            exponent=data['exponent'],
            inCHF=data['inCHF'],
            description=data.get('description', ''),
        )
        return _currency_to_dict(result.currency)
