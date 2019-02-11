# -*- coding: utf-8 -*-

import os
import click
import random
from datetime import datetime, timedelta
from app import db
from app.models import Currency, Event, Post, Expense, Settlement, User, Message

def register(app):
    @app.cli.group()
    def translate():
        """Translation and localization commands."""
        pass

    @translate.command()
    @click.argument('lang')
    def init(lang):
        """Initialize a new language."""
        if os.system('pybabel extract -F babel.cfg -k _l -o messages.pot .'):
            raise RuntimeError('extract command failed')
        if os.system(
                'pybabel init -i messages.pot -d app/translations -l ' + lang):
            raise RuntimeError('init command failed')
        os.remove('messages.pot')

    @translate.command()
    def update():
        """Update all languages."""
        if os.system('pybabel extract -F babel.cfg -k _l -o messages.pot .'):
            raise RuntimeError('extract command failed')
        if os.system('pybabel update -i messages.pot -d app/translations'):
            raise RuntimeError('update command failed')
        os.remove('messages.pot')

    @translate.command()
    def compile():
        """Compile all languages."""
        if os.system('pybabel compile -d app/translations'):
            raise RuntimeError('compile command failed')

    @app.cli.group()
    def dbinit():
        """Commands to initialize the database."""
        pass

    @dbinit.command()
    @click.option('--count', default=3, help='Number of dummy users to create.')
    def dummy(count):
        """Initialize with dummy data."""
        created_by = 'flask dummy --count {}'.format(count) 
            
        # Fill users with dummy values
        n_users = count
        users = []
        existing_usernames = [user.username for user in  User.query.all()]
        existing_emails = [user.email for user in  User.query.all()]
        for i_user in range(0, n_users):
            user = User(username = 'User'+str(i_user), 
                        email = 'user'+str(i_user)+'@email.ch', 
                        about_me = 'blablablabla from the life of User'+str(i_user), 
                        db_created_by = created_by)
            user.set_password(user.username)
            if (user.username not in existing_usernames) and (user.email not in existing_emails):
                user.get_token()
                users.append(user)
                db.session.add(user)
        db.session.commit()
        
        # Fill currencies with example values
        currencies = []
        existing_currencies = [currency.code for currency in Currency.query.all()]
        currency1 = Currency(code = 'CHF', 
                             name = 'Schweizer Franken', 
                             number = 756, 
                             exponent = 2, 
                             inCHF = 1, 
                             description = 'Schweiz, Liechtenstein', 
                             db_created_by = created_by)
        currency2 = Currency(code = 'EUR', 
                             name = 'Euro', 
                             number = 978, 
                             exponent = 2, 
                             inCHF = 1.15, 
                             description = 'Europäische Währungsunion', 
                             db_created_by = created_by)
        currency3 = Currency(code = 'USD', 
                             name = 'US-Dollar', 
                             number = 840, 
                             exponent = 2, 
                             inCHF = 0.99, 
                             description = 'Vereinigte Staaten', 
                             db_created_by = created_by)
        
        for currency in [currency1, currency2, currency3]:
            if currency.code not in existing_currencies:
                currencies.append(currency)
                db.session.add(currency)
        db.session.commit()
            
        # Fill events with dummy values
        n_events = count
        i_event = 0
        events = []
        existing_events = [e.name for e in Event.query.all()]
        for user in users:
            for i_event_tmp in range(0, n_events):
                i_event = i_event + 1
                event = Event(name = 'Event'+str(i_event)+' created by user '+user.username, 
                             date = datetime.utcnow() - timedelta(weeks=i_event),
                             admin = user,
                             accountant = user,
                             closed = False, 
                             description = 'Blablabla funny event nr '+str(i_event), 
                             db_created_by = created_by)
                if event.name not in existing_events:
                    events.append(event)
                    db.session.add(event)
                    event.add_user(user)
        db.session.commit()
        
        # Add all users to all events
        for event in events:
            for user in users:
                event.add_user(user)
        db.session.commit()

        # Fill posts with dummy values
        n_posts = count
        for event in events:
            for user in users:
                for i_post in range(0, n_posts):
                    ptmp = Post(body = 'post '+str(i_post)+' from user '+user.username+' in event '+event.name, 
                                timestamp = datetime.utcnow() - timedelta(days=i_post), 
                                author = user, 
                                event = event,
                                db_created_by = created_by)
                    db.session.add(ptmp)
        db.session.commit()
        
        # Fill messages with dummy values
        i_message = 0
        for sender in users:
            for recipient in users:
                mtmp = Message(body = 'Message '+str(i_message)+' from user '+sender.username+' to user '+recipient.username+'.', 
                            author = sender, 
                            recipient = recipient, 
                            db_created_by = created_by)
                db.session.add(mtmp)
                i_message = i_message+1
        db.session.commit()
        
        # Fill expenses with dummy values
        i_expense = 0
        for event in events:
            for user in users:
                for currency in currencies:
                    ptmp = Expense(user = user, 
                                   event = event, 
                                   currency = currency, 
                                   amount = float(random.randint(100, 1e5)/100),  
                                   affected_users = event.users,
                                   date = datetime.utcnow() - timedelta(hours=i_expense), 
                                   description = 'Blablabla nobody knows why be bought it nr '+str(i_expense), 
                                   db_created_by = created_by)
                    db.session.add(ptmp)
                    i_expense = i_expense+1
        db.session.commit()
