# -*- coding: utf-8 -*-

import sys
import time
import json

from datetime import datetime, timedelta
from weasyprint import HTML
from flask import render_template, current_app
from flask_babel import _, force_locale
from rq import get_current_job
from app import db, create_app, scheduler
from app.models import Currency, Expense, Settlement, Task, User, Event, EventUser, Post, Image, Thumbnail, Log
from app.db_logging import log_add
from app.email import send_email

from yahoofinancials import YahooFinancials
# from forex_python.converter import CurrencyRates
# import pandas_datareader.data as web

app = create_app()
app.app_context().push()

def _set_task_progress(progress):
    job = get_current_job()
    if job:
        job.meta['progress'] = progress
        job.save_meta()
        task = Task.query.get(job.get_id())
        task.user.add_notification('task_progress', {'task_id': job.get_id(),
                                                     'progress': progress})
        if progress >= 100:
            task.complete = True
        db.session.commit()

def consume_time(guid, amount):
    try:
        user = User.get_by_guid_or_404(guid)
        _set_task_progress(0)
        for i in range(amount):
            time.sleep(1)
            _set_task_progress(100*(1+i)//amount)
        
        _set_task_progress(100)
        message = '{}s of my valuable time have been consumed'.format(amount)
        send_email('Time has been consumed',
                sender=app.config['ADMIN_NOREPLY_SENDER'], recipients=[user.email],
                text_body=render_template('email/simple_email.txt', 
                                          username=user.username, 
                                          message=message),
                html_body=render_template('email/simple_email.html', 
                                          username=user.username, 
                                          message=message),
                attachments=[],
                sync=True)
    
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())

def create_thumbnails(image, update_progress=False):
    sizes = list(app.config['THUMBNAIL_SIZES'])
    total = len(app.config['THUMBNAIL_SIZES'])+1
    sizes.append(max((image.width, image.height)))
    i = 0;
    if update_progress:
        _set_task_progress(100*(1+i)//total)
    for size in sizes:
        i = i+1;
        thumbnail = Thumbnail(image, size)
        db.session.add(thumbnail)
        if update_progress:
            _set_task_progress(100*(1+i)//total)
    
    if update_progress:
        _set_task_progress(100)
    db.session.commit()

def import_image(guid, path, add_to_class, add_to_id):
    try:
        # Saving the image to a new file
        user = User.get_by_guid_or_404(guid)
        image = Image(path)
        image.description = 'Image uploaded by {}'.format(user.username)
        
        db.session.add(image)
        if add_to_class == 'User':
            add_to_user = User.query.get(add_to_id)
            add_to_user.profile_picture = image  
        elif add_to_class == 'Event':
            add_to_event = Event.query.get(add_to_id)
            add_to_event.image = image
        elif add_to_class == 'EventUser':
            add_to_eventuser = EventUser.query.get(add_to_id)
            add_to_eventuser.profile_picture = image
        elif add_to_class == 'Expense':
            add_to_expense = Expense.query.get(add_to_id)
            add_to_expense.image = image
        elif add_to_class == 'Settlement':
            add_to_settlement = Settlement.query.get(add_to_id)
            add_to_settlement.image = image 
        db.session.commit()
        
        # Create thumbnails
        create_thumbnails(image, update_progress=True)
        
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())
        
def export_posts(guid):
    try:
        user = User.get_by_guid_or_404(guid)
        _set_task_progress(0)
        data = []
        i = 0
        total_posts = user.posts.count()
        for post in user.posts.order_by(Post.timestamp.asc()):
            data.append({'body': post.body,
                         'timestamp': post.timestamp.isoformat() + 'Z'})
            i += 1
            _set_task_progress(100*i//total_posts)
        
        _set_task_progress(100)
        message = 'Please find attached the archive of your posts that you requested'
        send_email('Your posts',
                sender=app.config['ADMIN_NOREPLY_SENDER'], recipients=[user.email],
                text_body=render_template('email/simple_email.txt', 
                                          username=user.username, 
                                          message=message),
                html_body=render_template('email/simple_email.html', 
                                          username=user.username, 
                                          message=message),
                attachments=[('posts.json', 'application/json',
                              json.dumps({'posts': data}, indent=4))],
                sync=True)
    
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())

def get_balance_pdf(event, locale, timenow=None, recalculate=False):
    
    if recalculate:
        event.calculate_balance()
    else:
        event.settlements.filter_by(draft=True).all()
    balances_str, total_expenses_str = event.get_balance()
    
    if timenow is None:
        timenow=datetime.utcnow().replace(microsecond=0).isoformat()
        
    balance_grid = ('10%', '18%', '18%','18%','18%','18%')
    with force_locale(locale):
        html = render_template('pdf/balance.html', 
                               event=event,
                               timenow=timenow,
                               balance_grid=balance_grid,
                               stats=event.get_stats(),
                               balances_str=balances_str, 
                               total_expenses_str=total_expenses_str)
        
        pdf = HTML(string=html).write_pdf(presentational_hints=True)
    
    return pdf
    
def request_balance(guid, event_guid):
    try:
        user = User.get_by_guid_or_404(guid)
        event = Event.get_by_guid_or_404(event_guid)
        
        _set_task_progress(0)
        timenow=datetime.utcnow().replace(microsecond=0).isoformat()
        pdf = get_balance_pdf(event, user.locale, timenow, recalculate=True)
        
        with force_locale(user.locale):
            send_email(_('Your balance of event %(eventname)s', eventname=event.name),
                       sender=current_app.config['ADMIN_NOREPLY_SENDER'],
                       recipients=[user.email],
                       text_body=render_template('email/balance_email.txt',
                                                 username=user.username,
                                                 eventname=event.name,
                                                 timenow=timenow),
                       html_body=render_template('email/balance_email.html',
                                                 username=user.username,
                                                 eventname=event.name,
                                                 timenow=timenow),
                       attachments=[('balance.pdf', 'application/pdf', pdf)],
                       sync=True)
        _set_task_progress(100)
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())

