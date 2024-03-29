# -*- coding: utf-8 -*-

from flask_babel import _
from sqlalchemy.orm import validates
from sqlalchemy.types import TypeDecorator, CHAR, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy_utils.types.uuid import UUIDType
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from hashlib import md5
from time import time
from PIL import Image as ImagePIL
import jwt
import json
import redis
import rq
import base64
import os
import shutil
import uuid
import mimetypes

from app import db, login
from flask import current_app, url_for
from flask_login import UserMixin

from webauthn.helpers.structs import AuthenticatorTransport

class FIDO2Transports(TypeDecorator):
    """Convert a list of enums into a string for storage"""

    impl = String(64)

    def process_bind_param(self, value, dialect):
        if not isinstance(value, list):
            raise TypeError("FIDO2Transports columns support only list values.")
        return ','.join(value)

    def process_result_value(self, value, dialect):
        return [AuthenticatorTransport(x) for x in value.split(',')] if value else None

class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.

    """
    impl = CHAR
    cache_ok = True
    
    def __repr__(self):
        return self.impl.__repr__()

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value).int
            else:
                # hexstring
                return "%.32x" % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


class PaginatedAPIMixin(object):
    @staticmethod
    def to_collection_dict(query, page, per_page, endpoint, **kwargs):
        resources = query.paginate(page, per_page, False)
        data = {
            'items': [item.to_dict() for item in resources.items],
            '_meta': {
                'page': page,
                'per_page': per_page,
                'total_pages': resources.pages,
                'total_items': resources.total
            },
            '_links': {
                'self': url_for(endpoint, page=page, per_page=per_page,
                                **kwargs),
                'next': url_for(endpoint, page=page + 1, per_page=per_page,
                                **kwargs) if resources.has_next else None,
                'prev': url_for(endpoint, page=page - 1, per_page=per_page,
                                **kwargs) if resources.has_prev else None
            }
        }
        return data


class Entity():
    db_created_at = db.Column(db.DateTime)
    db_updated_at = db.Column(db.DateTime)
    db_created_by = db.Column(db.String(64))
    db_updated_by = db.Column(db.String(64))
    guid = db.Column(UUIDType(binary=False), default=uuid.uuid4, index=True, unique=True)

    def __init__(self, db_created_by='SYSTEM'):
        self.db_created_at = datetime.utcnow()
        self.db_updated_at = datetime.utcnow()
        self.db_created_by = db_created_by
        self.db_updated_by = db_created_by
    
    @classmethod
    def get_by_guid_or_404(cls, guid):
        return cls.query.filter(cls.guid==guid).first_or_404()
    

class Log(db.Model):
    __tablename__ = 'log'
    id = db.Column(db.Integer, primary_key=True)
    
    severity = db.Column(db.String(32))
    module = db.Column(db.String(128))
    msg_type = db.Column(db.String(128))
    msg = db.Column(db.String(256))
    trace = db.Column(db.String(4096))
    date = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User', back_populates='logs')
    
    def __init__(self, severity, module, msg_type, msg, user, trace=None):
        self.severity = severity
        self.module = module
        self.msg_type = msg_type
        self.msg = msg
        self.trace = trace
        self.user = user
    
    def __repr__(self):
        return '<{} log from {} at {}: {}>'.format(self.severity, self.user.username, self.date, self.msg)
    
    def can_view(self, user):
        return (user.is_admin or user==self.user) if user.is_authenticated else False
    
    @classmethod
    def get_class_stats(cls, user=None):
        description = _('Log entries')
        filters = []
        if not (user is None or user.is_admin):
            filters.append(cls.user==user)
        number = cls.query.filter(*filters).count()
        return [(description, number)]
        
class Thumbnail(Entity, db.Model):
    __tablename__ = 'thumbnails'
    id = db.Column(db.Integer, primary_key=True)
    
    name = db.Column(db.String(64), index=True)
    extension = db.Column(db.String(8))
    size = db.Column(db.Integer)
    format = db.Column(db.String(8))
    mode = db.Column(db.String(8))
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'), index=True)
    image = db.relationship('Image', foreign_keys=image_id, back_populates='thumbnails')
    
    def __init__(self, image, size):
        Entity.__init__(self)
        
        # Read image
        if not image.vector:
            im = ImagePIL.open(image.get_path())
            if im.mode=='RGBA':
                background = ImagePIL.new('RGB', im.size, (255, 255, 255))
                background.paste(im, mask=im.split()[3]) # 3 is the alpha channel
                im = background
                
            self.name = image.name + '_' + str(size)
            self.extension = '.' + current_app.config['IMAGE_DEFAULT_FORMAT']
            self.size = size
            self.format = current_app.config['IMAGE_DEFAULT_FORMAT']
            self.mode = im.mode
            self.image = image
            
            # Saving the thumbnail to a new file
            max_size = max((image.width, image.height))
            if size < max_size:
                im.thumbnail((size, size))
            im.save(self.get_path(), format=current_app.config['IMAGE_DEFAULT_FORMAT'])
    
    def __repr__(self):
        return '<Thumbnail {} {}x{}px>'.format(self.name, self.size, self.size)
        
    @classmethod
    def get_class_stats(cls, user=None):
        description = _('Thumbnails')
        number = cls.query.count()
        return [(description, number)]
    
    def get_path(self):
        return os.path.join(current_app.config['IMAGE_ROOT_PATH'], 
                            current_app.config['IMAGE_TIMG_PATH'], 
                            self.name + (self.extension if self.extension is not None else ''))
        
    def get_url(self):
        return os.path.join('/', current_app.config['IMAGE_TIMG_PATH'], 
                            self.name + (self.extension if self.extension is not None else ''))
    

class Image(Entity, db.Model):
    __tablename__ = 'images'
    id = db.Column(db.Integer, primary_key=True)
    
    name = db.Column(db.String(64), index=True)
    extension = db.Column(db.String(8))
    vector = db.Column(db.Boolean)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    height = db.Column(db.Integer)
    rotate = db.Column(db.Integer)
    format = db.Column(db.String(8))
    mode = db.Column(db.String(8))
    original_filename = db.Column(db.String(128))
    description = db.Column(db.String(256))
    thumbnails = db.relationship('Thumbnail', foreign_keys='Thumbnail.image_id', back_populates='image', lazy='dynamic')
    
    def import_properties(self, path):
        # Read image
        mime_type = mimetypes.guess_type(path)[0]
        if mime_type=='image/svg+xml':
            self.vector = True
            self.width = 0
            self.height = 0
            self.rotate = 0
            self.format = 'SVG'
            self.mode = 'RGB'
        else:
            im = ImagePIL.open(path)
            self.vector = False
            self.width = im.width
            self.height = im.height
            self.rotate = 0
            self.format = im.format
            self.mode = im.mode
            
        original_path, original_filename = os.path.split(path)
        self.original_filename = original_filename
        self.extension = '.' + self.format
        self.description = ''
    
    def __init__(self, path, keep_original=False, name=None):
        Entity.__init__(self)
        self.import_properties(path)
        
        if name is None:
            self.name = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8').replace('=', '')
        else:
            self.name = name
        
        # Moving the image to a new file
        if keep_original:
            shutil.copy(path, self.get_path())
        else:
            shutil.move(path, self.get_path())
    
    def __repr__(self):
        return '<Image {} {}x{}px>'.format(self.name, self.width, self.height)
        
    @classmethod
    def get_class_stats(cls, user=None):
        description = _('Images')
        number = cls.query.count()
        return [(description, number)]
       
    def rotate_image(self, degree):
        self.rotate = (self.rotate+degree)%360
        
    def get_html_scale(self):
        if self.rotate in (90,270) and self.width>self.height:
            return self.height/self.width
        elif self.rotate in (90,270) and self.width<self.height:
            return self.width/self.height
        else:
            return 1
       
    def update(self, path, keep_original=False, name=None):
        # Remove old file
        os.remove(self.get_path())
        
        self.import_properties(path)
        
        if name is not None:
            self.name = name
            
        # Moving the image to a new file
        if keep_original:
            shutil.copy(path, self.get_path())
        else:
            shutil.move(path, self.get_path())
     
    def get_path(self):
        if self.name:
            return os.path.join(current_app.config['IMAGE_ROOT_PATH'], 
                                current_app.config['IMAGE_IMG_PATH'], 
                                self.name + (self.extension if self.extension is not None else ''))
        else:
            return ''
        
    def get_url(self):
        if self.name:
            return os.path.join('/', current_app.config['IMAGE_IMG_PATH'], 
                                self.name + (self.extension if self.extension is not None else ''))
        else:
            return ''
           
    def get_thumbnail(self, desired_size):
        thumbnails = self.thumbnails.order_by(Thumbnail.size.asc()).all()
        if not self.vector:
            for thumbnail in thumbnails:
                if thumbnail.size > desired_size:
                    return thumbnail
        return None
        
    def get_thumbnail_url(self, desired_size):
        thumbnail = self.get_thumbnail(desired_size)
        if thumbnail:
            return thumbnail.get_url()
        else:
            return self.get_url()


class EventCurrency(db.Model):
    __tablename__ = 'event_currencies'
    
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), primary_key=True)
    event = db.relationship('Event', back_populates='eventcurrencies')
    currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'), primary_key=True)
    currency = db.relationship('Currency', back_populates='eventcurrencies')
    inCHF = db.Column(db.Float)

    def __init__(self, currency):
        self.currency = currency
        self.inCHF = currency.inCHF
        
    def __repr__(self):
        return '<EventCurrency {}>'.format(self.currency.code)
        
    @classmethod
    def get_class_stats(cls, user=None):
        description = _('Event currencies')
        filters = []
        if not (user is None or user.is_admin):
            events = Event.query.filter(Event.admin==user).all()
            filters.append(cls.event_id.in_([e.id for e in events]))
        number = cls.query.filter(*filters).count()
        return [(description, number)]
     
    def get_amount_in(self, amount, eventcurrency, exchange_fee):
        if self == eventcurrency:
            return amount
        else:
            return (1+exchange_fee/100)*amount*self.inCHF/eventcurrency.inCHF
    
    def get_amount_as_str(self, amount):
        amount_str = ('{} {:.'+'{}'.format(self.currency.exponent)+'f}').format(self.currency.code, amount)
        return amount_str
    
    def get_amount_as_str_in(self, amount, eventcurrency, exchange_fee):
        amount_str = ('{} {:.'+'{}'.format(self.currency.exponent)+'f}').format(eventcurrency.currency.code, self.get_amount_in(amount, eventcurrency, exchange_fee))
        return amount_str

class Currency(Entity, db.Model):
    __tablename__ = 'currencies'
    id = db.Column(db.Integer, primary_key=True)
    
    code = db.Column(db.String(3), index=True)
    name = db.Column(db.String(64))
    number = db.Column(db.Integer)
    exponent = db.Column(db.Integer)
    inCHF = db.Column(db.Float)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    image = db.relationship('Image', foreign_keys=image_id)
    source = db.Column(db.String(32))
    description = db.Column(db.String(256))
    expenses = db.relationship('Expense', back_populates='currency', lazy='dynamic')
    settlements = db.relationship('Settlement', back_populates='currency', lazy='dynamic')
    eventcurrencies = db.relationship('EventCurrency', back_populates='currency', lazy='dynamic', cascade='all, delete-orphan')
    events = association_proxy('eventcurrencies', 'event')
    #events = db.relationship('Event', secondary='event_currencies', back_populates='currencies', lazy='dynamic')
    events_base_currency = db.relationship('Event', foreign_keys='Event.base_currency_id', back_populates='base_currency', lazy='dynamic')
    
    def __init__(self, code, name, number, exponent, inCHF, description='', db_created_by='SYSTEM'):
        Entity.__init__(self, db_created_by)
        self.code = code
        self.name = name
        self.number = number
        self.exponent = exponent
        self.inCHF = inCHF
        self.description = description
    
    def __repr__(self):
        return '<Currency {}>'.format(self.code)
        
    @classmethod
    def get_class_stats(cls, user=None):
        description = _('Currencies')
        number = cls.query.count()
        return [(description, number)]
    
    def can_edit(self, user):
        return user.is_admin
    
    def avatar(self, size):
        if self.image:
            return self.image.get_thumbnail_url(size)
        else:
            return ''
        

class Event(Entity, db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(64))
    date = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    admin = db.relationship('User', foreign_keys=admin_id, back_populates='events_admin')
    accountant_id = db.Column(db.Integer, db.ForeignKey('eventusers.id'))
    accountant = db.relationship('EventUser', foreign_keys=accountant_id, back_populates='events_accountant')
    base_currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'))
    base_currency = db.relationship('Currency', foreign_keys=base_currency_id, back_populates='events_base_currency')
    base_eventcurrency = db.relationship('EventCurrency', primaryjoin='and_(foreign(Event.id)==remote(EventCurrency.event_id), foreign(Event.base_currency_id)==remote(EventCurrency.currency_id))')
    exchange_fee = db.Column(db.Float)
    users = db.relationship('EventUser', foreign_keys='EventUser.event_id', back_populates='event', lazy='dynamic')
    eventcurrencies = db.relationship('EventCurrency', back_populates='event', lazy='dynamic', cascade='all, delete-orphan')
    currencies = association_proxy('eventcurrencies', 'currency')
    #currencies = db.relationship('Currency', secondary='event_currencies', back_populates='events', lazy='dynamic')
    closed = db.Column(db.Boolean)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    image = db.relationship('Image', foreign_keys=image_id)
    description = db.Column(db.String(256))
    fileshare_link = db.Column(db.String(256))
    expenses = db.relationship('Expense', back_populates='event', lazy='dynamic')
    settlements = db.relationship('Settlement', back_populates='event', lazy='dynamic')
    posts = db.relationship('Post', back_populates='event', lazy='dynamic')
    
    def __init__(self, name, date, admin, base_currency, currencies, exchange_fee, fileshare_link, closed=False, description='', db_created_by='SYSTEM'):
        Entity.__init__(self, db_created_by)
        self.name = name
        self.date = date
        self.admin = admin
        self.base_currency = base_currency
        self.eventcurrencies = [EventCurrency(c) for c in currencies]
        self.exchange_fee = exchange_fee
        self.closed = closed
        self.fileshare_link = fileshare_link
        self.description = description
    
    def __repr__(self):
        return '<Event {}>'.format(self.name)
        
    @classmethod
    def get_class_stats(cls, user=None):
        description = _('Events')
        filters = []
        if not (user is None or user.is_admin):
            filters.append(cls.admin==user)
        number = cls.query.filter(*filters).count()
        return [(description, number)]
    
    def can_edit(self, user):
        return (user.is_admin or user==self.admin) if user.is_authenticated else False
        
    def avatar(self, size):
        if self.image:
            return self.image.get_thumbnail_url(size)
        else:
            return ''
        
    def get_stats(self):
        stats = {'users': self.users.count(),
                 'posts': self.posts.count(),
                 'expenses': self.expenses.count(),
                 'settlements': self.settlements.filter_by(draft=False).count()}
        return stats
    
    def has_user(self, user):
        return (user in self.users)
        
    def add_user(self, user):
        if not self.has_user(user):
            self.users.append(user)

    def remove_user(self, user):
        blocked_users = set([x.user for x in self.expenses] +
                            [x.sender for x in self.settlements] +
                            [x.recipient for x in self.settlements])
        
        if self.has_user(user) and user not in blocked_users:
            self.users.remove(user)
            return 0
        else:
            return 1
        
    def has_currency(self, currency):
        return (currency in self.currencies)
        
    def add_currency(self, currency):
        if not self.has_currency(currency):
            self.currencies.append(currency)

    def remove_currency(self, currency):
        blocked_currencies = set([x.currency for x in self.expenses] +
                            [x.currency for x in self.settlements] +
                            [self.base_currency])
        
        if self.has_currency(currency) and currency not in blocked_currencies:
            self.currencies.remove(currency)
            return 0
        else:
            return 1
    
    def convert_currencies_to_base(self):
        expenses = self.expenses.all()
        settlements = self.settlements.all()
        
        for x in expenses:
            x.amount = x.eventcurrency.get_amount_in(x.amount, self.base_eventcurrency, self.exchange_fee)
            x.currency = self.base_currency
            
        for x in settlements:
            x.amount = x.eventcurrency.get_amount_in(x.amount, self.base_eventcurrency, self.exchange_fee)
            x.currency = self.base_currency
            
    def get_currencies_str(self):
        currency_codes = [c.code for c in self.currencies]
        currency_codes.sort()
        return ', '.join(currency_codes)
                         
    def get_total_expenses(self):
        expenses = self.expenses.all()
        expenses_num = [x.get_amount() for x in expenses]
        return sum(expenses_num)
            
    def get_amount_paid(self, user):
        expenses = self.expenses.filter_by(user=user).all()
        expenses_num = [x.get_amount() for x in expenses]
        return sum(expenses_num)
    
    def get_amount_spent(self, user):
        expenses = self.expenses.all()
        expenses_num = [user.weighting*x.get_amount()/sum([u.weighting for u in x.affected_users.all()]) for x in expenses if user in x.affected_users]
        return sum(expenses_num)
    
    def get_amount_sent(self, user):
        settlements = self.settlements.filter_by(sender=user, draft=False).all()
        settlements_num = [x.get_amount() for x in settlements]
        return sum(settlements_num)
    
    def get_amount_received(self, user):
        settlements = self.settlements.filter_by(recipient=user, draft=False).all()
        settlements_num = [x.get_amount() for x in settlements]
        return sum(settlements_num)
    
    def get_user_balance(self, user):
        amount_paid = self.get_amount_paid(user)
        amount_spent = self.get_amount_spent(user)
        amount_sent = self.get_amount_sent(user)
        amount_received = self.get_amount_received(user)
        balance = amount_paid - amount_spent + amount_sent - amount_received
        return (user, amount_paid, amount_spent, amount_sent, amount_received, balance)
    
    def get_compensation_settlements_accountant(self):
        users = [u for u in self.users if u != self.accountant]
        settlements = []
        tolerance = 10**-self.base_currency.exponent
        
        for user in users:
            balance_item = self.get_user_balance(user)
            balance = balance_item[5]
            if balance<-tolerance:
                settlements.append(Settlement(sender=user, recipient=self.accountant, event=self, 
                                              currency=self.base_currency, amount=-balance, draft=True, date=datetime.utcnow()))
            elif balance>tolerance:
                settlements.append(Settlement(sender=self.accountant, recipient=user, event=self, 
                                              currency=self.base_currency, amount=balance, draft=True, date=datetime.utcnow()))
            else:
                continue
            
        return settlements
    
    def calculate_balance(self):
        self.settlements.filter_by(draft=True).delete()
        draft_settlements = self.get_compensation_settlements_accountant()
        db.session.add_all(draft_settlements)
        db.session.commit()
        return draft_settlements
    
    def get_balance(self):
        balances = [self.get_user_balance(u) for u in self.users]
        balances_str = list(map(lambda x: (x[0], 
                                           self.base_eventcurrency.get_amount_as_str(x[1]), 
                                           self.base_eventcurrency.get_amount_as_str(x[2]), 
                                           self.base_eventcurrency.get_amount_as_str(x[3]), 
                                           self.base_eventcurrency.get_amount_as_str(x[4]), 
                                           self.base_eventcurrency.get_amount_as_str(x[5])) 
                                           , balances))
        
        total_expenses = self.get_total_expenses()
        total_expenses_str = self.base_eventcurrency.get_amount_as_str(total_expenses)
        return (balances_str, total_expenses_str)

expense_affected_users = db.Table('expense_affected_users',
    db.Column('expense_id', db.Integer, db.ForeignKey('expenses.id')),
    db.Column('user_id', db.Integer, db.ForeignKey('eventusers.id')),
    db.PrimaryKeyConstraint('expense_id', 'user_id')
)   

class Expense(Entity, db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('eventusers.id'), index=True)
    user = db.relationship('EventUser', back_populates='expenses')
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), index=True)
    event = db.relationship('Event', back_populates='expenses')
    currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'))
    currency = db.relationship('Currency', back_populates='expenses')
    eventcurrency = db.relationship('EventCurrency', primaryjoin='and_(foreign(Expense.event_id)==remote(EventCurrency.event_id), foreign(Expense.currency_id)==remote(EventCurrency.currency_id))')
    amount = db.Column(db.Float)
    affected_users = db.relationship('EventUser', secondary=expense_affected_users, back_populates='affected_by_expenses', lazy='dynamic')
    date = db.Column(db.DateTime, index=True)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    image = db.relationship('Image', foreign_keys=image_id)
    description = db.Column(db.String(256))
    
    def __init__(self, user, event, currency, amount, affected_users, date, description='', db_created_by='SYSTEM'):
        Entity.__init__(self, db_created_by)
        self.user = user
        self.event = event
        self.currency = currency
        self.amount = amount
        self.affected_users = affected_users
        self.date = date
        self.description = description
    
    def __repr__(self):
        return '<Expense {}{}>'.format(self.amount, self.currency.code)
        
    @classmethod
    def get_class_stats(cls, user=None):
        description = _('Expenses')
        filters = []
        if not (user is None or user.is_admin):
            filters.append(cls.user==user)
        number = cls.query.filter(*filters).count()
        return [(description, number)]
    
    def avatar(self, size):
        if self.image:
            return self.image.get_thumbnail_url(size)
        else:
            return ''
    
    def can_edit(self, user, eventuser):
        return (user==eventuser.event.admin) if user.is_authenticated else (eventuser==self.user and not eventuser.event.closed)
        
    def has_user(self, user):
        return (user in self.affected_users)
        
    def add_user(self, user):
        if not self.has_user(user):
            self.affected_users.append(user)
            
    def add_users(self, users):
        for user in users:
            self.add_user(user)

    def remove_user(self, user):
        if self.has_user(user):
            self.affected_users.remove(user)
            return 0
        else:
            return 1
        
    def get_amount(self):
        return self.eventcurrency.get_amount_in(self.amount, self.event.base_eventcurrency, self.event.exchange_fee)
    
    def get_amount_str(self):
        amount_str = self.eventcurrency.get_amount_as_str(self.amount)
        
        if self.currency == self.event.base_currency:
            return amount_str
        else:
            amount_str_in = self.eventcurrency.get_amount_as_str_in(self.amount, self.event.base_eventcurrency, self.event.exchange_fee)
            return '{} ({})'.format(amount_str, amount_str_in)

class Settlement(Entity, db.Model):
    __tablename__ = 'settlements'
    id = db.Column(db.Integer, primary_key=True)
    
    sender_id = db.Column(db.Integer, db.ForeignKey('eventusers.id'), index=True)
    sender = db.relationship('EventUser', foreign_keys=sender_id, back_populates='settlements_sender')
    recipient_id = db.Column(db.Integer, db.ForeignKey('eventusers.id'), index=True)
    recipient = db.relationship('EventUser', foreign_keys=recipient_id, back_populates='settlements_recipient')
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), index=True)
    event = db.relationship('Event', back_populates='settlements')
    currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'))
    currency = db.relationship('Currency', back_populates='settlements')
    eventcurrency = db.relationship('EventCurrency', primaryjoin='and_(foreign(Settlement.event_id)==remote(EventCurrency.event_id), foreign(Settlement.currency_id)==remote(EventCurrency.currency_id))')
    amount = db.Column(db.Float)
    draft = db.Column(db.Boolean)
    date = db.Column(db.DateTime, index=True)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    image = db.relationship('Image', foreign_keys=image_id)
    description = db.Column(db.String(256))
    
    def __init__(self, sender, recipient, event, currency, amount, draft, date, description='', db_created_by='SYSTEM'):
        Entity.__init__(self, db_created_by)
        self.sender = sender
        self.recipient = recipient
        self.event = event
        self.currency = currency
        self.amount = amount
        self.draft = draft
        self.date = date
        self.description = description
    
    def __repr__(self):
        return '<Settlement {}{}>'.format(self.amount, self.currency.code)
        
    @classmethod
    def get_class_stats(cls, user=None):
        filters = []
        if not (user is None or user.is_admin):
            filters.append(cls.sender==user)
        number_s = cls.query.filter(*filters).count()
        filters = []
        if not (user is None or user.is_admin):
            filters.append(cls.recipient==user)
        number_r = cls.query.filter(*filters).count()
        return [(_('Settlements as sender'), number_s), (_('Settlements as recipient'), number_r)]
    
    def avatar(self, size):
        if self.image:
            return self.image.get_thumbnail_url(size)
        else:
            return ''
    
    def can_edit(self, user, eventuser):
        return (user==eventuser.event.admin) if user.is_authenticated else (eventuser==self.recipient and not eventuser.event.closed)
        
    def get_amount(self):
        return self.eventcurrency.get_amount_in(self.amount, self.event.base_eventcurrency, self.event.exchange_fee)
    
    def get_amount_str(self):
        amount_str = self.eventcurrency.get_amount_as_str(self.amount)
        
        if self.currency == self.event.base_currency:
            return amount_str
        else:
            amount_str_in = self.eventcurrency.get_amount_as_str_in(self.amount, self.event.base_eventcurrency, self.event.exchange_fee)
            return '{} ({})'.format(amount_str, amount_str_in)


class Post(Entity, db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    
    body = db.Column(db.String(256))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('eventusers.id'), index=True)
    author = db.relationship('EventUser', back_populates='posts')
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), index=True)
    event = db.relationship('Event', back_populates='posts')
    
    def __init__(self, body, timestamp, author, event, db_created_by='SYSTEM'):
        Entity.__init__(self, db_created_by)
        self.body = body
        self.timestamp = timestamp
        self.author = author
        self.event = event
    
    def __repr__(self):
        return '<Post {}>'.format(self.body)
        
    @classmethod
    def get_class_stats(cls, user=None):
        description = _('Posts')
        filters = []
        if not (user is None or user.is_admin):
            filters.append(cls.author==user)
        number = cls.query.filter(*filters).count()
        return [(description, number)]
    

class Message(Entity, db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    
    body = db.Column(db.String(256))
    timestamp = db.Column(db.DateTime, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    author = db.relationship('User', foreign_keys=sender_id, back_populates='messages_sent')
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    recipient = db.relationship('User', foreign_keys=recipient_id,  back_populates='messages_received')
    
    def __init__(self, body, author, recipient, db_created_by='SYSTEM'):
        Entity.__init__(self, db_created_by)
        self.body = body
        self.timestamp = datetime.utcnow()
        self.author = author
        self.recipient = recipient
        
    def __repr__(self):
        return '<Message {}>'.format(self.body)
        
    @classmethod
    def get_class_stats(cls, user=None):
        filters = []
        if not (user is None or user.is_admin):
            filters.append(cls.author==user)
        number_s = cls.query.filter(*filters).count()
        filters = []
        if not (user is None or user.is_admin):
            filters.append(cls.recipient==user)
        number_r = cls.query.filter(*filters).count()
        return [(_('Messages sent'), number_s), (_('Messages received'), number_r)]
    

class Notification(Entity, db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    
    name = db.Column(db.String(128), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User', back_populates='notifications')
    timestamp = db.Column(db.Float, index=True)
    payload_json = db.Column(db.Text)
    
    def __init__(self, name, user, payload_json, db_created_by='SYSTEM'):
        Entity.__init__(self, db_created_by)
        self.name = name
        self.user = user
        self.timestamp = datetime.utcnow().timestamp()
        self.payload_json = payload_json
        
    def __repr__(self):
        return '<Notification {}>'.format(self.name)
        
    @classmethod
    def get_class_stats(cls, user=None):
        description = _('Notifications')
        filters = []
        if not (user is None or user.is_admin):
            filters.append(cls.user==user)
        number = cls.query.filter(*filters).count()
        return [(description, number)]
    
    def get_data(self):
        return json.loads(str(self.payload_json))


class Task(Entity, db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.String(36), primary_key=True)
    
    name = db.Column(db.String(128), index=True)
    description = db.Column(db.String(128))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User', back_populates='tasks')
    complete = db.Column(db.Boolean, default=False)
    
    def __init__(self, id, name, description, user, complete=False, db_created_by='SYSTEM'):
        Entity.__init__(self, db_created_by)
        self.id = id
        self.name = name
        self.description = description
        self.user = user
        self.complete = complete
        
        
    def __repr__(self):
        return '<Task {} from {}: {}>'.format(self.id, self.user.username, ('Done' if self.complete else 'Unfinished'))
        
    @classmethod
    def get_class_stats(cls, user=None):
        description = _('Tasks')
        filters = []
        if not (user is None or user.is_admin):
            filters.append(cls.user==user)
        number = cls.query.filter(*filters).count()
        return [(description, number)]
    
    def can_edit(self, user):
        return (not self.complete and ((user.is_admin or user==self.user) if user.is_authenticated else False))
    
    def get_rq_job(self):
        try:
            rq_job = rq.job.Job.fetch(self.id, connection=current_app.redis)
        except (redis.exceptions.RedisError, rq.exceptions.NoSuchJobError):
            return None
        return rq_job

    def get_progress(self):
        job = self.get_rq_job()
        return job.meta.get('progress', 0) if job is not None else 100


class Credential(Entity, db.Model):
    __tablename__ = 'credential'
    pk = db.Column(db.Integer, primary_key=True)
    id = db.Column(db.LargeBinary)
    public_key = db.Column(db.LargeBinary)
    sign_count = db.Column(db.Integer)
    transports = db.Column(FIDO2Transports)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    user = db.relationship('User', back_populates='credentials')

    def __init__(self, id, public_key, sign_count, transports, user, db_created_by='SYSTEM'):
        Entity.__init__(self, db_created_by)
        self.id = id
        self.public_key = public_key
        self.sign_count = sign_count
        self.transports = transports
        self.user = user

    def __repr__(self):
        return '<Credential: {}>'.format(self.id)

class Challenge(Entity, db.Model):
    __tablename__ = 'challenge'
    pk = db.Column(db.Integer, primary_key=True)
    challenge = db.Column(db.LargeBinary)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    user = db.relationship('User', back_populates='challenges')

    def __init__(self, challenge):
        Entity.__init__(self)
        self.challenge = challenge

    def __repr__(self):
        return '<Challenge: {}>'.format(self.session)

class User(PaginatedAPIMixin, UserMixin, Entity, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(128), index=True, unique=True)
    locale = db.Column(db.String(32))
    password_hash = db.Column(db.String(128))
    token = db.Column(db.String(32), index=True, unique=True)
    token_expiration = db.Column(db.DateTime)
    profile_picture_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    profile_picture = db.relationship('Image', foreign_keys=profile_picture_id)
    events_admin = db.relationship('Event', foreign_keys='Event.admin_id', back_populates='admin', lazy='dynamic')
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', back_populates='author', lazy='dynamic')
    messages_received = db.relationship('Message', foreign_keys='Message.recipient_id', back_populates='recipient', lazy='dynamic')
    last_message_read_time = db.Column(db.DateTime)
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic')
    tasks = db.relationship('Task', foreign_keys='Task.user_id', back_populates='user', lazy='dynamic')
    logs = db.relationship('Log', foreign_keys='Log.user_id', back_populates='user', lazy='dynamic')
    credentials = db.relationship('Credential', back_populates='user')
    challenges = db.relationship('Challenge', back_populates='user')

    is_admin = db.Column(db.Boolean)
    about_me = db.Column(db.String(256))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    @validates('email')
    def convert_lower(self, field, value):
        if isinstance(value, str):
            return value.lower()
        else:
            return value[0].lower()
    
    def __init__(self, username, email, locale, about_me='', db_created_by='SYSTEM'):
        Entity.__init__(self, db_created_by)
        self.username = username
        self.email = email
        self.locale = locale
        self.password_hash = ''
        self.token = ''
        self.token_expiration = datetime.utcnow() - timedelta(seconds=1)
        self.last_message_read_time = datetime.utcnow()
        self.is_admin = False
        self.about_me = about_me
        self.last_seen = datetime.utcnow()
        
    def __repr__(self):
        return '<User {}>'.format(self.username)
        
    @classmethod
    def get_class_stats(cls, user=None):
        description = _('Users')
        number = cls.query.count()
        return [(description, number)]
    
    def to_dict(self, include_email=False):
        data = {
            'id': self.id,
            'username': self.username,
            'last_seen': self.last_seen.isoformat() + 'Z',
            'about_me': self.about_me,
            'post_count': self.posts.count(),
            '_links': {
                'self': url_for('apis.users_api_user', id=self.id),
                'avatar': self.avatar(128)
            }
        }
        if include_email:
            data['email'] = self.email
        return data
    
    def from_dict(self, data, new_user=False):
        for field in ['username', 'email', 'about_me']:
            if field in data:
                setattr(self, field, data[field])
        if new_user and 'password' in data:
            self.set_password(data['password'])
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def set_random_password(self):
        password_tmp = base64.b64encode(os.urandom(24)).decode('utf-8')
        self.password_hash = generate_password_hash(password_tmp)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            current_app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, current_app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)
    
    def avatar(self, size):
        if self.profile_picture:
            return self.profile_picture.get_thumbnail_url(size)
        else:
            return self.gravatar(size)
    
    def gravatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(
            digest, size)
    
    def new_messages(self):
        last_read_time = self.last_message_read_time or datetime(1900, 1, 1)
        return Message.query.filter_by(recipient=self).filter(
            Message.timestamp > last_read_time).count()
        
    def add_notification(self, name, data):
        self.notifications.filter_by(name=name).delete()
        n = Notification(name=name, payload_json=json.dumps(data), user=self)
        db.session.add(n)
        return n
    
    def launch_task(self, name, description, *args, **kwargs):
        rq_job = current_app.task_queue.enqueue('app.tasks.' + name, self.guid,
                                                *args, **kwargs)
        task = Task(id=rq_job.get_id(), name=name, description=description,
                    user=self)
        db.session.add(task)
        return task

    def get_tasks_in_progress(self):
        return Task.query.filter_by(user=self, complete=False).all()

    def get_task_in_progress(self, name):
        return Task.query.filter_by(name=name, user=self,
                                    complete=False).first()
    
    def get_token(self, expires_in=3600):
        now = datetime.utcnow()
        if self.token and self.token_expiration > now + timedelta(seconds=60):
            return self.token
        self.token = base64.b64encode(os.urandom(24)).decode('utf-8')
        self.token_expiration = now + timedelta(seconds=expires_in)
        db.session.add(self)
        return self.token

    def revoke_token(self):
        self.token_expiration = datetime.utcnow() - timedelta(seconds=1)

    @staticmethod
    def check_token(token):
        user = User.query.filter_by(token=token).first()
        if user is None or user.token_expiration < datetime.utcnow():
            return None
        return user

class EventUser(Entity, db.Model):
    __tablename__ = 'eventusers'
    id = db.Column(db.Integer, primary_key=True)
    
    # user data
    username = db.Column(db.String(64), index=True)
    email = db.Column(db.String(128), index=True)
    weighting = db.Column(db.Float)
    locale = db.Column(db.String(32))
    about_me = db.Column(db.String(256))
    
    # bank account data
    iban = db.Column(db.String(34))
    bank = db.Column(db.String(64))
    name = db.Column(db.String(64))
    address = db.Column(db.String(128))
    address_suffix = db.Column(db.String(128))
    zip_code = db.Column(db.Integer)
    city = db.Column(db.String(64))
    country = db.Column(db.String(64))
    
    # twint data
    
    # relationships
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), index=True)
    event = db.relationship('Event', foreign_keys=event_id, back_populates='users')
    events_accountant = db.relationship('Event', foreign_keys='Event.accountant_id', back_populates='accountant', lazy='dynamic')
    profile_picture_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    profile_picture = db.relationship('Image', foreign_keys=profile_picture_id)
    expenses = db.relationship('Expense', back_populates='user', lazy='dynamic')
    settlements_sender = db.relationship('Settlement', foreign_keys='Settlement.sender_id', back_populates='sender', lazy='dynamic')
    settlements_recipient = db.relationship('Settlement', foreign_keys='Settlement.recipient_id', back_populates='recipient', lazy='dynamic')
    affected_by_expenses = db.relationship('Expense', secondary=expense_affected_users, back_populates='affected_users', lazy='dynamic')
    posts = db.relationship('Post', back_populates='author', lazy='dynamic')
    
    @validates('email')
    def convert_lower(self, field, value):
        if isinstance(value, str):
            return value.lower()
        else:
            return value[0].lower()
    
    def __init__(self, username, email, weighting, locale, about_me='', db_created_by='SYSTEM'):
        Entity.__init__(self, db_created_by)
        self.username = username
        self.email = email
        self.weighting = weighting
        self.locale = locale
        self.about_me = about_me
        
    def __repr__(self):
        return '<EventUser {}>'.format(self.username)
        
    @classmethod
    def get_class_stats(cls, user=None):
        description = _('Event users')
        filters = []
        if not (user is None or user.is_admin):
            events = Event.query.filter(Event.admin==user).all()
            filters.append(cls.event_id.in_([e.id for e in events]))
        number = cls.query.filter(*filters).count()
        return [(description, number)]
    
    def avatar(self, size):
        if self.profile_picture:
            return self.profile_picture.get_thumbnail_url(size)
        else:
            return self.gravatar(size)
    
    def gravatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(
            digest, size)
    
@login.user_loader
def load_user(id):
    return User.query.get(int(id))
