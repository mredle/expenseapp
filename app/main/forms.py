# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm
from flask_babel import _, lazy_gettext as _l
from wtforms import StringField, SubmitField, TextAreaField, SelectField, SelectMultipleField, IntegerField, FloatField
from wtforms.validators import ValidationError, DataRequired, Length
from wtforms.fields.html5 import DateField

from app.models import User
    
class EditProfileForm(FlaskForm):
    username = StringField(_l('Username'), 
                           validators=[DataRequired()])
    about_me = TextAreaField(_l('About me'), 
                             validators=[Length(min=0, max=256)])
    submit = SubmitField(_l('Submit'))
    
    def __init__(self, original_username, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=self.username.data).first()
            if user is not None:
                raise ValidationError(_('Please use a different username.'))

class PostForm(FlaskForm):
    post = TextAreaField(_l('Say something'), 
                         validators=[
        DataRequired(), Length(min=1, max=256)])
    submit = SubmitField(_l('Submit'))

class MessageForm(FlaskForm):
    message = TextAreaField(_l('Message'), 
                            validators=[DataRequired(), Length(min=0, max=256)])
    submit = SubmitField(_l('Submit'))

class CurrencyForm(FlaskForm):
    name = StringField(_l('Name'), 
                       validators=[DataRequired(), Length(min=0, max=256)])
    code = StringField(_l('ISO-4217-Code'), 
                       validators=[DataRequired(), Length(min=3, max=3)])
    number = IntegerField(_l('ISO-4217-Number'), 
                          validators=[DataRequired()])
    exponent = IntegerField(_l('ISO-4217-Exponent'), 
                            validators=[DataRequired()])
    inCHF = FloatField(_l('Value in CHF'), 
                       validators=[DataRequired()])
    description = TextAreaField(_l('Description'), 
                                validators=[Length(min=0, max=256)])
    submit = SubmitField(_l('Submit'))

class EventForm(FlaskForm):
    name = StringField(_l('Name'), 
                       validators=[DataRequired(), Length(min=0, max=256)])
    date = DateField(_l('Date in Y-m-d'), 
                        format='%Y-%m-%d', 
                        validators=[DataRequired()])
    description = TextAreaField(_l('Description'), 
                                validators=[Length(min=0, max=256)])
    admin_id = SelectField(_l('Change admin user'), coerce=int,
                          validators=[DataRequired()])
    accountant_id = SelectField(_l('Change accountant user'), coerce=int,
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
