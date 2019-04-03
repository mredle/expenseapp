# -*- coding: utf-8 -*-

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
import uuid

from app import db, login
from flask import current_app, url_for
from flask_login import UserMixin


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

    def __init__(self, db_created_by=''):
        self.db_created_at = datetime.utcnow()
        self.db_updated_at = datetime.utcnow()
        self.db_created_by = db_created_by
        self.db_updated_by = db_created_by

class Thumbnail(Entity, db.Model):
    __tablename__ = 'thumbnails'
    id = db.Column(db.Integer, primary_key=True)
    
    name = db.Column(db.String(64))
    size = db.Column(db.Integer)
    format = db.Column(db.String(8))
    mode = db.Column(db.String(8))
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    image = db.relationship('Image', foreign_keys=image_id, back_populates='thumbnails')
    
    def __init__(self, image, size):
        Entity.__init__(self, '')
        
        # Read image
        im = ImagePIL.open(image.get_path())
        im_filename, im_extension = os.path.splitext(image.name)
        self.name = im_filename + '_' + str(size) +  '.'  + current_app.config['IMAGE_DEFAULT_FORMAT']
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
        return '<Thumbnail {}px>'.format(self.name, self.size)
    
    def get_path(self):
        return os.path.join(current_app.config['IMAGE_ROOT_PATH'], 
                            current_app.config['IMAGE_TIMG_PATH'], 
                            self.name)
        
    def get_url(self):
        return os.path.join('/', current_app.config['IMAGE_TIMG_PATH'], 
                            self.name)
    

class Image(Entity, db.Model):
    __tablename__ = 'images'
    id = db.Column(db.Integer, primary_key=True)
    
    name = db.Column(db.String(64))
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    format = db.Column(db.String(8))
    mode = db.Column(db.String(8))
    original_filename = db.Column(db.String(128))
    description = db.Column(db.String(256))
    thumbnails = db.relationship('Thumbnail', foreign_keys='Thumbnail.image_id', back_populates='image', lazy='dynamic')
    
    def __init__(self, path):
        Entity.__init__(self, '')
        
        # Read image
        im = ImagePIL.open(path)
        original_path, original_filename = os.path.split(path)
        self.name = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8').replace('=', '') +  '.' + im.format
        self.original_filename = original_filename
        self.width = im.width
        self.height = im.height
        self.format = im.format
        self.mode = im.mode
        self.description = ''
        
        # Moving the image to a new file
        os.rename(path, self.get_path())
        
        
    def __repr__(self):
        return '<Image {} {}x{}px>'.format(self.name, self.width, self.height)
        
    def get_path(self):
        if self.name:
            return os.path.join(current_app.config['IMAGE_ROOT_PATH'], 
                                current_app.config['IMAGE_IMG_PATH'], 
                                self.name)
        else:
            return ''
        
    def get_url(self):
        if self.name:
            return os.path.join('/', current_app.config['IMAGE_IMG_PATH'], 
                                self.name)
        else:
            return ''
           
    def get_thumbnail(self, desired_size):
        thumbnails = self.thumbnails.order_by(Thumbnail.size.asc()).all()
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


class Currency(Entity, db.Model):
    __tablename__ = 'currencies'
    id = db.Column(db.Integer, primary_key=True)
    
    code = db.Column(db.String(3))
    name = db.Column(db.String(64))
    number = db.Column(db.Integer)
    exponent = db.Column(db.Integer)
    inCHF = db.Column(db.Float)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    image = db.relationship('Image', foreign_keys=image_id)
    description = db.Column(db.String(256))
    expenses = db.relationship('Expense', back_populates='currency', lazy='dynamic')
    settlements = db.relationship('Settlement', back_populates='currency', lazy='dynamic')
    events_base_currency = db.relationship('Event', foreign_keys='Event.base_currency_id', back_populates='base_currency', lazy='dynamic')
    
    def __init__(self, code, name, number, exponent, inCHF, description='', db_created_by=''):
        Entity.__init__(self, db_created_by)
        self.code = code
        self.name = name
        self.number = number
        self.exponent = exponent
        self.inCHF = inCHF
        self.description = description
    
    def __repr__(self):
        return '<Currency {}>'.format(self.code)
    
    def avatar(self, size):
        if self.image:
            return self.image.get_thumbnail_url(size)
        else:
            return ''
    
    def get_amount_as_str(self, amount):
        amount_str = ('{} {:.'+'{}'.format(self.exponent)+'f}').format(self.code, amount)
        return amount_str
    
    def get_amount_as_str_in(self, amount, currency):
        amount_str = ('{} {:.'+'{}'.format(self.exponent)+'f}').format(currency.code, amount*self.inCHF/currency.inCHF)
        return amount_str


event_users = db.Table('event_users',
    db.Column('event_id', db.Integer, db.ForeignKey('events.id')),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.PrimaryKeyConstraint('event_id', 'user_id')
)

