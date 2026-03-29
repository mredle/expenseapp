"""Asynchronous and synchronous email dispatch via Flask-Mail."""

from __future__ import annotations

from threading import Thread
from typing import TYPE_CHECKING

from flask import current_app, Flask
from flask_mail import Message

from app import mail
from app.db_logging import log_email

if TYPE_CHECKING:
    from flask import Flask


def send_async_email(app: Flask, msg: Message) -> None:
    """Send *msg* inside a fresh application context (for use in a thread)."""
    with app.app_context():
        mail.send(msg)


def send_email(
    subject: str,
    sender: str,
    recipients: list[str],
    text_body: str,
    html_body: str,
    attachments: list[tuple[str, str, bytes]] | None = None,
    sync: bool = False,
) -> None:
    """Compose and send an email.

    Parameters
    ----------
    subject:
        Email subject line.
    sender:
        ``From`` address.
    recipients:
        List of recipient addresses.
    text_body:
        Plain-text body.
    html_body:
        HTML body.
    attachments:
        Optional sequence of ``(filename, content_type, data)`` tuples.
    sync:
        If ``True`` send in the current thread; otherwise spawn a
        background thread.
    """
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body

    if attachments:
        for attachment in attachments:
            msg.attach(*attachment)

    if sync:
        log_email('sync', subject, text_body, recipients[0])
        mail.send(msg)
    else:
        log_email('async', subject, text_body, recipients[0])
        Thread(
            target=send_async_email,
            args=(current_app._get_current_object(), msg),
        ).start()
