# -*- coding: utf-8 -*-

from app import db
from app.models import User, Log

def log_add(severity, module, msg_type, msg, user, trace=None):
    log = Log(severity, module, msg_type, msg, user, trace)
    db.session.add(log)
    db.session.commit()

def log_login(path, user):
    log_add('INFORMATION', path, 'login successful', 'User {} logs in successfully'.format(user.username), user)
    
def log_login_denied(path, username):
    user = User.query.filter_by(username='admin').first()
    log_add('WARNING', path, 'login denied', 'User with user name {} tried to log in'.format(username), user)
    
def log_logout(path, user):
    log_add('INFORMATION', path, 'logout', 'User {} logs out successfully'.format(user.username), user)
    
def log_register(path, user):
    log_add('INFORMATION', path, 'register', 'User {} registers'.format(user.username), user)
    
def log_reset_password_request(path, user):
    log_add('INFORMATION', path, 'reset password request', 'User {} requested a password reset'.format(user.username), user)
    
def log_reset_password(path, user):
    log_add('INFORMATION', path, 'reset password', 'User {} reset password'.format(user.username), user)
    
def log_page_access(request, user):
    log_add('INFORMATION', request.path, 'page access successful', 
            'User {} accessed {} successfully'.format(user.username, request.path), user, 
            str(request.headers.to_wsgi_list()))
    
def log_page_access_denied(request, user):
    log_add('WARNING', request.path, 'page access denied', 
            'User {} was denied from accessing {}'.format(user.username, request.path), user, 
            str(request.headers.to_wsgi_list()))
    
def log_email(email_type, subject, body, recipient):
    user = User.query.filter_by(username='admin').first()
    log_add('INFORMATION', email_type, 'email sent', 
            'User {}: {}'.format(recipient, subject), user, 
            body)
    
def log_error(request, error_type):
    user = User.query.filter_by(username='admin').first()
    log_add('ERROR', request.path, 'page access error', 
            'Error {} when accessing page {}'.format(error_type, request.path), user, 
            str(request.headers.to_wsgi_list()))