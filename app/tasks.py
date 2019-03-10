# -*- coding: utf-8 -*-

import sys
import time
import json
from flask import render_template
from rq import get_current_job
from app import db, create_app
from app.models import Task, User, Post
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

        send_email('Time has been consumed',
                sender=app.config['ADMIN_NOREPLY_SENDER'], recipients=[user.email],
                text_body=render_template('email/consume_time.txt', user=user, amount=amount),
                html_body=render_template('email/consume_time.html', user=user, amount=amount),
                attachments=[],
                sync=True)
    
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
            time.sleep(2)
            i += 1
            _set_task_progress(100 * i // total_posts)

        send_email('Your posts',
                sender=app.config['ADMIN_NOREPLY_SENDER'], recipients=[user.email],
                text_body=render_template('email/export_posts.txt', user=user),
                html_body=render_template('email/export_posts.html', user=user),
                attachments=[('posts.json', 'application/json',
                              json.dumps({'posts': data}, indent=4))],
                sync=True)
    
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())
