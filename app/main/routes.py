# coding=utf-8
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
from app.models import Currency, Image, Log, User
from app.services.main_service import (
    create_currency,
    create_user,
    get_notifications,
    get_statistics,
    get_user,
    launch_task,
    list_currencies,
    list_logs,
    list_messages,
    list_tasks,
    list_users,
    mark_messages_read,
    remove_task,
    revoke_admin,
    rotate_image,
    send_message,
    set_admin,
    update_currency,
    update_profile,
    update_profile_picture,
    update_user,
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
def rotate_image_route(guid: str):
    """Rotate an image by the requested degree."""
    degree = request.args.get('degree', 0, type=int)
    img = rotate_image(guid, degree)
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
    result = list_currencies(page)
    next_url = url_for('main.currencies', page=result.next_num) if result.has_next else None
    prev_url = url_for('main.currencies', page=result.prev_num) if result.has_prev else None
    return render_template(
        'currencies.html',
        title=_('Current currencies'),
        currencies=result.items,
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
        create_currency(
            code=form.code.data,
            name=form.name.data,
            number=form.number.data,
            exponent=form.exponent.data,
            inCHF=form.inCHF.data,
            description=form.description.data,
            created_by=current_user.username,
        )
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
        update_currency(
            guid=guid,
            code=form.code.data,
            name=form.name.data,
            number=form.number.data,
            exponent=form.exponent.data,
            inCHF=form.inCHF.data,
            description=form.description.data,
        )
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
    result = list_users(page)
    next_url = url_for('main.users', page=result.next_num) if result.has_next else None
    prev_url = url_for('main.users', page=result.prev_num) if result.has_prev else None
    return render_template(
        'users.html',
        title=_('Current users'),
        users=result.items,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route('/user/<guid>')
@login_required
def user(guid: str):
    """Show a single user's profile."""
    u = get_user(guid)
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
        result = create_user(
            username=form.username.data,
            email=form.email.data,
            locale=form.locale.data,
            about_me=form.about_me.data,
            password=form.password.data,
            is_admin=form.is_admin.data,
        )
        flash(_('New user %(username)s created', username=result.user.username))
        return redirect(url_for('main.users'))
    return render_template('edit_form.html', title=_('New User'), form=form)


@bp.route('/edit_user/<guid>', methods=['GET', 'POST'])
@login_required
def edit_user_route(guid: str):
    """Edit an existing user (admin only)."""
    if not current_user.is_admin:
        flash(_('Only an admin can edit users!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.users'))
    log_page_access(request, current_user)
    u = get_user(guid)
    admin = User.query.filter_by(username='admin').first()
    if u == admin:
        flash(_('You cannot change the master admin!'))
        return redirect(url_for('main.users'))
    form = EditUserForm(u.username, u.email)
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    if form.validate_on_submit():
        result = update_user(
            guid=guid,
            username=form.username.data,
            email=form.email.data,
            locale=form.locale.data,
            about_me=form.about_me.data,
            is_admin=form.is_admin.data,
            password=form.password.data if form.password.data else None,
        )
        if not result.success:
            flash(_(result.error))
            return redirect(url_for('main.users'))
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
def set_admin_route(guid: str):
    """Grant admin privileges to a user."""
    u = get_user(guid)
    if not current_user.is_admin:
        flash(_('Only an admin can set the admin rights!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.user', guid=u.guid))
    log_page_access(request, current_user)
    set_admin(guid)
    return redirect(url_for('main.user', guid=u.guid))


@bp.route('/revoke_admin/<guid>')
@login_required
def revoke_admin_route(guid: str):
    """Revoke admin privileges from a user."""
    u = get_user(guid)
    admin = User.query.filter_by(username='admin').first()
    if u == admin:
        flash(_('You cannot change the master admin!'))
        return redirect(url_for('main.user', guid=u.guid))
    if not current_user.is_admin:
        flash(_('Only an admin can revoke the admin rights!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.user', guid=u.guid))
    log_page_access(request, current_user)
    revoke_admin(guid)
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
    result = list_logs(page, severity=severity, user=current_user, is_admin=current_user.is_admin)
    next_url = url_for('main.logs', severity=severity, page=result.next_num) if result.has_next else None
    prev_url = url_for('main.logs', severity=severity, page=result.prev_num) if result.has_prev else None
    return render_template('logs.html', logs=result.items, title=_('Logs'), next_url=next_url, prev_url=prev_url)


@bp.route('/log_trace/<id>')
@login_required
def log_trace(id: int):
    """Show the trace details of a single log entry."""
    from app.services.main_service import get_log_trace
    log = get_log_trace(id)
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
    result = list_tasks(page, complete=complete, user=current_user, is_admin=current_user.is_admin)
    next_url = url_for('main.tasks', complete=complete_str, page=result.next_num) if result.has_next else None
    prev_url = url_for('main.tasks', complete=complete_str, page=result.prev_num) if result.has_prev else None
    return render_template('tasks.html', tasks=result.items, title=_('Tasks'), next_url=next_url, prev_url=prev_url)


@bp.route('/remove_task/<guid>')
@login_required
def remove_task_route(guid: str):
    """Remove a completed task."""
    from app.models import Task as TaskModel
    task = TaskModel.get_by_guid_or_404(guid)
    if not task.can_edit(current_user):
        flash(_('Your are only allowed to delete your own task!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.tasks'))
    log_page_access(request, current_user)
    task_name = task.name
    task_username = task.user.username
    remove_task(guid)
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
    kwargs = {}

    if key == 'WASTE_TIME':
        kwargs['amount'] = request.args.get('amount', 10, type=int)
    elif key == 'UPDATE_CURRENCIES':
        kwargs['source'] = request.args.get('source', 'yahoo', type=str)
    elif key == 'TYPE_ERROR':
        kwargs['amount'] = request.args.get('amount', 1, type=int)

    result = launch_task(current_user, key, **kwargs)

    if key == 'WASTE_TIME':
        flash(_('A time consuming task is currently in progress'))
    elif key == 'CHECK_CURRENCIES':
        flash(_('Checking online sources for currency rates'))
    elif key == 'UPDATE_CURRENCIES':
        flash(_('Updating currency rates from known sources'))
    elif key == 'TYPE_ERROR':
        amount = kwargs.get('amount', 1)
        flash(_('%(amount)s tasks with TypeErrors have been created', amount=amount))

    return redirect(url_for('main.tasks'))


@bp.route('/statistics')
@login_required
def statistics():
    """Show model statistics (admin sees all models; users see a subset)."""
    log_page_access(request, current_user)
    stats = get_statistics(current_user, current_user.is_admin)
    return render_template('statistics.html', rows=stats, title=_('Statistics'))


# ---------------------------------------------------------------------------
# Profile / profile picture
# ---------------------------------------------------------------------------

@bp.route('/user/<guid>/popup')
@login_required
def user_popup(guid: str):
    """Render a user popup card."""
    log_page_access(request, current_user)
    u = get_user(guid)
    return render_template('user_popup.html', user=u)


@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit the current user's own profile."""
    log_page_access(request, current_user)
    form = EditProfileForm(current_user.username)
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    if form.validate_on_submit():
        update_profile(current_user, form.username.data, form.about_me.data, form.locale.data)
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
            update_profile_picture(current_user, file_obj.stream, file_obj.filename)
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
    mark_messages_read(current_user)
    user_choices = [(u.id, u.username) for u in User.query.order_by(User.username.asc()) if u != current_user]
    form = MessageForm()
    form.recipient_id.choices = user_choices
    recipient_guid = request.args.get('recipient')

    if recipient_guid:
        recipient = get_user(recipient_guid)
        form.recipient_id.data = recipient.id
    if form.validate_on_submit():
        result = send_message(current_user, form.recipient_id.data, form.message.data)
        if result.success:
            flash(_('Your message has been sent.'))
        return redirect(url_for('main.messages'))

    page = request.args.get('page', 1, type=int)
    msg_result = list_messages(current_user, page)
    next_url = url_for('main.messages', page=msg_result.next_num) if msg_result.has_next else None
    prev_url = url_for('main.messages', page=msg_result.prev_num) if msg_result.has_prev else None
    return render_template(
        'messages.html',
        title=_('Messages'),
        form=form,
        messages=msg_result.items,
        next_url=next_url,
        prev_url=prev_url,
    )


@bp.route('/notifications')
@login_required
def notifications():
    """Return new notifications as JSON (used for AJAX polling)."""
    since = request.args.get('since', 0.0, type=float)
    return jsonify(get_notifications(current_user, since))


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
