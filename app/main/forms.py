# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from flask_babel import _, lazy_gettext as _l
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, IntegerField, FloatField, BooleanField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Length, Regexp

from app import images
from app.models import User

class ImageForm(FlaskForm): 
    image = FileField(_l('Picture'), validators=[FileAllowed(images, _l('Images only!'))])
    submit = SubmitField(_l('Submit'))

class EditProfileForm(FlaskForm):
    username = StringField(_l('Username'), 
                           validators=[DataRequired(), Regexp(r'^[\w.]+$')])
    about_me = TextAreaField(_l('About me'), 
                             validators=[Length(min=0, max=256)])
    locale = SelectField(_l('Language'), validators=[DataRequired()])
    timezone = SelectField(_l('Timezone'), validators=[DataRequired()])
    submit = SubmitField(_l('Submit'))
    
    def __init__(self, original_username, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=self.username.data).first()
            if user is not None:
                raise ValidationError(_('Please use a different username.'))

class MessageForm(FlaskForm):
    recipient_id = SelectField(_l('Recipient'), coerce=int,
                          validators=[DataRequired()])
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

class NewUserForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired(), Regexp(r'^[\w.]+$')])
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    password2 = PasswordField(_l('Repeat Password'), 
                              validators=[DataRequired(), EqualTo('password')])
    about_me = TextAreaField(_l('About me'), 
                             validators=[Length(min=0, max=256)])
    locale = SelectField(_l('Language'), validators=[DataRequired()])
    is_admin = BooleanField(_l('Administrator'))
    submit = SubmitField(_l('Submit'))

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError(_('Please use a different username.'))

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data.lower()).first()
        if user is not None:
            raise ValidationError(_('Please use a different email address.'))
            
class EditUserForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired(), Regexp(r'^[\w.]+$')])
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Password'), validators=[])
    password2 = PasswordField(_l('Repeat Password'), 
                              validators=[EqualTo('password')])
    about_me = TextAreaField(_l('About me'), 
                             validators=[Length(min=0, max=256)])
    locale = SelectField(_l('Language'), validators=[DataRequired()])
    is_admin = BooleanField(_l('Administrator'))
    submit = SubmitField(_l('Submit'))

    def __init__(self, original_username, original_email, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        self.original_username = original_username
        self.original_email = original_email

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=self.username.data).first()
            if user is not None:
                raise ValidationError(_('Please use a different username.'))
                
    def validate_email(self, email):
        if email.data.lower() != self.original_email:
            user = User.query.filter_by(email=self.email.data).first()
            if user is not None:
                raise ValidationError(_('Please use a different email address.'))
