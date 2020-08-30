# coding=utf-8

from datetime import datetime
from flask import request, render_template, make_response, flash, redirect, url_for, jsonify, g, current_app
from flask_login import current_user, login_required
from flask_uploads import UploadNotAllowed
from flask_babel import get_locale, _

from app import db, images
from app.main import bp
from app.main.forms import ImageForm, EditProfileForm, MessageForm, CurrencyForm, NewUserForm, EditUserForm
from app.models import Currency, User, Message, Notification, Image, Log, Task, Event, EventUser, EventCurrency, Expense, Settlement, Post
from app.db_logging import log_page_access, log_page_access_denied

@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
    g.locale = str(get_locale())

# routes for rendered pages
@bp.route('/')
def root():
    return redirect(url_for('main.index'))

@bp.route('/index')
def index():
    return redirect(url_for('event.index'))

@bp.route('/image/<guid>')
@login_required
def image(guid):
    log_page_access(request, current_user)
    image = Image.get_by_guid_or_404(guid)
    return render_template('image.html', 
                           title=_('Image'), 
                           image=image,
                           allow_turning=(not image.vector))

@bp.route('/rotate_image/<guid>')
@login_required
def rotate_image(guid):
    degree = request.args.get('degree', 0, type=int)
    image = Image.get_by_guid_or_404(guid)
    image.rotate_image(degree)
    log_page_access(request, current_user)
    return redirect(url_for('main.image', guid=image.guid))

