# coding=utf-8

from app import create_app, db, cli
from app.models import BankAccount, Thumbnail, Image, Currency, Event, EventCurrency, Post, Expense, Settlement, User, Message, Notification, Task

app = create_app()
cli.register(app)

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 
            'Thumbnail': Thumbnail, 
            'BankAccount': BankAccount, 
            'Image': Image, 
            'Currency': Currency, 
            'Event': Event, 
            'EventCurrency': EventCurrency, 
            'Post': Post, 
            'Expense': Expense, 
            'Settlement': Settlement, 
            'User': User, 
            'Message': Message, 
            'Notification': Notification,
            'Task': Task}
