"""Main blueprint routes: dashboard, user management, currencies, messaging, and admin tools."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_babel import _, get_locale
from flask_login import current_user, login_required

from app import db
from app.db_logging import log_page_access, log_page_access_denied
from app.main import bp
from app.main.forms import CurrencyForm, EditProfileForm, EditUserForm, ImageForm, MessageForm, NewUserForm
from app.media.processor import process_and_store_image
from app.models import (
    Currency,
    Event,
    EventCurrency,
    EventUser,
    Expense,
    Image,
    Log,
    Message,
    Notification,
    Post,
    Settlement,
    Task,
    User,
)


# ---------------------------------------------------------------------------
# Before-request hook
# ---------------------------------------------------------------------------

@bp.before_app_request
def before_request() -> None:
    """Update ``last_seen`` and set the locale on each request."""
    if current_user.is_authenticated:
        # Skip updating last_seen for media and static requests to prevent DB concurrency locks
        if request.endpoint and (request.endpoint.startswith('media.') or request.endpoint == 'static'):
            return

        try:
            current_user.last_seen = datetime.now(timezone.utc)
            db.session.commit()
        except Exception:
            db.session.rollback()
    from flask import g
    g.locale = str(get_locale())


# ---------------------------------------------------------------------------
# Index / root
# ---------------------------------------------------------------------------

@bp.route('/')
def root():
    """Redirect bare ``/`` to the main index."""
    return redirect(url_for('main.index'))


@bp.route('/index')
def index():
    """Redirect to the event index."""
    return redirect(url_for('event.index'))


# ---------------------------------------------------------------------------
# Image routes
# ---------------------------------------------------------------------------

@bp.route('/image/<guid>')
@login_required
def image(guid: str):
    """Display a single image."""
    log_page_access(request, current_user)
    img = Image.get_by_guid_or_404(guid)
    return render_template('image.html', title=_('Image'), image=img, allow_turning=(not img.is_vector))


@bp.route('/rotate_image/<guid>')
@login_required
def rotate_image(guid: str):
    """Rotate an image by the requested degree."""
    degree = request.args.get('degree', 0, type=int)
    img = Image.get_by_guid_or_404(guid)
    img.rotate_image(degree)
    log_page_access(request, current_user)
    return redirect(url_for('main.image', guid=img.guid))


# ---------------------------------------------------------------------------
# Currency routes
# ---------------------------------------------------------------------------

@bp.route('/currencies')
@login_required
def currencies():
    """List all currencies (paginated)."""
    log_page_access(request, current_user)
    page = request.args.get('page', 1, type=int)
    pagination = Currency.query.order_by(Currency.code.asc()).paginate(
        page=page, per_page=current_app.config['ITEMS_PER_PAGE'], error_out=False,
    )
    next_url = url_for('main.currencies', page=pagination.next_num) if pagination.has_next else None
    prev_url = url_for('main.currencies', page=pagination.prev_num) if pagination.has_prev else None
    return render_template(
        'currencies.html',
        title=_('Current currencies'),
        currencies=pagination.items,
        allow_new=current_user.is_admin,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route('/new_currency', methods=['GET', 'POST'])
@login_required
def new_currency():
    """Create a new currency (admin only)."""
    if not current_user.is_admin:
        flash(_('Only an admin is allowed to create new currencies!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.currencies'))
    log_page_access(request, current_user)
    form = CurrencyForm()
    if form.validate_on_submit():
        currency = Currency(
            code=form.code.data,
            name=form.name.data,
            number=form.number.data,
            exponent=form.exponent.data,
            inCHF=form.inCHF.data,
            description=form.description.data,
            db_created_by=current_user.username,
        )
        db.session.add(currency)
        db.session.commit()
        flash(_('Your new currency has been added.'))
        return redirect(url_for('main.currencies'))
    return render_template('edit_form.html', title=_('New Currency'), form=form)


@bp.route('/edit_currency/<guid>', methods=['GET', 'POST'])
@login_required
def edit_currency(guid: str):
    """Edit an existing currency (admin only)."""
    if not current_user.is_admin:
        flash(_('Only an admin is allowed to edit currencies!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.currencies'))
    log_page_access(request, current_user)
    currency = Currency.get_by_guid_or_404(guid)
    form = CurrencyForm()
    if form.validate_on_submit():
        currency.code = form.code.data
        currency.name = form.name.data
        currency.number = form.number.data
        currency.exponent = form.exponent.data
        currency.inCHF = form.inCHF.data
        currency.description = form.description.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.currencies'))
    elif request.method == 'GET':
        form.code.data = currency.code
        form.name.data = currency.name
        form.number.data = currency.number
        form.exponent.data = currency.exponent
        form.inCHF.data = currency.inCHF
        form.description.data = currency.description
    return render_template('edit_form.html', title=_('Edit Currency'), form=form)


# ---------------------------------------------------------------------------
# User routes
# ---------------------------------------------------------------------------

@bp.route('/users')
@login_required
def users():
    """List all users (paginated)."""
    log_page_access(request, current_user)
    page = request.args.get('page', 1, type=int)
    pagination = User.query.order_by(User.username.asc()).paginate(
        page=page, per_page=current_app.config['ITEMS_PER_PAGE'], error_out=False,
    )
    next_url = url_for('main.users', page=pagination.next_num) if pagination.has_next else None
    prev_url = url_for('main.users', page=pagination.prev_num) if pagination.has_prev else None
    return render_template(
        'users.html',
        title=_('Current users'),
        users=pagination.items,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route('/user/<guid>')
@login_required
def user(guid: str):
    """Show a single user's profile."""
    u = User.get_by_guid_or_404(guid)
    log_page_access(request, current_user)
    return render_template('user.html', title=_('User %(username)s', username=u.username), user=u)


