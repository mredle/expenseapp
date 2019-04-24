# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm
from flask_babel import _, lazy_gettext as _l
from wtforms import StringField, SubmitField, TextAreaField, SelectField, SelectMultipleField, FloatField
from wtforms.validators import DataRequired, Length
from wtforms.fields.html5 import DateField


class PostForm(FlaskForm):
    post = TextAreaField(_l('Say something'), 
                         validators=[DataRequired(), Length(min=1, max=256)])
    submit = SubmitField(_l('Submit'))

class EventForm(FlaskForm):
    name = StringField(_l('Name'), 
                       validators=[DataRequired(), Length(min=0, max=256)])
    date = DateField(_l('Date in Y-m-d'), 
                        format='%Y-%m-%d', 
                        validators=[DataRequired()])
    
    description = TextAreaField(_l('Description'), 
                                validators=[Length(min=0, max=256)])
    admin_id = SelectField(_l('Administrator'), coerce=int,
                          validators=[DataRequired()])
    accountant_id = SelectField(_l('Accountant'), coerce=int,
                          validators=[DataRequired()])
    base_currency_id = SelectField(_l('Base currency'), coerce=int,
                          validators=[DataRequired()])
    exchange_fee = FloatField(_l('Exchange fee (%)'), 
                       validators=[DataRequired()])
    submit = SubmitField(_l('Submit'))
    
class EventAddUserForm(FlaskForm):
    user_id = SelectField(_l('Add user'), coerce=int,
                          validators=[DataRequired()])
    submit = SubmitField(_l('Submit'))

class ExpenseForm(FlaskForm):
    currency_id = SelectField(_l('Currency'), coerce=int,
                              validators=[DataRequired()])
    amount = FloatField(_l('Amount'), 
                        validators=[DataRequired()])
    affected_users_id = SelectMultipleField(_l('Affected Users'), coerce=int,
                              validators=[DataRequired()])
    date = DateField(_l('Date'), 
                         format='%Y-%m-%d', 
                         validators=[DataRequired()])
    description = TextAreaField(_l('Description'), 
                                validators=[Length(min=0, max=256)])
    submit = SubmitField(_l('Submit'))
    
class SettlementForm(FlaskForm):
    currency_id = SelectField(_l('Currency'), coerce=int,
                              validators=[DataRequired()])
    amount = FloatField(_l('Amount'), 
                        validators=[DataRequired()])
    recipient_id = SelectField(_l('Recipient'), coerce=int,
                               validators=[DataRequired()])
    description = TextAreaField(_l('Description'), 
                                validators=[Length(min=0, max=256)])
    submit = SubmitField(_l('Submit'))