class Event(Entity, db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(64))
    date = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    admin = db.relationship('User', foreign_keys=admin_id, back_populates='events_admin')
    accountant_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    accountant = db.relationship('User', foreign_keys=accountant_id, back_populates='events_accountant')
    base_currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'))
    base_currency = db.relationship('Currency', foreign_keys=base_currency_id, back_populates='events_base_currency')
    exchange_fee = db.Column(db.Float)
    users = db.relationship('User', secondary=event_users, back_populates='events', lazy='dynamic')
    closed = db.Column(db.Boolean)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    image = db.relationship('Image', foreign_keys=image_id)
    description = db.Column(db.String(256))
    expenses = db.relationship('Expense', back_populates='event', lazy='dynamic')
    settlements = db.relationship('Settlement', back_populates='event', lazy='dynamic')
    posts = db.relationship('Post', back_populates='event', lazy='dynamic')
    
    def __init__(self, name, date, admin, accountant, base_currency, exchange_fee, closed=False, description='', db_created_by=''):
        Entity.__init__(self, db_created_by)
        self.name = name
        self.date = date
        self.admin = admin
        self.accountant = accountant
        self.base_currency = base_currency
        self.exchange_fee = exchange_fee
        self.closed = closed
        self.description = description
    
    def __repr__(self):
        return '<Event {}>'.format(self.name)
        
    def avatar(self, size):
        if self.image:
            return self.image.get_thumbnail_url(size)
        else:
            return ''
    
    def has_user(self, user):
        return (user in self.users)
        
    def add_user(self, user):
        if not self.has_user(user):
            self.users.append(user)

    def remove_user(self, user):
        if self.has_user(user):
            self.users.remove(user)
            
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
        expenses_num = [x.get_amount()/x.affected_users.count() for x in expenses if user in x.affected_users]
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
                                              currency=self.base_currency, amount=-balance, draft=True, date=datetime.utcnow(), 
                                              description='Settlement to service depts', db_created_by='ExpenseApp'))
            elif balance>tolerance:
                settlements.append(Settlement(sender=self.accountant, recipient=user, event=self, 
                                              currency=self.base_currency, amount=balance, draft=True, date=datetime.utcnow(), 
                                              description='Settlement to service depts', db_created_by='ExpenseApp'))
            else:
                continue
            
        return settlements


expense_affected_users = db.Table('expense_affected_users',
    db.Column('expense_id', db.Integer, db.ForeignKey('expenses.id')),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.PrimaryKeyConstraint('expense_id', 'user_id')
)   