def send_reminders(guid, event_guid):
    try:
        #user = User.get_by_guid_or_404(guid)
        event = Event.get_by_guid_or_404(event_guid)
        
        _set_task_progress(0)
        draft_settlements = event.calculate_balance()
        timenow=datetime.utcnow().replace(microsecond=0).isoformat()
        total_payments = len(draft_settlements)
        
        i = 0
        for settlement in draft_settlements:
            with force_locale(settlement.sender.locale):
                bank_accounts = settlement.recipient.bank_accounts
                
                pdf = get_balance_pdf(event, settlement.sender.locale, timenow)
                
                send_email(_('Please settle your depts!'),
                           sender=current_app.config['ADMIN_NOREPLY_SENDER'],
                           recipients=[settlement.sender.email],
                           text_body=render_template('email/reminder_email.txt',
                                                     settlement=settlement,
                                                     bank_accounts=bank_accounts,
                                                     timenow=timenow),
                           html_body=render_template('email/reminder_email.html',
                                                     settlement=settlement,
                                                     bank_accounts=bank_accounts,
                                                     timenow=timenow),
                           attachments=[('balance.pdf', 'application/pdf', pdf)],
                           sync=True)
            i += 1
            _set_task_progress(100*i//total_payments)
        
        _set_task_progress(100)

    
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())
   
def clean_log(error, keepdays):
    """Clean log entries older than certain days"""
    
    # find log entries
    keydate = datetime.utcnow() - timedelta(days=keepdays)
    if error:
        Log.query.filter(Log.date<=keydate).delete()
    else:
        Log.query.filter(Log.date<=keydate, Log.severity!='ERROR').delete()
    db.session.commit()
   
