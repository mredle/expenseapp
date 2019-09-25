# -*- coding: utf-8 -*-

from flask import render_template, current_app, url_for
from flask_babel import _, force_locale
from app.email import send_email

def send_reminder_email(draft_settlements):
    for settlement in draft_settlements:
        with force_locale(settlement.sender.locale):
            bank_accounts = settlement.recipient.bank_accounts
            
            send_email(_('Please settle your depts!'),
                       sender=current_app.config['ADMIN_NOREPLY_SENDER'],
                       recipients=[settlement.sender.email],
                       text_body=render_template('email/reminder_email.txt',
                                                 settlement=settlement,
                                                 bank_accounts=bank_accounts),
                       html_body=render_template('email/reminder_email.html',
                                                 settlement=settlement,
                                                 bank_accounts=bank_accounts))