@bp.route('/currencies')
@login_required
def currencies():
    log_page_access(request, current_user)
    page = request.args.get('page', 1, type=int)
    currencies = Currency.query.order_by(Currency.code.asc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.currencies', page=currencies.next_num) if currencies.has_next else None
    prev_url = url_for('main.currencies', page=currencies.prev_num) if currencies.has_prev else None
    return render_template('currencies.html', 
                           title=_('Current currencies'), 
                           currencies=currencies.items, 
                           allow_new=current_user.is_admin,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/new_currency', methods=['GET', 'POST'])
@login_required
def new_currency():
    if not current_user.is_admin:
        flash(_('Only an admin is allowed to create new currencies!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.currencies'))
    log_page_access(request, current_user)
    form = CurrencyForm()
    if form.validate_on_submit():
        currency = Currency(code=form.code.data, 
                            name=form.name.data, 
                            number=form.number.data, 
                            exponent=form.exponent.data, 
                            inCHF=form.inCHF.data, 
                            description=form.description.data, 
                            db_created_by=current_user.username)
        
        db.session.add(currency)
        db.session.commit()
        flash(_('Your new currency has been added.'))
        return redirect(url_for('main.currencies'))
    return render_template('edit_form.html', 
                           title=_('New Currency'), 
                           form=form)

@bp.route('/edit_currency/<guid>', methods=['GET', 'POST'])
@login_required
def edit_currency(guid):
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
    return render_template('edit_form.html', 
                           title=_('Edit Currency'), 
                           form=form)

@bp.route('/users')
@login_required
def users():
    log_page_access(request, current_user)
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.username.asc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.users', page=users.next_num) if users.has_next else None
    prev_url = url_for('main.users', page=users.prev_num) if users.has_prev else None
    return render_template('users.html', 
                           title=_('Current users'), 
                           users=users.items, 
                           next_url=next_url, prev_url=prev_url)

@bp.route('/user/<guid>')
@login_required
def user(guid):
    user = User.get_by_guid_or_404(guid)
    log_page_access(request, current_user)
    return render_template('user.html', 
                           title= _('User %(username)s', username = user.username), 
                           user=user)

@bp.route('/new_user', methods=['GET', 'POST'])
def new_user():
    if not current_user.is_admin:
        flash(_('Only an admin can create new users!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.users'))
    log_page_access(request, current_user)
    form = NewUserForm()
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    if form.validate_on_submit():
        user = User(username=form.username.data, 
                    email=form.email.data,
                    locale=form.locale.data,
                    about_me=form.about_me.data)
        user.is_admin = form.is_admin.data
        user.set_password(form.password.data)
        user.get_token()
        db.session.add(user)
        db.session.commit()
        flash(_('New user %(username)s created', username = user.username))
        return redirect(url_for('main.users'))
    return render_template('edit_form.html', title=_('New User'), form=form)

@bp.route('/edit_user/<guid>', methods=['GET', 'POST'])
def edit_user(guid):
    if not current_user.is_admin:
        flash(_('Only an admin can edit users!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.users'))
    log_page_access(request, current_user)
    user = User.get_by_guid_or_404(guid)
    admin = User.query.filter_by(username='admin').first()
    if user==admin:
        flash(_('You cannot change the master admin!'))
        return redirect(url_for('main.users'))
    form = EditUserForm(user.username, user.email)
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    if form.validate_on_submit():
        user.username=form.username.data, 
        user.email=form.email.data,
        user.locale=form.locale.data,
        user.about_me = form.about_me.data
        user.is_admin = form.is_admin.data
        if form.password.data:
            user.set_password(form.password.data)
        user.get_token()
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.users'))
    elif request.method == 'GET':
        form.username.data = user.username
        form.email.data = user.email
        form.locale.data = user.locale
        form.about_me.data = user.about_me
        form.is_admin.data = user.is_admin
    return render_template('edit_form.html', title=_('Edit User'), form=form)

@bp.route('/set_admin/<guid>')
@login_required
def set_admin(guid):
    user = User.get_by_guid_or_404(guid)
    if not current_user.is_admin:
        flash(_('Only an admin can set the admin rights!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.user', username=user.username))
    log_page_access(request, current_user)
    user.is_admin = True
    db.session.commit()
    return redirect(url_for('main.user', guid=user.guid))

@bp.route('/revoke_admin/<guid>')
@login_required
def revoke_admin(guid):
    user = User.get_by_guid_or_404(guid)
    admin = User.query.filter_by(username='admin').first()
    if user==admin:
        flash(_('You cannot change the master admin!'))
        return redirect(url_for('main.user', guid=user.guid))
    if not current_user.is_admin:
        flash(_('Only an admin can revoke the admin rights!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.user', guid=user.guid))
    log_page_access(request, current_user)
    user.is_admin = False
    db.session.commit()
    return redirect(url_for('main.user', guid=user.guid))

@bp.route('/administration')
@login_required
def administration():
    log_page_access(request, current_user)
    return render_template('administration.html',
                           title= _('Administration'))

@bp.route('/logs')
@login_required
def logs():
    log_page_access(request, current_user)
    page = request.args.get('page', 1, type=int)
    severity = request.args.get('severity', None, type=str)
    filters = []
    if severity is not None:
        filters.append(Log.severity==severity.upper())
    if not current_user.is_admin:
        filters.append(Log.user==current_user)
    logs = Log.query.filter(*filters).order_by(Log.date.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.logs', page=logs.next_num) \
        if logs.has_next else None
    prev_url = url_for('main.logs', page=logs.prev_num) \
        if logs.has_prev else None
    return render_template('logs.html',
                           logs=logs.items,
                           title= _('Logs'),
                           next_url=next_url, prev_url=prev_url)


@bp.route('/log_trace/<id>')
@login_required
def log_trace(id):
    log = Log.query.get_or_404(id)
    if not log.can_view(current_user):
        flash(_('Your are only allowed to view your own logs!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.logs'))
    log_page_access(request, current_user)
    return render_template('trace.html',
                           log=log,
                           title= _('Trace'))

@bp.route('/create_error')
@login_required
def create_error():
    if not current_user.is_admin:
        flash(_('Only an admin can create errors!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.logs'))
    log_page_access(request, current_user)
    
    key = request.args.get('key', 'TYPE_ERROR', type=str)
    
    if key=='TYPE_ERROR':
        test_str = 'asdf'
        test_number = test_str + 5
        flash(_('This flash should never show up: %(test_number)s', test_number=test_number))
    db.session.commit()
    return redirect(url_for('main.logs'))
    
@bp.route('/tasks')
@login_required
def tasks():
    log_page_access(request, current_user)
    page = request.args.get('page', 1, type=int)
    complete_str = request.args.get('complete', None, type=str)
    complete = (False if complete_str=='False' else True if complete_str=='True' else None)
    filters = []
    if complete is not None:
        filters.append(Task.complete==complete)
    if not current_user.is_admin:
        filters.append(Task.user==current_user)
    tasks = Task.query.filter(*filters).order_by(Task.db_created_at.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.tasks', page=tasks.next_num) \
        if tasks.has_next else None
    prev_url = url_for('main.tasks', page=tasks.prev_num) \
        if tasks.has_prev else None
    return render_template('tasks.html',
                           tasks=tasks.items,
                           title= _('Tasks'),
                           next_url=next_url, prev_url=prev_url)

@bp.route('/remove_task/<guid>')
@login_required
def remove_task(guid):
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
    if not current_user.is_admin:
        flash(_('Only an admin can start tasks!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('main.tasks'))
    log_page_access(request, current_user)
    
    key = request.args.get('key', 'WASTE_TIME', type=str)
    
    if key=='WASTE_TIME':
        amount = request.args.get('amount', 10, type=int)
        current_user.launch_task('consume_time', _('Consuming %(amount)s s of time...', amount=amount), amount=amount)
        flash(_('A time consuming task is currently in progress'))
    elif key=='CHECK_CURRENCIES':
        current_user.launch_task('check_rates_yahoo', _('Checking currencies...'))
        flash(_('Checking online sources for currencie rates'))
    elif key=='UPDATE_CURRENCIES':
        source = request.args.get('source', 'yahoo', type=str)
        if source=='yahoo':
            current_user.launch_task('update_rates_yahoo', _('Updating currencies...'))
        flash(_('Updating currencie rates from known sources'))
    elif key=='TYPE_ERROR':
        amount = request.args.get('amount', 1, type=int)
        for count in range(0, amount):
          current_user.launch_task(key.lower(), _('Creating %(count)s/%(amount)s errors of type %(error_type)s ...', count=count+1, amount=amount, error_type=key))
        flash(_('%(amount)s tasks with TypeErrors have been created', amount=amount))
    db.session.commit()
    return redirect(url_for('main.tasks'))

@bp.route('/statistics')
@login_required
def statistics():
    log_page_access(request, current_user)
    if current_user.is_admin:
        classes = [Currency, User, Message, Notification, Image, Log, Task, Event, EventUser, EventCurrency, Expense, Settlement, Post]
    else:
        classes = [Message, Notification, Log, Task, Expense, Settlement, Event, EventUser, EventCurrency, Post]

    statistics = []
    for c in classes:
        statistics.extend(c.get_class_stats(current_user))
    
    return render_template('statistics.html',
                           rows=statistics,
                           title= _('Statistics'))

@bp.route('/user/<guid>/popup')
@login_required
def user_popup(guid):
    log_page_access(request, current_user)
    user = User.get_by_guid_or_404(guid)
    return render_template('user_popup.html', user=user)

@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
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
    return render_template('edit_form.html', 
                           title=_('Edit Profile'), 
                           form=form)

@bp.route('/edit_profile_picture', methods=['GET', 'POST'])
@login_required
def edit_profile_picture():
    log_page_access(request, current_user)
    form = ImageForm()
    if form.validate_on_submit():
        try:
            image_filename = images.save(request.files['image'])
            image_path = images.path(image_filename)
            current_user.launch_task('import_image', _('Importing %(filename)s...', filename=image_filename), path=image_path, add_to_class='User', add_to_id=current_user.id)
            db.session.commit()
            flash(_('Your changes have been saved.'))
        except UploadNotAllowed:
            flash(_('Invalid or empty image.'))
        return redirect(url_for('main.user', guid=current_user.guid))
    return render_template('edit_form.html', 
                           title=_('Profile Picture'), 
                           form=form)

@bp.route('/messages', methods=['GET', 'POST'])
@login_required
def messages():
    log_page_access(request, current_user)
    current_user.last_message_read_time = datetime.utcnow()
    current_user.add_notification('unread_message_count', 0)
    db.session.commit()
    users = [(u.id, u.username) for u in User.query.order_by(User.username.asc()) if u != current_user]
    form = MessageForm()
    form.recipient_id.choices = users
    recipient_guid = request.args.get('recipient')
    if recipient_guid:
        recipient = User.get_by_guid_or_404(recipient_guid)
        form.recipient_id.data = recipient.id
    if form.validate_on_submit():
        recipient = User.query.get(form.recipient_id.data)
        msg = Message(author=current_user, 
                      recipient=recipient,
                      body=form.message.data)
        db.session.add(msg)
        recipient.add_notification('unread_message_count', recipient.new_messages())
        db.session.commit()
        flash(_('Your message has been sent.'))
        return redirect(url_for('main.messages'))
    page = request.args.get('page', 1, type=int)
    messages = current_user.messages_sent.union(current_user.messages_received).order_by(
        Message.timestamp.desc()).paginate(
            page, current_app.config['MESSAGES_PER_PAGE'], False)
    next_url = url_for('main.messages', page=messages.next_num) \
        if messages.has_next else None
    prev_url = url_for('main.messages', page=messages.prev_num) \
        if messages.has_prev else None
    return render_template('messages.html', 
                           title=_('Messages'),
                           form=form,
                           messages=messages.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/notifications')
@login_required
def notifications():
    since = request.args.get('since', 0.0, type=float)
    notifications = current_user.notifications.filter(
        Notification.timestamp > since).order_by(Notification.timestamp.asc())
    return jsonify([{
        'name': n.name,
        'data': n.get_data(),
        'timestamp': n.timestamp
    } for n in notifications])

@bp.route('/export_posts')
@login_required
def export_posts():
    log_page_access(request, current_user)
    if current_user.get_task_in_progress('export_posts'):
        flash(_('An export task is currently in progress'))
    else:
        current_user.launch_task('export_posts', _('Exporting posts...'))
        db.session.commit()
    return redirect(url_for('main.user', guid=current_user.guid))

@bp.route('/consume_time/<amount>')
@login_required
def consume_time(amount):
    log_page_access(request, current_user)
    if current_user.get_task_in_progress('consume_time'):
        flash(_('A time consuming task is currently in progress'))
    else:
        current_user.launch_task('consume_time', _('Consuming %(amount)s s of time...', amount=amount), amount=int(amount))
        db.session.commit()
    return redirect(url_for('main.user', guid=current_user.guid))

@bp.route('/cookies')
@login_required
def cookies():
    log_page_access(request, current_user)
    
    cookies = [(k, v) for k, v in request.cookies.items()]
    print(cookies)
    return render_template('statistics.html',
                           rows=cookies,
                           title= _('Cookies'))

@bp.route('/setcookie/<text>')
@login_required
def setcookie(text):
    log_page_access(request, current_user)
    response = make_response('<h1>Text from the cookie: </h1><br>' + text)
    response.set_cookie('TESTtext', text)
    return response

@bp.route('/getcookie')
@login_required
def getcookie():
    log_page_access(request, current_user)
    text = request.cookies.get('TESTtext')
    response = make_response(('<h1>Text from the cookie: </h1><br>' + text) if text is not None else '<h1>No cookie found</h1>')
    return response