@bp.route('/new_user', methods=['GET', 'POST'])
@login_required
def new_user():
    """Create a new user (admin only)."""
    if not current_user.is_admin:
        flash(_('Only an admin can create new users!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.users'))
    log_page_access(request, current_user)
    form = NewUserForm()
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    if form.validate_on_submit():
        u = User(
            username=form.username.data,
            email=form.email.data,
            locale=form.locale.data,
            about_me=form.about_me.data,
        )
        u.is_admin = form.is_admin.data
        u.set_password(form.password.data)
        u.get_token()
        db.session.add(u)
        db.session.commit()
        flash(_('New user %(username)s created', username=u.username))
        return redirect(url_for('main.users'))
    return render_template('edit_form.html', title=_('New User'), form=form)


@bp.route('/edit_user/<guid>', methods=['GET', 'POST'])
@login_required
def edit_user(guid: str):
    """Edit an existing user (admin only)."""
    if not current_user.is_admin:
        flash(_('Only an admin can edit users!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.users'))
    log_page_access(request, current_user)
    u = User.get_by_guid_or_404(guid)
    admin = User.query.filter_by(username='admin').first()
    if u == admin:
        flash(_('You cannot change the master admin!'))
        return redirect(url_for('main.users'))
    form = EditUserForm(u.username, u.email)
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    if form.validate_on_submit():
        # BUG FIX: removed trailing commas that turned these into tuple assignments
        u.username = form.username.data
        u.email = form.email.data
        u.locale = form.locale.data
        u.about_me = form.about_me.data
        u.is_admin = form.is_admin.data
        if form.password.data:
            u.set_password(form.password.data)
        u.get_token()
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.users'))
    elif request.method == 'GET':
        form.username.data = u.username
        form.email.data = u.email
        form.locale.data = u.locale
        form.about_me.data = u.about_me
        form.is_admin.data = u.is_admin
    return render_template('edit_form.html', title=_('Edit User'), form=form)


