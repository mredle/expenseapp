"""Main blueprint forms: profile editing, user management, currencies, and messages."""

from __future__ import annotations

from flask_babel import _, lazy_gettext as _l
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    FloatField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp, ValidationError

from app import images
from app.models import User


class ImageForm(FlaskForm):
    """Upload form for a single image."""

    image = FileField(_l('Picture'), validators=[FileAllowed(images, _l('Images only!'))])
    submit = SubmitField(_l('Submit'))


class EditProfileForm(FlaskForm):
    """Edit the current user's own profile."""

    username = StringField(_l('Username'), validators=[DataRequired(), Regexp(r'^[\w.]+$')])
    about_me = TextAreaField(_l('About me'), validators=[Length(min=0, max=256)])
    locale = SelectField(_l('Language'), validators=[DataRequired()])
    submit = SubmitField(_l('Submit'))

    def __init__(self, original_username: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username) -> None:
        """Reject duplicate usernames."""
        if username.data != self.original_username:
            user = User.query.filter_by(username=self.username.data).first()
            if user is not None:
                raise ValidationError(_('Please use a different username.'))


class MessageForm(FlaskForm):
    """Send a direct message to another user."""

    recipient_id = SelectField(_l('Recipient'), coerce=int, validators=[DataRequired()])
    message = TextAreaField(_l('Message'), validators=[DataRequired(), Length(min=0, max=256)])
    submit = SubmitField(_l('Submit'))


class CurrencyForm(FlaskForm):
    """Create or edit an ISO-4217 currency."""

    name = StringField(_l('Name'), validators=[DataRequired(), Length(min=0, max=256)])
    code = StringField(_l('ISO-4217-Code'), validators=[DataRequired(), Length(min=3, max=3)])
    number = IntegerField(_l('ISO-4217-Number'), validators=[DataRequired()])
    exponent = IntegerField(_l('ISO-4217-Exponent'), validators=[DataRequired()])
    inCHF = FloatField(_l('Value in CHF'), validators=[DataRequired()])
    description = TextAreaField(_l('Description'), validators=[Length(min=0, max=256)])
    submit = SubmitField(_l('Submit'))


class NewUserForm(FlaskForm):
    """Admin form to create a new user."""

    username = StringField(_l('Username'), validators=[DataRequired(), Regexp(r'^[\w.]+$')])
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    password2 = PasswordField(_l('Repeat Password'), validators=[DataRequired(), EqualTo('password')])
    about_me = TextAreaField(_l('About me'), validators=[Length(min=0, max=256)])
    locale = SelectField(_l('Language'), validators=[DataRequired()])
    is_admin = BooleanField(_l('Administrator'))
    submit = SubmitField(_l('Submit'))

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


class EditUserForm(FlaskForm):
    """Admin form to edit an existing user."""

    username = StringField(_l('Username'), validators=[DataRequired(), Regexp(r'^[\w.]+$')])
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Password'), validators=[])
    password2 = PasswordField(_l('Repeat Password'), validators=[EqualTo('password')])
    about_me = TextAreaField(_l('About me'), validators=[Length(min=0, max=256)])
    locale = SelectField(_l('Language'), validators=[DataRequired()])
    is_admin = BooleanField(_l('Administrator'))
    submit = SubmitField(_l('Submit'))

    def __init__(self, original_username: str, original_email: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.original_username = original_username
        self.original_email = original_email

    def validate_username(self, username) -> None:
        """Reject duplicate usernames."""
        if username.data != self.original_username:
            user = User.query.filter_by(username=self.username.data).first()
            if user is not None:
                raise ValidationError(_('Please use a different username.'))

    def validate_email(self, email) -> None:
        """Reject duplicate email addresses."""
        if email.data.lower() != self.original_email:
            user = User.query.filter_by(email=self.email.data).first()
            if user is not None:
                raise ValidationError(_('Please use a different email address.'))
