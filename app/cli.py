# -*- coding: utf-8 -*-

import os
import sys
import click
import redis
import boto3
import time
import csv
import uuid
from datetime import datetime
from sqlalchemy.sql import text
from sqlalchemy import inspect
from flask import current_app
from app import create_app, db
from app.models import Thumbnail, Image, Currency, Event, EventUser, Post, Expense, Settlement, User, Message, Notification, Task
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
                        if not currency.image.is_vector:
                            create_thumbnails(currency.image)
                        db.session.commit()
                    except:
                        print('Adding flag for {} failed'.format(country_code))
                        db.session.rollback()
            else:
                try:
                    image = Image(url, keep_original=True, name=country_code)
                    image.description = 'Static image'
                    if not image.is_vector:
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
                        if not existing_image.is_vector:
                            create_thumbnails(existing_image)
                        db.session.commit()
                    except:
                        print('Updating icon {} failed'.format(file))
                        db.session.rollback()
            else:
                try:
                    image = Image(url, keep_original=True, name=name)
                    image.description = 'Static image'
                    if not image.is_vector:
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
        
        # look for existing anonymous account
        existing_anonymous_user = User.query.filter_by(username='anonymous').first()
        
        if existing_anonymous_user:
            if overwrite:
                existing_anonymous_user.username ='anonymous'
                existing_anonymous_user.email = 'anonymous@mystery.ch'
                existing_anonymous_user.db_created_by = created_by
                existing_anonymous_user.is_admin = False
                existing_anonymous_user.set_random_password()
                existing_anonymous_user.get_token()
                db.session.commit()
        else:
            anonymous_user = User(username = 'anonymous', 
                                  email = 'anonymous@mystery.ch', 
                                  locale = app.config['LANGUAGES'][0],
                                  about_me = 'I am the unknown user!', 
                                  db_created_by = created_by)
            anonymous_user.is_admin = False
            anonymous_user.set_random_password()
            anonymous_user.get_token()
            db.session.add(anonymous_user)
            
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
        created_by = 'flask dummyusers --count {}'.format(count) 
            
        # Fill users with dummy values
        n_users = count
        existing_usernames = [user.username for user in  User.query.all()]
        existing_emails = [user.email for user in  User.query.all()]
        for i_user in range(0, n_users):
            user = User(username = 'User'+str(i_user), 
                        email = 'user'+str(i_user)+'@email.net', 
                        locale = 'en', 
                        about_me = 'blablablabla from the life of User'+str(i_user), 
                        db_created_by = created_by)
            user.set_password(user.username)
            if (user.username not in existing_usernames) and (user.email not in existing_emails):
                user.get_token()
                db.session.add(user)
        db.session.commit()
                
                
    @app.cli.group()
    def dbmaint():
        """Commands for database maintenance."""
        pass
    
    @dbmaint.command()
    def add_missing_guid():
        """Fill table with missing guid"""
        updated_by = 'flask dbmaint add_missing_guid'
            
        # Fill table with missing guid
        def class_add_missing_guid(UserClass):
            instances = UserClass.query.filter(UserClass.guid.is_(None)).all()
            
            for instance in instances:
                instance.db_updated_by = updated_by
                instance.db_updated_at = datetime.utcnow()
                instance.guid = uuid.uuid4();
                
            db.session.commit()
        
        class_add_missing_guid(Event)
        class_add_missing_guid(Thumbnail) 
        class_add_missing_guid(Image) 
        class_add_missing_guid(Currency) 
        class_add_missing_guid(Event) 
        class_add_missing_guid(Post) 
        class_add_missing_guid(Expense) 
        class_add_missing_guid(Settlement) 
        class_add_missing_guid(User) 
        class_add_missing_guid(EventUser) 
        class_add_missing_guid(Message) 
        class_add_missing_guid(Notification)
        class_add_missing_guid(Task)
    
    @app.cli.command("flush-media-cache")
    def flush_media_cache():
        """Clear all cached images from Redis."""
        # Connect to Redis using your app config
        r = redis.Redis(
            host=current_app.config.get('REDIS_HOST', 'localhost'),
            port=current_app.config.get('REDIS_PORT', 6379),
            db=current_app.config.get('REDIS_DB', 0),
            password=current_app.config.get('REDIS_PASSWORD')
        )
        
        # Find all keys matching our media cache pattern
        keys = r.keys('media_cache:*')
        
        if keys:
            # Delete them all in a single batch operation
            r.delete(*keys)
            click.echo(f"Successfully flushed {len(keys)} media files from Redis cache.")
        else:
            click.echo("Redis media cache is already empty.")

    @app.cli.command("flush-s3")
    def flush_s3():
        """Delete all objects and folders in the S3 bucket."""
        bucket_name = current_app.config.get('S3_BUCKET_NAME')
        if not bucket_name:
            click.echo("S3_BUCKET_NAME is not configured.")
            return

        click.echo(f"Connecting to S3 to empty bucket '{bucket_name}'...")
        
        try:
            # We use boto3.resource here because it provides a high-level API 
            # for batch deleting all objects in a bucket efficiently
            s3 = boto3.resource(
                's3',
                region_name=current_app.config.get('S3_REGION'),
                endpoint_url=current_app.config.get('S3_ENDPOINT_URL')
            )
            bucket = s3.Bucket(bucket_name)
            
            # S3 doesn't technically have folders, just objects with '/' in their keys.
            # Deleting all objects automatically removes the "folders".
            deleted = bucket.objects.all().delete()
            
            if deleted:
                count = sum(len(batch.get('Deleted', [])) for batch in deleted)
                click.echo(f"Successfully deleted {count} objects/folders from S3.")
            else:
                click.echo("Bucket is already empty.")
                
        except Exception as e:
            click.echo(f"Error emptying S3 bucket: {e}")

    @app.cli.command("flush-db")
    def flush_db():
        """Completely drop all tables, data, indexes, and constraints."""
        from app import db # Import db locally to avoid circular imports
        
        click.echo("WARNING: Dropping all database tables...")
        try:
            # 1. Disable foreign key checks so MariaDB doesn't block dropping tables with relations
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            
            # 2. Reflect the current state of the database to find ALL tables
            db.metadata.reflect(bind=db.engine)
            
            # 3. Drop them all
            db.metadata.drop_all(bind=db.engine)
            
            # 4. Re-enable foreign key checks for future queries
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            db.session.commit()
            
            click.echo("Successfully wiped the entire database (tables, content, indexes).")
            
        except Exception as e:
            db.session.rollback()
            click.echo(f"Error flushing database: {e}")
    
    @app.cli.command("flush-db-force")
    def flush_db_force():
        """Completely drop all tables, data, indexes, and constraints."""
        from app import db 
        
        click.echo("WARNING: Dropping all database tables...")
        try:
            # 1. Disable foreign key checks so MariaDB allows the drops
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            
            # 2. Bypass SQLAlchemy's sorting by getting raw table names from the DB
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            # 3. Drop each table manually using raw SQL
            for table in tables:
                db.session.execute(text(f"DROP TABLE IF EXISTS `{table}`;"))
                click.echo(f"Dropped table: {table}")
            
            # 4. Re-enable foreign key checks
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            db.session.commit()
            
            click.echo("Successfully wiped the entire database (tables, content, indexes).")
            
        except Exception as e:
            db.session.rollback()
            click.echo(f"Error flushing database: {e}")