@bp.route('/set_admin/<guid>')
@login_required
def set_admin(guid: str):
    """Grant admin privileges to a user."""
    u = User.get_by_guid_or_404(guid)
    if not current_user.is_admin:
        flash(_('Only an admin can set the admin rights!'))
        log_page_access_denied(request, current_user)
        # BUG FIX: was using username= instead of guid=
        return redirect(url_for('main.user', guid=u.guid))
    log_page_access(request, current_user)
    u.is_admin = True
    db.session.commit()
    return redirect(url_for('main.user', guid=u.guid))


@bp.route('/revoke_admin/<guid>')
@login_required
def revoke_admin(guid: str):
    """Revoke admin privileges from a user."""
    u = User.get_by_guid_or_404(guid)
    admin = User.query.filter_by(username='admin').first()
    if u == admin:
        flash(_('You cannot change the master admin!'))
        return redirect(url_for('main.user', guid=u.guid))
    if not current_user.is_admin:
        flash(_('Only an admin can revoke the admin rights!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.user', guid=u.guid))
    log_page_access(request, current_user)
    u.is_admin = False
    db.session.commit()
    return redirect(url_for('main.user', guid=u.guid))


# ---------------------------------------------------------------------------
# Admin / logs / tasks / statistics
# ---------------------------------------------------------------------------

@bp.route('/administration')
@login_required
def administration():
    """Show the admin dashboard."""
    if not current_user.is_admin:
        flash(_('Only an admin can view the administration page!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.index'))
    log_page_access(request, current_user)
    return render_template('administration.html', title=_('Administration'))


@bp.route('/logs')
@login_required
def logs():
    """List log entries (paginated, filterable by severity)."""
    log_page_access(request, current_user)
    page = request.args.get('page', 1, type=int)
    severity = request.args.get('severity', None, type=str)
    filters = []
    if severity is not None:
        filters.append(Log.severity == severity.upper())
    if not current_user.is_admin:
        filters.append(Log.user == current_user)
    pagination = Log.query.filter(*filters).order_by(Log.date.desc()).paginate(
        page=page, per_page=current_app.config['ITEMS_PER_PAGE'], error_out=False,
    )
    next_url = url_for('main.logs', severity=severity, page=pagination.next_num) if pagination.has_next else None
    prev_url = url_for('main.logs', severity=severity, page=pagination.prev_num) if pagination.has_prev else None
    return render_template('logs.html', logs=pagination.items, title=_('Logs'), next_url=next_url, prev_url=prev_url)


@bp.route('/log_trace/<id>')
@login_required
def log_trace(id: int):
    """Show the trace details of a single log entry."""
    log = Log.query.get_or_404(id)
    if not log.can_view(current_user):
        flash(_('Your are only allowed to view your own logs!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.logs'))
    log_page_access(request, current_user)
    return render_template('trace.html', log=log, title=_('Trace'))


@bp.route('/create_error')
@login_required
def create_error():
    """Deliberately trigger an error for testing purposes (admin only)."""
    if not current_user.is_admin:
        flash(_('Only an admin can create errors!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.logs'))
    log_page_access(request, current_user)

    key = request.args.get('key', 'TYPE_ERROR', type=str)

    if key == 'TYPE_ERROR':
        test_str = 'asdf'
        test_number = test_str + 5  # noqa: F841 — deliberately broken
        flash(_('This flash should never show up: %(test_number)s', test_number=test_number))
    db.session.commit()
    return redirect(url_for('main.logs'))


@bp.route('/tasks')
@login_required
def tasks():
    """List background tasks (paginated, filterable by completion state)."""
    log_page_access(request, current_user)
    page = request.args.get('page', 1, type=int)
    complete_str = request.args.get('complete', None, type=str)
    complete = False if complete_str == 'False' else True if complete_str == 'True' else None
    filters = []
    if complete is not None:
        filters.append(Task.complete == complete)
    if not current_user.is_admin:
        filters.append(Task.user == current_user)
    pagination = Task.query.filter(*filters).order_by(Task.db_created_at.desc()).paginate(
        page=page, per_page=current_app.config['ITEMS_PER_PAGE'], error_out=False,
    )
    next_url = url_for('main.tasks', complete=complete_str, page=pagination.next_num) if pagination.has_next else None
    prev_url = url_for('main.tasks', complete=complete_str, page=pagination.prev_num) if pagination.has_prev else None
    return render_template('tasks.html', tasks=pagination.items, title=_('Tasks'), next_url=next_url, prev_url=prev_url)


