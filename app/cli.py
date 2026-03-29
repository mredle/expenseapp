"""Flask CLI commands for translation, database init, maintenance, and cache management."""

from __future__ import annotations

import csv
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import boto3
import click
import redis
from flask import current_app
from sqlalchemy import inspect
from sqlalchemy.sql import text

from app import create_app, db
from app.models import (
    Currency,
    Event,
    EventUser,
    Expense,
    Image,
    Message,
    Notification,
    Post,
    Settlement,
    Task,
    Thumbnail,
    User,
)
from app.tasks import create_thumbnails
from config import Config


def register(app) -> None:  # noqa: C901 — CLI registration is inherently complex
    """Register all CLI commands on *app*."""

    # ------------------------------------------------------------------
    # Translation commands
    # ------------------------------------------------------------------

    @app.cli.group()
    def translate():
        """Translation and localization commands."""
        pass

    @translate.command()
    @click.argument('lang')
    def init(lang: str) -> None:
        """Initialize a new language."""
        if os.system('pybabel extract -F babel.cfg -k _l -o messages.pot .'):
            raise RuntimeError('extract command failed')
        if os.system(f'pybabel init -i messages.pot -d app/translations -l {lang}'):
            raise RuntimeError('init command failed')
        os.remove('messages.pot')

    @translate.command()
    def update() -> None:
        """Update all languages."""
        if os.system('pybabel extract -F babel.cfg -k _l -o messages.pot .'):
            raise RuntimeError('extract command failed')
        if os.system('pybabel update -i messages.pot -d app/translations'):
            raise RuntimeError('update command failed')
        os.remove('messages.pot')

    @translate.command()
    def compile() -> None:
        """Compile all languages."""
        if os.system('pybabel compile -d app/translations'):
            raise RuntimeError('compile command failed')

    # ------------------------------------------------------------------
    # Database initialisation commands
    # ------------------------------------------------------------------

    @app.cli.group()
    def dbinit():
        """Commands to initialize the database."""
        pass

    @dbinit.command()
    @click.option('--interval', default=5, help='Polling interval in seconds')
    @click.option('--timeout', default=60, help='Timeout in seconds')
    def wait4db(interval: int, timeout: int) -> None:
        """Wait for the database to become available."""
        timer = 0
        while timer < timeout:
            time.sleep(interval)
            timer += interval
            try:
                User.query.filter_by(username='admin').first()
            except ConnectionRefusedError:
                continue
            except Exception:
                print('Unexpected error:', sys.exc_info()[0])
                raise
            return
        raise SystemExit(f'DB timeout after {timeout}s')

    @dbinit.command()
    @click.option('--overwrite/--no-overwrite', default=False, help='Overwrite existing currencies.')
    def currencies(overwrite: bool) -> None:
        """Initialize currencies with predefined values."""
        currencies_list: list[Currency] = []
        with open('app/resources/currencies.csv', 'r', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=';')
            line_count = 0
            for row in csv_reader:
                if line_count == 0:
                    line_count += 1
                else:
                    line_count += 1
                    na = row[1][:64] if len(row[1]) > 64 else row[1]
                    try:
                        e = int(row[4])
                    except ValueError:
                        e = 0
                    try:
                        nu = int(row[3])
                    except ValueError:
                        nu = 0

                    c = Currency(
                        code=row[2].upper(),
                        name=na,
                        number=nu,
                        exponent=e,
                        inCHF=1,
                        description=row[0],
                        db_created_by='flask dbinit currency',
                    )
                    currencies_list.append(c)

        for currency in currencies_list:
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

        click.echo('Successfully updated the currencies.')

    @dbinit.command()
    @click.option('--overwrite/--no-overwrite', default=False, help='Overwrite existing flags.')
    def currency_flags(overwrite: bool) -> None:
        """Initialize currency flags."""
        from app.models import File
        from app.storage import get_storage_provider

        storage = get_storage_provider(current_app.config['STORAGE_DEFAULT_BACKEND'])
        flag_path = os.path.join(current_app.config['IMAGE_ROOT_PATH'], 'resources', 'flags')
        existing_currencies = Currency.query.all()

        for currency in existing_currencies:
            country_code = currency.code[:2].upper()
            filename = f'{country_code}.svg'
            filepath = os.path.join(flag_path, filename)

            if not os.path.exists(filepath):
                continue

            if currency.image and currency.image.file:
                if overwrite:
                    try:
                        storage.save(currency.image.file.storage_key, filepath, mime_type='image/svg+xml')
                        currency.image.file.file_size = os.path.getsize(filepath)
                        currency.image.description = 'Static image'

                        if not currency.image.is_vector:
                            create_thumbnails(currency.image)
                        db.session.commit()
                    except Exception as e:
                        print(f'Updating flag for {country_code} failed: {e}')
                        db.session.rollback()
            else:
                try:
                    storage_key = f'flags/{uuid.uuid4().hex}_{filename}'
                    storage.save(storage_key, filepath, mime_type='image/svg+xml')

                    new_file = File(
                        original_filename=filename,
                        storage_backend=current_app.config['STORAGE_DEFAULT_BACKEND'],
                        storage_key=storage_key,
                        mime_type='image/svg+xml',
                        file_size=os.path.getsize(filepath),
                    )
                    image = Image(file_obj=new_file, is_vector=True, description='Static image')

                    currency.image = image
                    db.session.add(new_file)
                    db.session.add(image)
                    db.session.commit()

                    if not image.is_vector:
                        create_thumbnails(image)
                except Exception as e:
                    print(f'Adding flag for {country_code} failed: {e}')
                    db.session.rollback()

        click.echo('Successfully updated the flags.')

    @dbinit.command()
    @click.option('--overwrite/--no-overwrite', default=False, help='Overwrite existing flags.')
    @click.option('--subfolder', default='', help='Subfolder for icons')
    def icons(overwrite: bool, subfolder: str) -> None:
        """Initialize icons."""
        from app.models import File
        from app.storage import get_storage_provider

        storage = get_storage_provider(current_app.config['STORAGE_DEFAULT_BACKEND'])
        icon_path = os.path.join(current_app.config['IMAGE_ROOT_PATH'], 'resources', subfolder)

        if not os.path.exists(icon_path):
            print(f'Icon path does not exist: {icon_path}')
            return

        files = [f for f in os.listdir(icon_path) if f.endswith('.svg')]
        for file in files:
            filepath = os.path.join(icon_path, file)

            existing_image = Image.query.join(File).filter(File.original_filename == file).first()

            if existing_image and existing_image.file:
                if overwrite:
                    try:
                        storage.save(existing_image.file.storage_key, filepath, mime_type='image/svg+xml')
                        existing_image.file.file_size = os.path.getsize(filepath)
                        existing_image.description = 'Static image'

                        if not existing_image.is_vector:
                            create_thumbnails(existing_image)
                        db.session.commit()
                    except Exception as e:
                        print(f'Updating icon {file} failed: {e}')
                        db.session.rollback()
            else:
                try:
                    storage_key = f'icons/{uuid.uuid4().hex}_{file}'
                    storage.save(storage_key, filepath, mime_type='image/svg+xml')

                    new_file = File(
                        original_filename=file,
                        storage_backend=current_app.config['STORAGE_DEFAULT_BACKEND'],
                        storage_key=storage_key,
                        mime_type='image/svg+xml',
                        file_size=os.path.getsize(filepath),
                    )
                    image = Image(file_obj=new_file, is_vector=True, description='Static image')

                    db.session.add(new_file)
                    db.session.add(image)
                    db.session.commit()

                    if not image.is_vector:
                        create_thumbnails(image)
                except Exception as e:
                    print(f'Adding icon {file} failed: {e}')
                    db.session.rollback()

        click.echo('Successfully updated the icons.')

    @dbinit.command()
    @click.option('--overwrite/--no-overwrite', default=False, help='Overwrite existing admin.')
    def admin(overwrite: bool) -> None:
        """Initialize admin with password taken from environment variables."""
        created_by = 'flask dbinit admin'
        cli_app = create_app(Config)

        # Look for existing anonymous account
        existing_anonymous_user = User.query.filter_by(username='anonymous').first()

        if existing_anonymous_user:
            if overwrite:
                existing_anonymous_user.username = 'anonymous'
                existing_anonymous_user.email = 'anonymous@mystery.ch'
                existing_anonymous_user.db_created_by = created_by
                existing_anonymous_user.is_admin = False
                existing_anonymous_user.set_random_password()
                existing_anonymous_user.get_token()
                db.session.commit()
        else:
            anonymous_user = User(
                username='anonymous',
                email='anonymous@mystery.ch',
                locale=cli_app.config['LANGUAGES'][0],
                about_me='I am the unknown user!',
                db_created_by=created_by,
            )
            anonymous_user.is_admin = False
            anonymous_user.set_random_password()
            anonymous_user.get_token()
            db.session.add(anonymous_user)

        # Look for existing admin account
        existing_admin_user = User.query.filter_by(username='admin').first()

        if existing_admin_user:
            if overwrite:
                existing_admin_user.username = cli_app.config['ADMIN_USERNAME']
                existing_admin_user.email = cli_app.config['ADMIN_EMAIL']
                existing_admin_user.db_created_by = created_by
                existing_admin_user.is_admin = True
                existing_admin_user.set_password(cli_app.config['ADMIN_PASSWORD'])
                existing_admin_user.get_token()
                db.session.commit()
        else:
            admin_user = User(
                username=cli_app.config['ADMIN_USERNAME'],
                email=cli_app.config['ADMIN_EMAIL'],
                locale=cli_app.config['LANGUAGES'][0],
                about_me='I am the mighty admin!',
                db_created_by=created_by,
            )
            admin_user.is_admin = True
            admin_user.set_password(cli_app.config['ADMIN_PASSWORD'])
            admin_user.get_token()
            db.session.add(admin_user)
            db.session.commit()

        click.echo('Successfully added the admin user.')

    @dbinit.command()
    @click.option('--count', default=3, help='Number of dummy users to create.')
    def dummyusers(count: int) -> None:
        """Create dummy users for development."""
        created_by = f'flask dummyusers --count {count}'

        existing_usernames = [user.username for user in User.query.all()]
        existing_emails = [user.email for user in User.query.all()]
        for i_user in range(count):
            user = User(
                username=f'User{i_user}',
                email=f'user{i_user}@email.net',
                locale='en',
                about_me=f'blablablabla from the life of User{i_user}',
                db_created_by=created_by,
            )
            user.set_password(user.username)
            if user.username not in existing_usernames and user.email not in existing_emails:
                user.get_token()
                db.session.add(user)
        db.session.commit()

        click.echo(f'Successfully added {count} dummy users.')

    # ------------------------------------------------------------------
    # Database maintenance commands
    # ------------------------------------------------------------------

    @app.cli.group()
    def dbmaint():
        """Commands for database maintenance."""
        pass

    @dbmaint.command()
    def add_missing_guid() -> None:
        """Fill tables with missing GUIDs."""
        updated_by = 'flask dbmaint add_missing_guid'

        def class_add_missing_guid(model_class) -> None:
            instances = model_class.query.filter(model_class.guid.is_(None)).all()
            for instance in instances:
                instance.db_updated_by = updated_by
                instance.db_updated_at = datetime.now(timezone.utc)
                instance.guid = uuid.uuid4()
            db.session.commit()

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

        click.echo('Successfully added missing guids.')

    # ------------------------------------------------------------------
    # Cache / storage flush commands
    # ------------------------------------------------------------------

    @app.cli.command('flush-media-cache')
    def flush_media_cache() -> None:
        """Clear all cached images from Redis."""
        r = redis.Redis(
            host=current_app.config.get('REDIS_HOST', 'localhost'),
            port=current_app.config.get('REDIS_PORT', 6379),
            db=current_app.config.get('REDIS_DB', 0),
            password=current_app.config.get('REDIS_PASSWORD'),
        )

        keys = r.keys('media_cache:*')
        if keys:
            r.delete(*keys)
            click.echo(f'Successfully flushed {len(keys)} media files from Redis cache.')
        else:
            click.echo('Redis media cache is already empty.')

    @app.cli.command('flush-jobs')
    def flush_jobs() -> None:
        """Clear all scheduled jobs from Redis."""
        r = redis.Redis(
            host=current_app.config.get('REDIS_HOST', 'localhost'),
            port=current_app.config.get('REDIS_PORT', 6379),
            db=current_app.config.get('REDIS_DB', 0),
            password=current_app.config.get('REDIS_PASSWORD'),
        )

        r.delete('housekeeping_jobs', 'housekeeping_jobs_running')
        click.echo('Successfully flushed orphaned scheduled jobs from Redis.')

    @app.cli.command('flush-s3')
    def flush_s3() -> None:
        """Delete all objects and folders in the S3 bucket."""
        bucket_name = current_app.config.get('S3_BUCKET_NAME')
        if not bucket_name:
            click.echo('S3_BUCKET_NAME is not configured.')
            return

        click.echo(f"Connecting to S3 to empty bucket '{bucket_name}'...")

        try:
            s3 = boto3.resource(
                's3',
                region_name=current_app.config.get('S3_REGION'),
                endpoint_url=current_app.config.get('S3_ENDPOINT_URL'),
            )
            bucket = s3.Bucket(bucket_name)

            # Delete objects one by one to bypass OCI's MD5 requirement
            count = 0
            for obj in bucket.objects.all():
                obj.delete()
                count += 1

            if count > 0:
                click.echo(f'Successfully deleted {count} objects/folders from S3.')
            else:
                click.echo('Bucket is already empty.')
        except Exception as e:
            click.echo(f'Error emptying S3 bucket: {e}')

    @app.cli.command('flush-db')
    def flush_db() -> None:
        """Completely drop all tables, data, indexes, and constraints."""
        click.echo('WARNING: Dropping all database tables...')
        try:
            db.metadata.reflect(bind=db.engine)
            db.metadata.drop_all(bind=db.engine)
            db.session.commit()
            click.echo('Successfully wiped the entire database (tables, content, indexes).')
        except Exception as e:
            db.session.rollback()
            click.echo(f'Error flushing database: {e}')

    @app.cli.command('flush-db-force')
    def flush_db_force() -> None:
        """Completely drop all tables using dialect-specific force logic."""
        click.echo('WARNING: Dropping all database tables...')
        try:
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            dialect = db.engine.dialect.name

            if dialect in ('mysql', 'mariadb'):
                db.session.execute(text('SET FOREIGN_KEY_CHECKS = 0;'))
                for table in tables:
                    db.session.execute(text(f'DROP TABLE IF EXISTS `{table}`;'))
                    click.echo(f'Dropped table: {table}')
                db.session.execute(text('SET FOREIGN_KEY_CHECKS = 1;'))

            elif dialect == 'oracle':
                for table in tables:
                    db.session.execute(text(f'DROP TABLE {table} CASCADE CONSTRAINTS'))
                    click.echo(f'Dropped table: {table} (Cascaded)')

            else:
                # SQLite, PostgreSQL, etc.
                for table in tables:
                    db.session.execute(text(f'DROP TABLE {table} CASCADE;'))
                    click.echo(f'Dropped table: {table}')

            db.session.commit()
            click.echo(f'Successfully wiped the entire {dialect.upper()} database.')
        except Exception as e:
            db.session.rollback()
            click.echo(f'Error flushing database: {e}')
