# -*- coding: utf-8 -*-

import sys
import time
import json
from weasyprint import HTML
from flask import render_template, current_app
from flask_babel import _, force_locale
from rq import get_current_job
from app import db, create_app
from app.models import Expense, Settlement, Task, User, Event, Post, Image, Thumbnail
from app.email import send_email

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

def consume_time(user_id):
    amount=10
    try:
        user = User.query.get(user_id)
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

def import_image(user_id, path, add_to_class, add_to_id):
    try:
        # Saving the image to a new file
        user = User.query.get(user_id)
        image = Image(path)
        image.description = 'Image uploaded by {}'.format(user.username)
        
        db.session.add(image)
        if add_to_class == 'User':
            add_to_user = User.query.get(add_to_id)
            add_to_user.profile_picture = image  
        elif add_to_class == 'Event':
            add_to_event = Event.query.get(add_to_id)
            add_to_event.image = image
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
        
def export_posts(user_id):
    try:
        user = User.query.get(user_id)
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

def request_balance(user_id, event_id):
    try:
        user = User.query.get(user_id)
        event = Event.query.get(event_id)
        _set_task_progress(0)
        
        draft_settlements, balances_str, total_expenses_str = event.calculate_balance()
        
        i = 0
        total_payments = len(draft_settlements)
        with force_locale(user.locale):
            
            html = render_template('pdf/balance.html', 
                                   event=event,
                                   stats=event.get_stats(),
                                   draft_settlements=draft_settlements,
                                   balances_str=balances_str, 
                                   total_expenses_str=total_expenses_str)
            
            pdf = HTML(string=html).write_pdf(presentational_hints=True)
            
            send_email(_('Please settle your depts!'),
                       sender=current_app.config['ADMIN_NOREPLY_SENDER'],
                       recipients=[settlement.sender.email],
                       text_body=render_template('email/reminder_email.txt',
                                                 settlement=settlement,
                                                 bank_accounts=bank_accounts),
                       html_body=render_template('email/reminder_email.html',
                                                 settlement=settlement,
                                                 bank_accounts=bank_accounts),
                       attachments=[('balance.pdf', 'application/pdf', pdf)],
                       sync=True)
            i += 1
            _set_task_progress(100*i//total_payments)
        
        _set_task_progress(100)

    
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())

def send_reminders(user_id, event_id):
    try:
        user = User.query.get(user_id)
        event = Event.query.get(event_id)
        _set_task_progress(0)
        
        draft_settlements, balances_str, total_expenses_str = event.calculate_balance()
        
        i = 0
        total_payments = len(draft_settlements)
        for settlement in draft_settlements:
            with force_locale(settlement.sender.locale):
                bank_accounts = settlement.recipient.bank_accounts
                
                html = render_template('pdf/balance.html', 
                                       event=event,
                                       stats=event.get_stats(),
                                       draft_settlements=draft_settlements,
                                       balances_str=balances_str, 
                                       total_expenses_str=total_expenses_str)
                
                pdf = HTML(string=html).write_pdf(presentational_hints=True)
                
                send_email(_('Please settle your depts!'),
                           sender=current_app.config['ADMIN_NOREPLY_SENDER'],
                           recipients=[settlement.sender.email],
                           text_body=render_template('email/reminder_email.txt',
                                                     settlement=settlement,
                                                     bank_accounts=bank_accounts),
                           html_body=render_template('email/reminder_email.html',
                                                     settlement=settlement,
                                                     bank_accounts=bank_accounts),
                           attachments=[('balance.pdf', 'application/pdf', pdf)],
                           sync=True)
            i += 1
            _set_task_progress(100*i//total_payments)
        
        _set_task_progress(100)

    
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())
        