@bp.route('/remove_task/<guid>')
@login_required
def remove_task(guid: str):
    """Remove a completed task."""
    task = Task.get_by_guid_or_404(guid)
    if not task.can_edit(current_user):
        flash(_('Your are only allowed to delete your own task!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.tasks'))
    log_page_access(request, current_user)
    task_name = task.name
    task_username = task.user.username
    db.session.delete(task)
    db.session.commit()
    flash(_('Task %(name)s from user %(username)s has been removed', name=task_name, username=task_username))
    return redirect(url_for('main.tasks'))


@bp.route('/start_task')
@login_required
def start_task():
    """Launch a background task by key (admin only)."""
    if not current_user.is_admin:
        flash(_('Only an admin can start tasks!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.tasks'))
    log_page_access(request, current_user)

    key = request.args.get('key', 'WASTE_TIME', type=str)

    if key == 'WASTE_TIME':
        amount = request.args.get('amount', 10, type=int)
        current_user.launch_task('consume_time', _('Consuming %(amount)s s of time...', amount=amount), amount=amount)
        flash(_('A time consuming task is currently in progress'))
    elif key == 'CHECK_CURRENCIES':
        current_user.launch_task('check_rates_yahoo', _('Checking currencies...'))
        flash(_('Checking online sources for currency rates'))
    elif key == 'UPDATE_CURRENCIES':
        source = request.args.get('source', 'yahoo', type=str)
        if source == 'yahoo':
            current_user.launch_task('update_rates_yahoo', _('Updating currencies...'))
        flash(_('Updating currency rates from known sources'))
    elif key == 'TYPE_ERROR':
        amount = request.args.get('amount', 1, type=int)
        for count in range(amount):
            current_user.launch_task(
                key.lower(),
                _('Creating %(count)s/%(amount)s errors of type %(error_type)s ...', count=count + 1, amount=amount, error_type=key),
            )
        flash(_('%(amount)s tasks with TypeErrors have been created', amount=amount))
    db.session.commit()
    return redirect(url_for('main.tasks'))


@bp.route('/statistics')
@login_required
def statistics():
    """Show model statistics (admin sees all models; users see a subset)."""
    log_page_access(request, current_user)
    if current_user.is_admin:
        classes = [Currency, User, Message, Notification, Image, Log, Task, Event, EventUser, EventCurrency, Expense, Settlement, Post]
    else:
        classes = [Message, Notification, Log, Task, Expense, Settlement, Event, EventUser, EventCurrency, Post]

    stats: list = []
    for c in classes:
        stats.extend(c.get_class_stats(current_user))

    return render_template('statistics.html', rows=stats, title=_('Statistics'))


# ---------------------------------------------------------------------------
# Profile / profile picture
# ---------------------------------------------------------------------------

@bp.route('/user/<guid>/popup')
@login_required
def user_popup(guid: str):
    """Render a user popup card."""
    log_page_access(request, current_user)
    u = User.get_by_guid_or_404(guid)
    return render_template('user_popup.html', user=u)


@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit the current user's own profile."""
    log_page_access(request, current_user)
    form = EditProfileForm(current_user.username)
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        current_user.locale = form.locale.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.user', guid=current_user.guid))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
        form.locale.data = current_user.locale
    return render_template('edit_form.html', title=_('Edit Profile'), form=form)


