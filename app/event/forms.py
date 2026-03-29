# -*- coding: utf-8 -*-
"""WTForms form classes for the event blueprint."""

from __future__ import annotations

from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l
from wtforms import (
    StringField, SubmitField, TextAreaField, SelectField,
    SelectMultipleField, IntegerField, FloatField,
)
from wtforms.validators import DataRequired, Optional, Length, Email, Regexp
from wtforms.fields import DateField


class PostForm(FlaskForm):
    """Form for submitting a new post on the event wall."""

    post = TextAreaField(
        _l('Say something'),
        validators=[DataRequired(), Length(min=1, max=256)],
    )
    submit = SubmitField(_l('Submit'))


class SetRateForm(FlaskForm):
    """Form for setting a currency exchange rate."""

    inCHF = FloatField(_l('Value in CHF'), validators=[DataRequired()])
    submit = SubmitField(_l('Submit'))


class EventForm(FlaskForm):
    """Form for creating a new event."""

    name = StringField(
        _l('Name'),
        validators=[DataRequired(), Length(min=0, max=256)],
    )
    date = DateField(
        _l('Date in Y-m-d'),
        format='%Y-%m-%d',
        validators=[DataRequired()],
    )
    fileshare_link = TextAreaField(
        _l('Link to external fileshare'),
        validators=[Length(min=0, max=256)],
    )
    description = TextAreaField(
        _l('Description'),
        validators=[Length(min=0, max=256)],
    )
    base_currency_id = SelectField(
        _l('Base currency'),
        coerce=int,
        validators=[DataRequired()],
    )
    currency_id = SelectMultipleField(
        _l('Allowed currencies'),
        coerce=int,
        validators=[DataRequired()],
    )
    exchange_fee = FloatField(
        _l('Exchange fee (%)'),
        default=2.0,
        validators=[DataRequired()],
    )
    submit = SubmitField(_l('Submit'))


class EventEditForm(FlaskForm):
    """Form for editing an existing event."""

    name = StringField(
        _l('Name'),
        validators=[DataRequired(), Length(min=0, max=256)],
    )
    date = DateField(
        _l('Date in Y-m-d'),
        format='%Y-%m-%d',
        validators=[DataRequired()],
    )
    fileshare_link = TextAreaField(
        _l('Link to external fileshare'),
        validators=[Length(min=0, max=256)],
    )
    description = TextAreaField(
        _l('Description'),
        validators=[Length(min=0, max=256)],
    )
    base_currency_id = SelectField(
        _l('Base currency'),
        coerce=int,
        validators=[DataRequired()],
    )
    currency_id = SelectMultipleField(
        _l('Allowed currencies'),
        coerce=int,
        validators=[DataRequired()],
    )
    exchange_fee = FloatField(
        _l('Exchange fee (%)'),
        default=2.0,
        validators=[DataRequired()],
    )
    accountant_id = SelectField(
        _l('Select accountant'),
        coerce=int,
        validators=[DataRequired()],
    )
    submit = SubmitField(_l('Submit'))


class EventUserForm(FlaskForm):
    """Form for creating or editing an event user."""

    username = StringField(_l('Username'), validators=[DataRequired(), Regexp(r'^[\w.]+$')])
    email = StringField(_l('Email'), validators=[Optional(), Email()])
    weighting = FloatField(
        _l('Weighting'),
        default=1.0,
        validators=[DataRequired()],
    )
    about_me = TextAreaField(
        _l('About me'),
        validators=[Length(min=0, max=256)],
    )
    locale = SelectField(_l('Language'), validators=[DataRequired()])
    submit = SubmitField(_l('Submit'))


class BankAccountForm(FlaskForm):
    """Form for editing an event user's bank account details."""

    iban = StringField(
        _l('IBAN'),
        validators=[DataRequired(), Length(min=0, max=34)],
    )
    bank = StringField(
        _l('Bank name'),
        validators=[Length(min=0, max=64)],
    )
    name = StringField(
        _l('Account owner name'),
        validators=[DataRequired(), Length(min=0, max=64)],
    )
    address = StringField(
        _l('Address line'),
        validators=[DataRequired(), Length(min=0, max=128)],
    )
    address_suffix = StringField(
        _l('Address suffix'),
        validators=[Length(min=0, max=128)],
    )
    zip_code = IntegerField(_l('ZIP'), validators=[DataRequired()])
    city = StringField(
        _l('City'),
        validators=[DataRequired(), Length(min=0, max=64)],
    )
    country = StringField(
        _l('Country'),
        validators=[Length(min=0, max=64)],
    )
    submit = SubmitField(_l('Submit'))


class SelectUserForm(FlaskForm):
    """Form for selecting an event user context (stored as a cookie)."""

    user_id = SelectField(
        _l('Select user (will be saved as cookie)'),
        coerce=int,
        validators=[DataRequired()],
    )
    submit = SubmitField(_l('Submit'))


class ExpenseAddUserForm(FlaskForm):
    """Form for adding users to an expense."""

    user_id = SelectMultipleField(
        _l('Add user'),
        coerce=int,
        validators=[DataRequired()],
    )
    submit = SubmitField(_l('Submit'))


class ExpenseForm(FlaskForm):
    """Form for creating or editing an expense."""

    currency_id = SelectField(
        _l('Currency'),
        coerce=int,
        validators=[DataRequired()],
    )
    amount = FloatField(_l('Amount'), validators=[DataRequired()])
    affected_users_id = SelectMultipleField(
        _l('For users'),
        coerce=int,
        validators=[DataRequired()],
    )
    date = DateField(
        _l('Date'),
        format='%Y-%m-%d',
        validators=[DataRequired()],
    )
    description = TextAreaField(
        _l('Description'),
        validators=[Length(min=0, max=256)],
    )
    submit = SubmitField(_l('Submit'))


class SettlementForm(FlaskForm):
    """Form for creating or editing a settlement."""

    currency_id = SelectField(
        _l('Currency'),
        coerce=int,
        validators=[DataRequired()],
    )
    amount = FloatField(_l('Amount'), validators=[DataRequired()])
    recipient_id = SelectField(
        _l('Recipient'),
        coerce=int,
        validators=[DataRequired()],
    )
    description = TextAreaField(
        _l('Description'),
        validators=[Length(min=0, max=256)],
    )
    submit = SubmitField(_l('Submit'))
