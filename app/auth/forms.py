"""Authentication forms: login, registration, password reset, and FIDO2."""

from __future__ import annotations

from flask_babel import _, lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Regexp, ValidationError

from app.models import User


class AuthenticatePasswordForm(FlaskForm):
    """Username / password login form."""

    username = StringField(_l('Username'), validators=[DataRequired()])
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    remember_me = BooleanField(_l('Remember Me'))
    submit = SubmitField(_l('Sign In'))


class RegistrationForm(FlaskForm):
    """New-user registration form."""

    username = StringField(_l('Username'), validators=[DataRequired(), Regexp(r'^[\w.]+$')])
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    locale = SelectField(_l('Language'), validators=[DataRequired()])
    submit = SubmitField(_l('Register'))

    def validate_username(self, username) -> None:
        """Reject duplicate usernames."""
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError(_('Please use a different username.'))

    def validate_email(self, email) -> None:
        """Reject duplicate email addresses."""
        user = User.query.filter_by(email=email.data.lower()).first()
        if user is not None:
            raise ValidationError(_('Please use a different email address.'))


class ResetUserRequestForm(FlaskForm):
    """Request a password / authentication reset."""

    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    submit = SubmitField(_l('Request Password Reset'))


class RegisterFIDO2Form(FlaskForm):
    """Display-only form shown during FIDO2 device registration."""

    email = StringField(_l('Email'), render_kw={'readonly': True})


class RegisterPasswordForm(FlaskForm):
    """Set a new password after token validation."""

    password = PasswordField(_l('Password'), validators=[DataRequired()])
    password2 = PasswordField(
        _l('Repeat Password'),
        validators=[DataRequired(), EqualTo('password')],
    )
    submit = SubmitField(_l('Set password'))
