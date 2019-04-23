# -*- coding: utf-8 -*-

import os
import sys
import click
import time
import csv
from app import create_app, db
from app.models import Currency, User, Image
from app.tasks import create_thumbnails
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
    @click.option('--interval', default=5, help='Polling interval in seconds')
    @click.option('--timeout', default=60, help='Timeout in seconds')
    def wait4db(interval, timeout):
        timer = 0
        while timer<timeout:
            time.sleep(interval)
            timer = timer + interval
            try:
                User.query.filter_by(username='admin').first()
            except ConnectionRefusedError:
                continue
            except:
                print('Unexpected error:', sys.exc_info()[0])
                raise
            return
        raise SystemExit('DB timeout after {}s'.format(timeout))
    
    @dbinit.command()
    @click.option('--overwrite/--no-overwrite', default=False, help='Overwrite existing currencies.')
    def currencies(overwrite):
        """Initialize currencies with predefined values."""
        
        # Fill currencies from CSV file
        currencies = []
        with open('app/resources/currencies.csv', 'r', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=';')
            line_count = 0
            for row in csv_reader:
                if line_count == 0:
                    line_count += 1
                else:
                    line_count += 1
                    if len(row[1])>64:
                        na = row[1][0:64]
                    else:
                        na = row[1]
                    try:
                        e = int(row[4])
                    except ValueError:
                        e = 0
                    
                    try:
                        nu = int(row[3])
                    except ValueError:
                        nu = 0
                     
                    c = Currency(code = row[2].upper(), 
                                 name = na, 
                                 number = nu, 
                                 exponent = e, 
                                 inCHF = 1, 
                                 description = row[0], 
                                 db_created_by = 'flask dbinit currency')
                    currencies.append(c)
        
        for currency in currencies:
            existing_currency = Currency.query.filter_by(code=currency.code).first()
            if existing_currency:
                if overwrite:
                    existing_currency.code = currency.code
                    existing_currency.name = currency.name
                    existing_currency.number = currency.number
                    existing_currency.exponent = currency.exponent
                    existing_currency.description = currency.description
                    existing_currency.db_created_by = currency.db_created_by
                    db.session.commit()
            else:
                db.session.add(currency)
                db.session.commit()
    
    @dbinit.command()
    @click.option('--overwrite/--no-overwrite', default=False, help='Overwrite existing flags.')
    def currency_flags(overwrite):
        """Initialize currency flags."""
        
        # Update flags
        flag_path = os.path.join(app.config['IMAGE_ROOT_PATH'], 'resources', 'flags')
        existing_currencies = Currency.query.all()
        for currency in existing_currencies:
            country_code = currency.code[0:2].upper()
            url = os.path.join(flag_path, country_code + '.svg')
            if currency.image:
                if overwrite:
                    try:
                        currency.image.update(url, keep_original=True, name=country_code)
                        currency.image.description = 'Static image'
                        if not currency.image.vector:
                            create_thumbnails(currency.image)
                        db.session.commit()
                    except:
                        print('Adding flag for {} failed'.format(country_code))
                        db.session.rollback()
            else:
                try:
                    image = Image(url, keep_original=True, name=country_code)
                    image.description = 'Static image'
                    if not image.vector:
                        create_thumbnails(image)
                    currency.image = image
                    db.session.commit()
                except:
                    print('Adding flag for {} failed'.format(country_code))
                    db.session.rollback()
                    
    @dbinit.command()
    @click.option('--overwrite/--no-overwrite', default=False, help='Overwrite existing flags.')
    @click.option('--subfolder', default='', help='Subfolder for icons')
    def icons(overwrite, subfolder):
        """Initialize icons."""
        
        # Update icons
        icon_path = os.path.join(app.config['IMAGE_ROOT_PATH'], 'resources', subfolder)
        files = [f for f in os.listdir(icon_path) if f.endswith('.svg')]
        for file in files:
            url = os.path.join(icon_path, file)
            name = os.path.splitext(file)[0]
            existing_image = Image.query.filter_by(name=name).first()
            if existing_image:
                if overwrite:
                    try:
                        existing_image.update(url, keep_original=True, name=name)
                        existing_image.description = 'Static image'
                        if not existing_image.vector:
                            create_thumbnails(existing_image)
                        db.session.commit()
                    except:
                        print('Updating icon {} failed'.format(file))
                        db.session.rollback()
            else:
                try:
                    image = Image(url, keep_original=True, name=name)
                    image.description = 'Static image'
                    if not image.vector:
                        create_thumbnails(image)
                    db.session.add(image)
                    db.session.commit()
                except:
                    print('Adding icon {} failed'.format(file))
                    db.session.rollback()
    
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
                existing_admin_user.db_created_by = created_by
                existing_admin_user.is_admin = True
                existing_admin_user.set_password(app.config['ADMIN_PASSWORD'])
                existing_admin_user.get_token()
                db.session.commit()
        else:
            admin_user = User(username = app.config['ADMIN_USERNAME'], 
                              email = app.config['ADMIN_EMAIL'], 
                              locale = app.config['LANGUAGES'][0],
                              timezone = app.config['TIMEZONES'][0],
                              about_me = 'I am the mighty admin!', 
                              db_created_by = created_by)
            admin_user.is_admin = True
            admin_user.set_password(app.config['ADMIN_PASSWORD'])
            admin_user.get_token()
            db.session.add(admin_user)
            db.session.commit()
        
    @dbinit.command()
    @click.option('--count', default=3, help='Number of dummy users to create.')
    def dummyusers(count):
        """Create dummy users for development."""
        created_by = 'flask dummy --count {}'.format(count) 
            
        # Fill users with dummy values
        n_users = count
        users = []
        existing_usernames = [user.username for user in  User.query.all()]
        existing_emails = [user.email for user in  User.query.all()]
        for i_user in range(0, n_users):
            user = User(username = 'User'+str(i_user), 
                        email = 'user'+str(i_user)+'@email.net', 
                        locale = 'en', 
                        timezone = 'Etc/UTC',
                        about_me = 'blablablabla from the life of User'+str(i_user), 
                        db_created_by = created_by)
            user.set_password(user.username)
            if (user.username not in existing_usernames) and (user.email not in existing_emails):
                user.get_token()
                users.append(user)
                db.session.add(user)
        db.session.commit()
        
