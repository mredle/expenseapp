# -*- coding: utf-8 -*-

import sys
import time
import json
from flask import render_template
from rq import get_current_job
from app import db, create_app
from app.models import Expense, Settlement, Currency, Task, User, Event, Post, Image, Thumbnail
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

def import_image(user_id, path, add_to_class, add_to_id):
    try:
        i = 0;
        total = len(app.config['THUMBNAIL_SIZES'])+1
        _set_task_progress(100*(1+i)//total)
        
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
        elif add_to_class == 'Currency':
            add_to_currency = Currency.query.get(add_to_id)
            add_to_currency.image = image 
        elif add_to_class == 'Expense':
            add_to_expense = Expense.query.get(add_to_id)
            add_to_expense.image = image
        elif add_to_class == 'Settlement':
            add_to_settlement = Settlement.query.get(add_to_id)
            add_to_settlement.image = image 
        db.session.commit()
        
        # Create thumbnails
        sizes = list(app.config['THUMBNAIL_SIZES'])
        sizes.append(max((image.width, image.height)))
        for size in sizes:
            i = i+1;
            thumbnail = Thumbnail(image, size)
            db.session.add(thumbnail)
            _set_task_progress(100*(1+i)//total)
        
        _set_task_progress(100)
        db.session.commit()
        
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
