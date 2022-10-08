# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm
from flask_babel import _, lazy_gettext as _l
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Regexp

from app.models import User

class AuthenticatePasswordForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired()])
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    remember_me = BooleanField(_l('Remember Me'))
    submit = SubmitField(_l('Sign In'))

class RegistrationForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired(), Regexp(r'^[\w.]+$')])
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    locale = SelectField(_l('Language'), validators=[DataRequired()])
    submit = SubmitField(_l('Register'))

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError(_('Please use a different username.'))

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data.lower()).first()
        if user is not None:
            raise ValidationError(_('Please use a different email address.'))

class ResetUserRequestForm(FlaskForm):
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    submit = SubmitField(_l('Request Password Reset'))

class RegisterFIDO2Form(FlaskForm):
    email = StringField(_l('Email'), render_kw={'readonly': True})

class RegisterPasswordForm(FlaskForm):
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    password2 = PasswordField(_l('Repeat Password'), 
                              validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField(_l('Set password'))
