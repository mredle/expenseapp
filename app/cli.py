# -*- coding: utf-8 -*-

import os
import click
from app import create_app, db
from app.models import Currency, User
from config import Config

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
    @click.option('--overwrite/--no-overwrite', default=False, help='Overwrite existing currencies.')
    def currency(overwrite):
        """Initialize currencies with predefined values."""
        created_by = 'flask dbinit currency' 
        
        # Fill currencies with example values
        currencies = []
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
            existing_currency = Currency.query.filter_by(code=currency.code).first()
            if existing_currency:
                if overwrite:
                    existing_currency.code = currency.code
                    existing_currency.name = currency.name
                    existing_currency.number = currency.number
                    existing_currency.exponent = currency.exponent
                    existing_currency.inCHF = currency.inCHF 
                    existing_currency.description = currency.description
                    existing_currency.db_created_by = currency.db_created_by
                    db.session.commit()
            else:
                currencies.append(currency)
                db.session.add(currency)
                db.session.commit()
            
    @dbinit.command()
    @click.option('--overwrite/--no-overwrite', default=False, help='Overwrite existing admin.')
    def admin(overwrite):
        """Initialize admin with password taken from environment variables."""
        created_by = 'flask dbinit admin'
        app = create_app(Config)
        
        # look for existing admin account
        existing_admin_user = User.query.filter_by(username='admin').first()
        
        if existing_admin_user:
            if overwrite:
                existing_admin_user.username = app.config['ADMIN_USERNAME']
                existing_admin_user.email = app.config['ADMIN_EMAIL']
                existing_admin_user.about_me = 'I am the mighty admin!'
                existing_admin_user.db_created_by = created_by
                existing_admin_user.set_password(app.config['ADMIN_PASSWORD'])
                existing_admin_user.get_token()
                db.session.commit()
        else:
            admin_user = User(username = app.config['ADMIN_USERNAME'], 
                              email = app.config['ADMIN_EMAIL'], 
                              about_me = 'I am the mighty admin!', 
                              db_created_by = created_by)
            admin_user.set_password(app.config['ADMIN_PASSWORD'])
            admin_user.get_token()
            db.session.add(admin_user)
            db.session.commit()
        
        
        