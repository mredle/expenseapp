"""Background tasks dispatched via RQ and scheduled cron jobs via APScheduler."""

from __future__ import annotations

import concurrent.futures
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from flask import current_app, render_template
from flask_babel import _, force_locale
from rq import get_current_job
from weasyprint import HTML
from yahoofinancials import YahooFinancials

from app import create_app, db, scheduler
from app.db_logging import log_add
from app.email import send_email
from app.models import (
    Currency,
    Event,
    EventUser,
    Expense,
    Image,
    Log,
    Post,
    Settlement,
    Task,
    Thumbnail,
    User,
)

if TYPE_CHECKING:
    pass

app = create_app()
app.app_context().push()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_task_progress(progress: int) -> None:
    """Update the progress meta-field on the current RQ job."""
    job = get_current_job()
    if job:
        job.meta['progress'] = progress
        job.save_meta()
        task = db.session.get(Task, job.id)
        task.user.add_notification(
            'task_progress', {'task_id': job.id, 'progress': progress},
        )
        if progress >= 100:
            task.complete = True
        db.session.commit()


# ---------------------------------------------------------------------------
# RQ tasks
# ---------------------------------------------------------------------------

def consume_time(guid: str, amount: int) -> None:
    """Burn *amount* seconds of wall-clock time (for testing the task queue)."""
    try:
        user = User.get_by_guid_or_404(guid)
        _set_task_progress(0)
        for i in range(amount):
            time.sleep(1)
            _set_task_progress(100 * (1 + i) // amount)

        _set_task_progress(100)
        message = f'{amount}s of my valuable time have been consumed'
        send_email(
            'Time has been consumed',
            sender=app.config['ADMIN_NOREPLY_SENDER'],
            recipients=[user.email],
            text_body=render_template(
                'email/simple_email.txt', username=user.username, message=message,
            ),
            html_body=render_template(
                'email/simple_email.html', username=user.username, message=message,
            ),
            attachments=[],
            sync=True,
        )
    except Exception:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def type_error(guid: str) -> None:
    """Intentionally trigger a ``TypeError`` (for testing error handling)."""
    try:
        user = User.get_by_guid_or_404(guid)  # noqa: F841
        _set_task_progress(0)
        test_str = 'asdf'
        test_number = test_str + 5  # noqa: F841  — deliberately broken
        _set_task_progress(100)
    except Exception:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def create_thumbnails(image: Image, update_progress: bool = False) -> None:
    """Generate all configured thumbnail sizes for *image*."""
    sizes = list(app.config['THUMBNAIL_SIZES'])
    total = len(app.config['THUMBNAIL_SIZES']) + 1
    sizes.append(max((image.width, image.height)))
    i = 0
    if update_progress:
        _set_task_progress(100 * (1 + i) // total)
    for size in sizes:
        i += 1
        thumbnail = Thumbnail(image, size)
        db.session.add(thumbnail)
        if update_progress:
            _set_task_progress(100 * (1 + i) // total)

    if update_progress:
        _set_task_progress(100)
    db.session.commit()


def import_image(guid: str, path: str, add_to_class: str, add_to_id: int) -> None:
    """Import an image from *path* and attach it to the specified model instance."""
    try:
        user = User.get_by_guid_or_404(guid)
        image = Image(path)
        image.description = f'Image uploaded by {user.username}'

        db.session.add(image)
        if add_to_class == 'User':
            db.session.get(User, add_to_id).profile_picture = image
        elif add_to_class == 'Event':
            db.session.get(Event, add_to_id).image = image
        elif add_to_class == 'EventUser':
            db.session.get(EventUser, add_to_id).profile_picture = image
        elif add_to_class == 'Expense':
            db.session.get(Expense, add_to_id).image = image
        elif add_to_class == 'Settlement':
            db.session.get(Settlement, add_to_id).image = image
        db.session.commit()

        # Create thumbnails
        create_thumbnails(image, update_progress=True)
    except Exception:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def export_posts(guid: str) -> None:
    """Export all posts for the user identified by *guid* and email as JSON."""
    try:
        user = User.get_by_guid_or_404(guid)
        _set_task_progress(0)
        data: list[dict[str, str]] = []

        eventusers = EventUser.query.filter_by(email=user.email).all()
        total_posts = sum(eu.posts.count() for eu in eventusers)

        i = 0
        for eu in eventusers:
            for post in eu.posts.order_by(Post.timestamp.asc()):
                data.append({
                    'body': post.body,
                    'timestamp': f'{post.timestamp.isoformat()}Z',
                })
                i += 1
                _set_task_progress(100 * i // max(total_posts, 1))

        _set_task_progress(100)
        message = 'Please find attached the archive of your posts that you requested'
        send_email(
            'Your posts',
            sender=app.config['ADMIN_NOREPLY_SENDER'],
            recipients=[user.email],
            text_body=render_template(
                'email/simple_email.txt', username=user.username, message=message,
            ),
            html_body=render_template(
                'email/simple_email.html', username=user.username, message=message,
            ),
            attachments=[('posts.json', 'application/json', json.dumps({'posts': data}, indent=4))],
            sync=True,
        )
    except Exception:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def get_balance_pdf(
    event: Event,
    locale: str,
    timenow: str | None = None,
    recalculate: bool = False,
) -> bytes:
    """Render the balance sheet for *event* as a PDF and return the bytes."""
    if recalculate:
        event.calculate_balance()
    else:
        event.settlements.filter_by(draft=True).all()
    balances_str, total_expenses_str = event.get_balance()

    if timenow is None:
        timenow = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    balance_grid = ('10%', '18%', '18%', '18%', '18%', '18%')
    with force_locale(locale):
        html = render_template(
            'pdf/balance.html',
            event=event,
            timenow=timenow,
            balance_grid=balance_grid,
            stats=event.get_stats(),
            balances_str=balances_str,
            total_expenses_str=total_expenses_str,
        )
        pdf: bytes = HTML(string=html).write_pdf(presentational_hints=True)

    return pdf


def request_balance(guid: str, event_guid: str, eventuser_guid: str) -> None:
    """Generate the balance PDF for an event and email it to the requesting user."""
    try:
        event = Event.get_by_guid_or_404(event_guid)
        eventuser = EventUser.get_by_guid_or_404(eventuser_guid)

        _set_task_progress(0)
        timenow = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        pdf = get_balance_pdf(event, eventuser.locale, timenow, recalculate=True)

        with force_locale(eventuser.locale):
            send_email(
                _('Your balance of event %(eventname)s', eventname=event.name),
                sender=current_app.config['ADMIN_NOREPLY_SENDER'],
                recipients=[eventuser.email],
                text_body=render_template(
                    'email/balance_email.txt',
                    username=eventuser.username, eventname=event.name, timenow=timenow,
                ),
                html_body=render_template(
                    'email/balance_email.html',
                    username=eventuser.username, eventname=event.name, timenow=timenow,
                ),
                attachments=[('balance.pdf', 'application/pdf', pdf)],
                sync=True,
            )
        _set_task_progress(100)
    except Exception:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def send_reminders(guid: str, event_guid: str) -> None:
    """Send payment-reminder emails to all debtors of *event*."""
    try:
        event = Event.get_by_guid_or_404(event_guid)

        _set_task_progress(0)
        draft_settlements = event.calculate_balance()
        timenow = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        total_payments = len(draft_settlements)

        i = 0
        for settlement in draft_settlements:
            if settlement.sender.email:
                with force_locale(settlement.sender.locale):
                    pdf = get_balance_pdf(event, settlement.sender.locale, timenow)

                    send_email(
                        _('Please settle your depts!'),
                        sender=current_app.config['ADMIN_NOREPLY_SENDER'],
                        recipients=[settlement.sender.email],
                        text_body=render_template(
                            'email/reminder_email.txt', settlement=settlement, timenow=timenow,
                        ),
                        html_body=render_template(
                            'email/reminder_email.html', settlement=settlement, timenow=timenow,
                        ),
                        attachments=[('balance.pdf', 'application/pdf', pdf)],
                        sync=True,
                    )
            i += 1
            _set_task_progress(100 * i // total_payments)

        _set_task_progress(100)
    except Exception:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def clean_log(error: bool, keepdays: int) -> None:
    """Delete log entries older than *keepdays* days.

    If *error* is ``True`` all entries are removed; otherwise ``ERROR``
    entries are preserved.
    """
    keydate = datetime.now(timezone.utc) - timedelta(days=keepdays)
    if error:
        Log.query.filter(Log.date <= keydate).delete()
    else:
        Log.query.filter(Log.date <= keydate, Log.severity != 'ERROR').delete()
    db.session.commit()


def update_rates_yahoo(guid: str) -> None:
    """Fetch latest exchange rates from Yahoo Finance and update the database."""
    user = User.get_by_guid_or_404(guid)
    _set_task_progress(0)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=5)  # Look back 5 days to bypass weekends/holidays

    # CHF → USD baseline
    yahoo_currencies = 'CHF=X'
    yahoo_financials_currencies = YahooFinancials(yahoo_currencies)
    daily_currency_prices = yahoo_financials_currencies.get_historical_price_data(
        start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), 'daily',
    )

    chf_data = daily_currency_prices.get('CHF=X', {})
    if not chf_data or 'prices' not in chf_data or len(chf_data['prices']) == 0:
        raise Exception(f"Failed to fetch baseline CHF=X rate. Yahoo response: {daily_currency_prices}")

    USD_inCHF = chf_data['prices'][-1]['adjclose']

    existing_currencies = Currency.query.filter(Currency.source == 'yahoo').all()
    n = len(existing_currencies)

    def chunks(lst: list, chunk_size: int):
        """Yield successive *chunk_size*-sized chunks from *lst*."""
        for i in range(0, len(lst), chunk_size):
            yield lst[i:i + chunk_size]

    _set_task_progress(1)

    trace: str | None = None
    try:
        updated_count = 0
        processed_count = 0

        for currency_chunk in chunks(existing_currencies, 10):
            yahoo_currencies_list = [f'{c.code}=X' for c in currency_chunk]
            yahoo_financials_currencies = YahooFinancials(yahoo_currencies_list)

            daily_currency_prices = None
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        yahoo_financials_currencies.get_historical_price_data,
                        start.strftime('%Y-%m-%d'),
                        end.strftime('%Y-%m-%d'),
                        'daily',
                    )
                    daily_currency_prices = future.result(timeout=15)
            except concurrent.futures.TimeoutError:
                app.logger.warning(f"Yahoo API timeout for batch: {yahoo_currencies_list}. Skipping chunk.")
                processed_count += len(currency_chunk)
                _set_task_progress(100 * processed_count // n)
                continue
            except Exception as e:
                app.logger.warning(f"Yahoo API error for batch: {yahoo_currencies_list} - {e}")
                processed_count += len(currency_chunk)
                _set_task_progress(100 * processed_count // n)
                continue

            trace = str(daily_currency_prices)
            if len(trace) > 4000:
                trace = trace[:4000]

            if daily_currency_prices:
                exchange_rates = {
                    v.get('currency'): USD_inCHF / daily_currency_prices[k]['prices'][-1]['adjclose']
                    for k, v in daily_currency_prices.items()
                    if v and 'currency' in v and 'prices' in v and len(v['prices']) > 0
                }

                for c in currency_chunk:
                    if c.code in exchange_rates:
                        c.inCHF = exchange_rates[c.code]
                        c.db_updated_at = start
                        c.db_updated_by = 'update_rates_yahoo'
                        updated_count += 1

            processed_count += len(currency_chunk)
            _set_task_progress(100 * processed_count // n)
            time.sleep(1)

        message = f'{updated_count} currencies updated successfully from yahoo.'
        log_add('INFORMATION', 'scheduler.task', 'get_rates_yahoo', message, user, trace=trace)
        db.session.commit()
    except Exception:
        message = f'{n} currencies could not be updated from yahoo.'
        log_add(
            'WARNING', 'scheduler.task', 'get_rates_yahoo', message, user,
            trace=(trace if trace is not None else str(sys.exc_info())),
        )

    _set_task_progress(100)


def check_rates_yahoo(guid: str) -> None:
    """Verify which currencies are available on Yahoo Finance and tag them."""
    user = User.get_by_guid_or_404(guid)
    _set_task_progress(0)

    start = datetime.now(timezone.utc)
    end = start

    # CHF → USD baseline
    yahoo_currencies = 'CHF=X'
    yahoo_financials_currencies = YahooFinancials(yahoo_currencies)
    daily_currency_prices = yahoo_financials_currencies.get_historical_price_data(
        start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), 'daily',
    )
    USD_inCHF = daily_currency_prices['CHF=X']['prices'][0]['adjclose']

    existing_currencies = Currency.query.all()

    # Reset source flag
    for c in existing_currencies:
        c.source = None
    log_add('INFORMATION', 'scheduler.task', 'check_rates_yahoo', 'flags reset', user)
    db.session.commit()

    # Search and update on Yahoo
    i = 0
    n = len(existing_currencies)
    for c in existing_currencies:
        trace: str | None = None
        try:
            yahoo_currency = f'{c.code}=X'
            yahoo_financials_currencies = YahooFinancials(yahoo_currency)
            daily_currency_prices = yahoo_financials_currencies.get_historical_price_data(
                start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), 'daily',
            )
            trace = str(daily_currency_prices)
            if len(trace) > 4000:
                trace = trace[:4000]

            exchange_rate = USD_inCHF / daily_currency_prices[yahoo_currency]['prices'][-1]['adjclose']

            c.inCHF = exchange_rate
            c.source = 'yahoo'
            c.db_updated_at = start
            c.db_updated_by = 'check_rates_yahoo'
            message = f'Currency {c.code} updated successfully from yahoo with rate {c.inCHF}.'
            log_add('INFORMATION', 'scheduler.task', 'check_rates_yahoo', message, user, trace=trace)
            db.session.commit()
        except Exception:
            message = f'Currency {c.code} could not be updated from yahoo'
            log_add(
                'WARNING', 'scheduler.task', 'check_rates_yahoo', message, user,
                trace=(trace if trace is not None else str(sys.exc_info())),
            )

        i += 1
        _set_task_progress(100 * i // n)

    _set_task_progress(100)


def housekeeping(guid: str) -> None:
    """Perform periodic maintenance (log cleanup)."""
    try:
        user = User.get_by_guid_or_404(guid)
        _set_task_progress(0)
        clean_log(False, 360)
        message = 'clean_log job started successfully'
        log_add('INFORMATION', 'scheduler.task', 'housekeeping', message, user)
        _set_task_progress(100)
    except Exception:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


# ---------------------------------------------------------------------------
# APScheduler cron jobs
# ---------------------------------------------------------------------------

@scheduler.task('cron', id='j_housekeeping', day='2', hour='3')
def j_housekeeping() -> None:
    """Run housekeeping on the 2nd of each month at 03:00."""
    with scheduler.app.app_context():
        admin = User.query.filter(User.username == 'admin').first()
        admin.launch_task('housekeeping', _('Performing housekeeping jobs...'))
        db.session.commit()


@scheduler.task('cron', id='j_check_currencies', day_of_week='2', hour='4')
def j_check_currencies() -> None:
    """Check currency availability on Yahoo every Tuesday at 04:00."""
    with scheduler.app.app_context():
        admin = User.query.filter(User.username == 'admin').first()
        admin.launch_task('check_rates_yahoo', _('Checking currencies...'))
        db.session.commit()


@scheduler.task('cron', id='j_update_currencies', day='*', hour='5')
def j_update_currencies() -> None:
    """Update exchange rates from Yahoo every day at 05:00."""
    with scheduler.app.app_context():
        admin = User.query.filter(User.username == 'admin').first()
        admin.launch_task('update_rates_yahoo', _('Updating currencies...'))
        db.session.commit()