class Expense(Entity, db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User', back_populates='expenses')
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'))
    event = db.relationship('Event', back_populates='expenses')
    currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'))
    currency = db.relationship('Currency', back_populates='expenses')
    amount = db.Column(db.Float)
    affected_users = db.relationship('User', secondary=expense_affected_users, back_populates='affected_by_expenses', lazy='dynamic')
    date = db.Column(db.DateTime, index=True)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    image = db.relationship('Image', foreign_keys=image_id)
    description = db.Column(db.String(256))
    
    def __init__(self, user, event, currency, amount, affected_users, date, description='', db_created_by=''):
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
    
    def avatar(self, size):
        if self.image:
            return self.image.get_thumbnail_url(size)
        else:
            return '0'
        
    def get_amount(self):
        if self.currency == self.event.base_currency:
            return self.amount
        else:
            return self.amount*self.currency.inCHF/self.event.base_currency.inCHF
    
    def get_amount_str(self):
        amount_str = self.currency.get_amount_as_str(self.amount)
        
        if self.currency == self.event.base_currency:
            return amount_str
        else:
            amount_str_in = self.currency.get_amount_as_str_in(self.amount, self.event.base_currency)
            return '{} ({})'.format(amount_str, amount_str_in)
    
    def get_affected_users_str(self):
        return ', '.join([u.username for u in self.affected_users])

class Settlement(Entity, db.Model):
    __tablename__ = 'settlements'
    id = db.Column(db.Integer, primary_key=True)
    
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    sender = db.relationship('User', foreign_keys=sender_id, back_populates='settlements_sender')
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    recipient = db.relationship('User', foreign_keys=recipient_id, back_populates='settlements_recipient')
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'))
    event = db.relationship('Event', back_populates='settlements')
    currency_id = db.Column(db.Integer, db.ForeignKey('currencies.id'))
    currency = db.relationship('Currency', back_populates='settlements')
    amount = db.Column(db.Float)
    draft = db.Column(db.Boolean)
    date = db.Column(db.DateTime, index=True)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    image = db.relationship('Image', foreign_keys=image_id)
    description = db.Column(db.String(256))
    
    def __init__(self, sender, recipient, event, currency, amount, draft, date, description='', db_created_by=''):
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
    
    def avatar(self, size):
        if self.image:
            return self.image.get_thumbnail_url(size)
        else:
            return '0'
        
    def get_amount(self):
        if self.currency == self.event.base_currency:
            return self.amount
        else:
            return self.amount*self.currency.inCHF/self.event.base_currency.inCHF
    
    def get_amount_str(self):
        amount_str = self.currency.get_amount_as_str(self.amount)
        
        if self.currency == self.event.base_currency:
            return amount_str
        else:
            amount_str_in = self.currency.get_amount_as_str_in(self.amount, self.event.base_currency)
            return '{} ({})'.format(amount_str, amount_str_in)


class Post(Entity, db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    
    body = db.Column(db.String(256))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = db.relationship('User', back_populates='posts')
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'))
    event = db.relationship('Event', back_populates='posts')
    
    def __init__(self, body, timestamp, author, event, db_created_by=''):
        Entity.__init__(self, db_created_by)
        self.body = body
        self.timestamp = timestamp
        self.author = author
        self.event = event
    
    def __repr__(self):
        return '<Post {}>'.format(self.body)


class Message(Entity, db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    
    body = db.Column(db.String(256))
    timestamp = db.Column(db.DateTime, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = db.relationship('User', foreign_keys=sender_id, back_populates='messages_sent')
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    recipient = db.relationship('User', foreign_keys=recipient_id,  back_populates='messages_received')
    
    def __init__(self, body, author, recipient, db_created_by=''):
        Entity.__init__(self, db_created_by)
        self.body = body
        self.timestamp = datetime.utcnow()
        self.author = author
        self.recipient = recipient
        
    def __repr__(self):
        return '<Message {}>'.format(self.body)


class Notification(Entity, db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    
    name = db.Column(db.String(128), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User', back_populates='notifications')
    timestamp = db.Column(db.Float, index=True)
    payload_json = db.Column(db.Text)
    
    def __init__(self, name, user, payload_json, db_created_by=''):
        Entity.__init__(self, db_created_by)
        self.name = name
        self.user = user
        self.timestamp = datetime.utcnow().timestamp()
        self.payload_json = payload_json
        
    def __repr__(self):
        return '<Notification {}>'.format(self.name)
    
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
    
    def __init__(self, id, name, description, user, complete=False, db_created_by=''):
        Entity.__init__(self, db_created_by)
        self.id = id
        self.name = name
        self.description = description
        self.user = user
        self.complete = complete
        
        
    def __repr__(self):
        return '<Task {}>'.format(self.id)
    
    def get_rq_job(self):
        try:
            rq_job = rq.job.Job.fetch(self.id, connection=current_app.redis)
        except (redis.exceptions.RedisError, rq.exceptions.NoSuchJobError):
            return None
        return rq_job

    def get_progress(self):
        job = self.get_rq_job()
        return job.meta.get('progress', 0) if job is not None else 100


class User(PaginatedAPIMixin, UserMixin, Entity, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(128), index=True, unique=True)
    locale = db.Column(db.String(32))
    timezone = db.Column(db.String(32))
    password_hash = db.Column(db.String(128))
    token = db.Column(db.String(32), index=True, unique=True)
    token_expiration = db.Column(db.DateTime)
    profile_picture_id = db.Column(db.Integer, db.ForeignKey('images.id'))
    profile_picture = db.relationship('Image', foreign_keys=profile_picture_id)
    events = db.relationship('Event', secondary=event_users, back_populates='users', lazy='dynamic')
    events_admin = db.relationship('Event', foreign_keys='Event.admin_id', back_populates='admin', lazy='dynamic')
    events_accountant = db.relationship('Event', foreign_keys='Event.accountant_id', back_populates='accountant', lazy='dynamic')
    expenses = db.relationship('Expense', back_populates='user', lazy='dynamic')
    settlements_sender = db.relationship('Settlement', foreign_keys='Settlement.sender_id', back_populates='sender', lazy='dynamic')
    settlements_recipient = db.relationship('Settlement', foreign_keys='Settlement.recipient_id', back_populates='recipient', lazy='dynamic')
    affected_by_expenses = db.relationship('Expense', secondary=expense_affected_users, back_populates='affected_users', lazy='dynamic')
    posts = db.relationship('Post', back_populates='author', lazy='dynamic')
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', back_populates='author', lazy='dynamic')
    messages_received = db.relationship('Message', foreign_keys='Message.recipient_id', back_populates='recipient', lazy='dynamic')
    last_message_read_time = db.Column(db.DateTime)
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic')
    tasks = db.relationship('Task', back_populates='user', lazy='dynamic')
    
    about_me = db.Column(db.String(256))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, username, email, locale, timezone, about_me='', db_created_by=''):
        Entity.__init__(self, db_created_by)
        self.username = username
        self.email = email
        self.locale = locale
        self.timezone = timezone
        self.password_hash = ''
        self.token = ''
        self.token_expiration = datetime.utcnow() - timedelta(seconds=1)
        self.last_message_read_time = datetime.utcnow()
        self.about_me = about_me
        self.last_seen = datetime.utcnow()
        
    def __repr__(self):
        return '<User {}>'.format(self.username)
    
    def to_dict(self, include_email=False):
        data = {
            'id': self.id,
            'username': self.username,
            'last_seen': self.last_seen.isoformat() + 'Z',
            'about_me': self.about_me,
            'post_count': self.posts.count(),
            '_links': {
                'self': url_for('api.get_user', id=self.id),
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
            current_app.config['SECRET_KEY'], algorithm='HS256').decode('utf-8')

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
        rq_job = current_app.task_queue.enqueue('app.tasks.' + name, self.id,
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

@login.user_loader
def load_user(id):
    return User.query.get(int(id))