def update_rates_yahoo(guid):
    """Update rates from yahoo"""
    user = User.get_by_guid_or_404(guid)
    _set_task_progress(0)
    
    start = datetime.utcnow()
    end = datetime.utcnow()
    
    # CHF -> USD
    yahoo_currencies = 'CHF=X'
    yahoo_financials_currencies = YahooFinancials(yahoo_currencies)
    daily_currency_prices = yahoo_financials_currencies.get_historical_price_data(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), 'daily')
    USD_inCHF = daily_currency_prices['CHF=X']['prices'][0]['adjclose']
    
    existing_currencies = Currency.query.filter(Currency.source=='yahoo').all()
    yahoo_currencies = ['{}=X'.format(c.code) for c in existing_currencies]
    n = len(existing_currencies)
    # def chunks(lst, n):
    #     """Yield successive n-sized chunks from lst."""
    #     for i in range(0, len(lst), n):
    #         yield lst[i:i + n]
    
    try:
        yahoo_financials_currencies = YahooFinancials(yahoo_currencies)
        daily_currency_prices = yahoo_financials_currencies.get_historical_price_data(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), 'daily')
        
        exchange_rates = {v['currency']: USD_inCHF/daily_currency_prices[k]['prices'][0]['adjclose'] 
                          for k, v in daily_currency_prices.items() 
                          if 'currency' in v}
        
        for c in existing_currencies:
            if c.code in exchange_rates:
                c.inCHF = exchange_rates[c.code]
                c.db_updated_at = start
                c.db_updated_by = 'update_rates_yahoo'
        
        message = '{} currencies updated successfully from yahoo.'.format(n)
        log_add('INFORMATION', 'scheduler.task', 'get_rates_yahoo', message, user)
        db.session.commit()
    except:
        message = '{} currencies could not be updated from yahoo.'.format(n)
        log_add('WARNING', 'scheduler.task', 'get_rates_yahoo', message, user)
        
    _set_task_progress(100)
    
            
def check_rates_yahoo(guid):
    """Check if rates are available on yahoo"""
    user = User.get_by_guid_or_404(guid)
    _set_task_progress(0)
        
    start = datetime.utcnow()
    end = datetime.utcnow()
    
    # CHF -> USD
    yahoo_currencies = 'CHF=X'
    yahoo_financials_currencies = YahooFinancials(yahoo_currencies)
    daily_currency_prices = yahoo_financials_currencies.get_historical_price_data(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), 'daily')
    USD_inCHF = daily_currency_prices['CHF=X']['prices'][0]['adjclose']
    
    existing_currencies = Currency.query.all()
    i = 0
    n = len(existing_currencies)
    for c in existing_currencies:
        try:
            yahoo_currency = '{}=X'.format(c.code)
            yahoo_financials_currencies = YahooFinancials(yahoo_currency)
            daily_currency_prices = yahoo_financials_currencies.get_historical_price_data(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), 'daily')
            exchange_rate = USD_inCHF/daily_currency_prices[yahoo_currency]['prices'][0]['adjclose'] 
            
            c.inCHF = exchange_rate
            c.source = 'yahoo'
            c.db_updated_at = start
            c.db_updated_by = 'check_rates_yahoo'
            message = 'Currency {} updated successfully from yahoo with rate {}.'.format(c.code, c.inCHF)
            log_add('INFORMATION', 'scheduler.task', 'check_rates_yahoo', message, user)
            db.session.commit()
        except:
            message = 'Currency {} could not be updated from yahoo'.format(c.code)
            log_add('WARNING', 'scheduler.task', 'check_rates_yahoo', message, user)
            
        i += 1
        _set_task_progress(100*i//n)
        
    _set_task_progress(100)
        

def housekeeping(guid):
    try:
        user = User.get_by_guid_or_404(guid)
        _set_task_progress(0)
        clean_log(False, 360)
        message = 'clean_log job started successfully'
        log_add('INFORMATION', 'scheduler.task', 'housekeeping', message, user)
        _set_task_progress(100)
        
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())
        
# cron jobs
@scheduler.task('cron', id='j_housekeeping', day='15', hour='3')
def j_housekeeping():
    with scheduler.app.app_context():
        admin = User.query.filter(User.username=='admin').first()
        admin.launch_task('housekeeping', _('Performing housekeeping jobs...'))
        db.session.commit()

@scheduler.task('cron', id='j_check_currencies', day='15', hour='4')
def j_check_currencies():
    with scheduler.app.app_context():
        admin = User.query.filter(User.username=='admin').first()
        admin.launch_task('check_rates_yahoo', _('Checking currencies...'))
        db.session.commit()

@scheduler.task('cron', id='j_update_currencies', day='*', hour='5')
def j_update_currencies():
    with scheduler.app.app_context():
        admin = User.query.filter(User.username=='admin').first()
        admin.launch_task('update_rates_yahoo', _('Updating currencies...'))
        db.session.commit()
        