# coding=utf-8
"""Application entry point: creates the Flask app and registers the shell context."""

from __future__ import annotations

from app import create_app, db, cli
from app.models import (
    Thumbnail, Image, Currency, Event, EventCurrency,
    Post, Expense, Settlement, User, Message, Notification, Task,
)

app = create_app()
cli.register(app)


@app.shell_context_processor
def make_shell_context() -> dict:
    """Expose frequently used models in ``flask shell``."""
    return {
        'db': db,
        'Thumbnail': Thumbnail,
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
        'Task': Task,
    }