@bp.route('/edit_profile_picture', methods=['GET', 'POST'])
@login_required
def edit_profile_picture():
    """Upload a new profile picture."""
    log_page_access(request, current_user)
    form = ImageForm()
    if form.validate_on_submit():
        if 'image' not in request.files or request.files['image'].filename == '':
            flash(_('Invalid or empty image.'))
            return redirect(url_for('main.user', guid=current_user.guid))

        file_obj = request.files['image']
        try:
            new_image = process_and_store_image(file_obj.stream, file_obj.filename)
            current_user.profile_picture = new_image
            db.session.commit()
            flash(_('Your changes have been saved.'))
        except Exception as e:
            current_app.logger.error(f'Failed to upload profile picture: {e}')
            flash(_('An error occurred while uploading your image.'))

        return redirect(url_for('main.user', guid=current_user.guid))
    return render_template('edit_form.html', title=_('Profile Picture'), form=form)


# ---------------------------------------------------------------------------
# Messaging / notifications
# ---------------------------------------------------------------------------

@bp.route('/messages', methods=['GET', 'POST'])
@login_required
def messages():
    """List and compose direct messages."""
    log_page_access(request, current_user)
    current_user.last_message_read_time = datetime.now(timezone.utc)
    current_user.add_notification('unread_message_count', 0)
    db.session.commit()
    user_choices = [(u.id, u.username) for u in User.query.order_by(User.username.asc()) if u != current_user]
    form = MessageForm()
    form.recipient_id.choices = user_choices
    recipient_guid = request.args.get('recipient')

    if recipient_guid:
        recipient = User.get_by_guid_or_404(recipient_guid)
        form.recipient_id.data = recipient.id
    if form.validate_on_submit():
        recipient = db.session.get(User, form.recipient_id.data)
        msg = Message(author=current_user, recipient=recipient, body=form.message.data)
        db.session.add(msg)
        recipient.add_notification('unread_message_count', recipient.new_messages())
        db.session.commit()
        flash(_('Your message has been sent.'))
        return redirect(url_for('main.messages'))

    page = request.args.get('page', 1, type=int)
    pagination = current_user.messages_sent.union(current_user.messages_received).order_by(
        Message.timestamp.desc(),
    ).paginate(page=page, per_page=current_app.config['ITEMS_PER_PAGE'], error_out=False)
    next_url = url_for('main.messages', page=pagination.next_num) if pagination.has_next else None
    prev_url = url_for('main.messages', page=pagination.prev_num) if pagination.has_prev else None
    return render_template(
        'messages.html',
        title=_('Messages'),
        form=form,
        messages=pagination.items,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route('/notifications')
@login_required
def notifications():
    """Return new notifications as JSON (used for AJAX polling)."""
    since = request.args.get('since', 0.0, type=float)
    notifs = current_user.notifications.filter(
        Notification.timestamp > since,
    ).order_by(Notification.timestamp.asc())
    return jsonify([
        {'name': n.name, 'data': n.get_data(), 'timestamp': n.timestamp}
        for n in notifs
    ])


# ---------------------------------------------------------------------------
# Task launchers
# ---------------------------------------------------------------------------

@bp.route('/export_posts')
@login_required
def export_posts():
    """Launch a background job to export the user's posts."""
    log_page_access(request, current_user)
    if current_user.get_task_in_progress('export_posts'):
        flash(_('An export task is currently in progress'))
    else:
        current_user.launch_task('export_posts', _('Exporting posts...'))
        db.session.commit()
    return redirect(url_for('main.user', guid=current_user.guid))


@bp.route('/consume_time/<amount>')
@login_required
def consume_time(amount: str):
    """Launch a background job that burns wall-clock time (testing)."""
    log_page_access(request, current_user)
    if current_user.get_task_in_progress('consume_time'):
        flash(_('A time consuming task is currently in progress'))
    else:
        current_user.launch_task(
            'consume_time',
            _('Consuming %(amount)s s of time...', amount=amount),
            amount=int(amount),
        )
        db.session.commit()
    return redirect(url_for('main.user', guid=current_user.guid))
