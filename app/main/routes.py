# coding=utf-8

from datetime import datetime
from flask import request, render_template, flash, redirect, url_for, jsonify, g, current_app
from flask_login import current_user, login_required
from flask_babel import get_locale, _
from flask_uploads import UploadNotAllowed

from app import db, images
from app.main import bp
from app.main.forms import EditProfileForm, PostForm, MessageForm, CurrencyForm, EventForm, EventAddUserForm, ExpenseForm, SettlementForm
from app.models import Currency, Event, Expense, Settlement, Post, User, Message, Notification

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
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    events = current_user.events.order_by(Event.date.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.index', page=events.next_num) if events.has_next else None
    prev_url = url_for('main.index', page=events.prev_num) if events.has_prev else None
    return render_template('index.html', 
                           title=_('Hi %(username)s, your events:', username=current_user.username), 
                           events=events.items, 
                           next_url=next_url, prev_url=prev_url)

@bp.route('/currencies')
@login_required
def currencies():
    page = request.args.get('page', 1, type=int)
    currencies = Currency.query.order_by(Currency.code.asc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.my_events', page=currencies.next_num) if currencies.has_next else None
    prev_url = url_for('main.my_events', page=currencies.prev_num) if currencies.has_prev else None
    return render_template('currencies.html', 
                           title=_('Current currencies'), 
                           currencies=currencies.items, 
                           next_url=next_url, prev_url=prev_url)
    
@bp.route('/users')
@login_required
def users():
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.username.asc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.users', page=users.next_num) if users.has_next else None
    prev_url = url_for('main.users', page=users.prev_num) if users.has_prev else None
    return render_template('users.html', 
                           title=_('Current users'), 
                           users=users.items, 
                           next_url=next_url, prev_url=prev_url)
    
@bp.route('/event/<event_id>', methods=['GET', 'POST'])
@login_required
def event(event_id):
    event = Event.query.get_or_404(event_id)
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body=form.post.data, author=current_user, timestamp=datetime.utcnow(), event=event)
        db.session.add(post)
        db.session.commit()
        flash(_('Your post is now live!'))
        return redirect(url_for('main.event', event_id=event_id))
    
    page = request.args.get('page', 1, type=int)
    posts = event.posts.order_by(Post.timestamp.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.event', event_id=event.id, page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.event', event_id=event.id, page=posts.prev_num) if posts.has_prev else None
    return render_template('event.html', 
                           form=form, 
                           event=event, 
                           posts=posts.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/event_users/<event_id>', methods=['GET', 'POST'])
@login_required
def event_users(event_id):
    event = Event.query.get_or_404(event_id)
    admins = User.query.filter_by(username='admin').all()
    admins.append(event.admin)
    form = EventAddUserForm()
    form.user_id.choices = [(u.id, u.username) for u in User.query.order_by('username') if u not in admins]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', event_id=event.id))
        user = User.query.get(form.user_id.data)
        event.add_user(user)
        db.session.commit()
        flash(_('User %(username)s has been added to event %(event_name)s.', username=user.username, event_name=event.name))
        return redirect(url_for('main.event_users', event_id=event_id))
    
    page = request.args.get('page', 1, type=int)
    users = event.users.order_by(User.username.asc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.event_users', event_id=event.id, page=users.next_num) if users.has_next else None
    prev_url = url_for('main.event_users', event_id=event.id, page=users.prev_num) if users.has_prev else None
    return render_template('event_users.html', 
                           form=form, 
                           event=event, 
                           users=users.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/event_expenses/<event_id>', methods=['GET', 'POST'])
@login_required
def event_expenses(event_id):
    event = Event.query.get_or_404(event_id)
    form = ExpenseForm()
    form.currency_id.choices = [(c.id, c.code) for c in Currency.query.order_by('code')]
    form.affected_users_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', event_id=event.id))
        expense = Expense(user=current_user, 
                          event=event, 
                          currency=Currency.query.get(form.currency_id.data), 
                          amount=form.amount.data, 
                          affected_users=[User.query.get(user_id) for user_id in form.affected_users_id.data], 
                          date=form.date.data,
                          description=form.description.data, 
                          db_created_by=current_user.username)
        
        db.session.add(expense)
        db.session.commit()
        flash(_('Your new expense has been added to event %(event_name)s.', event_name=event.name))
        return redirect(url_for('main.event_expenses', event_id=event_id))
    
    page = request.args.get('page', 1, type=int)
    expenses = event.expenses.order_by(Expense.date.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.event_expenses', event_id=event.id, page=expenses.next_num) if expenses.has_next else None
    prev_url = url_for('main.event_expenses', event_id=event.id, page=expenses.prev_num) if expenses.has_prev else None
    return render_template('event_expenses.html', 
                           form=form, 
                           event=event, 
                           expenses=expenses.items,
                           next_url=next_url, prev_url=prev_url)
    
@bp.route('/event_settlements/<event_id>', methods=['GET', 'POST'])
@login_required
def event_settlements(event_id):
    event = Event.query.get_or_404(event_id)
    form = SettlementForm()
    form.currency_id.choices = [(c.id, c.code) for c in Currency.query.order_by('code')]
    form.recipient_id.choices = [(u.id, u.username) for u in event.users if u!=current_user]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', event_id=event.id))
        settlement = Settlement(sender=current_user, 
                                recipient=User.query.get(form.recipient_id.data), 
                                event=event, 
                                currency=Currency.query.get(form.currency_id.data), 
                                amount=form.amount.data, 
                                draft=False,
                                date=datetime.utcnow(),
                                description=form.description.data, 
                                db_created_by=current_user.username)
        
        db.session.add(settlement)
        db.session.commit()
        flash(_('Your new settlement has been added to event %(event_name)s.', event_name=event.name))
        return redirect(url_for('main.event_settlements', event_id=event_id))
    
    page = request.args.get('page', 1, type=int)
    settlements = event.settlements.filter_by(draft=False).order_by(Settlement.date.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.event_settlements', event_id=event.id, page=settlements.next_num) if settlements.has_next else None
    prev_url = url_for('main.event_settlements', event_id=event.id, page=settlements.prev_num) if settlements.has_prev else None
    return render_template('event_settlements.html', 
                           form=form, 
                           event=event, 
                           settlements=settlements.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/event_balance/<event_id>', methods=['GET'])
@login_required
def event_balance(event_id):
    event = Event.query.get_or_404(event_id)
    
    balances = [event.get_user_balance(u) for u in event.users]
    balances_str = list(map(lambda x: (x[0], 
                                       event.base_currency.get_amount_as_str(x[1]), 
                                       event.base_currency.get_amount_as_str(x[2]), 
                                       event.base_currency.get_amount_as_str(x[3]), 
                                       event.base_currency.get_amount_as_str(x[4]), 
                                       event.base_currency.get_amount_as_str(x[5])) 
                                       , balances))
    
    total_expenses = event.get_total_expenses()
    total_expenses_str = event.base_currency.get_amount_as_str(total_expenses)
    
    event.settlements.filter_by(draft=True).delete()
    draft_settlements = event.get_compensation_settlements_accountant()
    db.session.add_all(draft_settlements)
    db.session.commit()
    
    return render_template('event_balance.html', 
                           event=event, 
                           draft_settlements=draft_settlements,
                           balances_str=balances_str, 
                           total_expenses_str=total_expenses_str)

@bp.route('/event_balance/pay/<settlement_id>', methods=['GET'])
@login_required
def event_settlement_execute(settlement_id):
    settlement = Settlement.query.get_or_404(settlement_id)
    settlement.draft = False
    db.session.commit()
    return redirect(url_for('main.event_balance', event_id=settlement.event.id))
    
@bp.route('/event_add_user/<event_id>/<username>')
@login_required
def event_add_user(event_id, username):
    event = Event.query.get_or_404(event_id)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('main.event', event_id=event.id))
    user = User.query.filter_by(username=username).first_or_404()
    if user == event.admin:
        flash(_('You cannot add the event admin as user!'))
        return redirect(url_for('main.event_users', event_id=event.id))
    event.add_user(user)
    db.session.commit()
    flash(_('User %(username)s has been added to event %(event_name)s.', username=user.username, event_name=event.name))
    return redirect(url_for('main.event_users', event_id=event_id))

@bp.route('/event_remove_user/<event_id>/<username>')
@login_required
def event_remove_user(event_id, username):
    event = Event.query.get_or_404(event_id)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('main.event', event_id=event.id))
    user = User.query.filter_by(username=username).first_or_404()
    if user == event.admin:
        flash(_('You cannot remove the event admin!'))
        return redirect(url_for('main.event_users', event_id=event.id))
    event.remove_user(user)
    db.session.commit()
    flash(_('User %(username)s has been removed from event %(event_name)s.', username=user.username, event_name=event.name))
    return redirect(url_for('main.event_users', event_id=event_id))

@bp.route('/event_edit_expense/<event_id>/<expense_id>', methods=['GET', 'POST'])
@login_required
def event_edit_expense(event_id, expense_id):
    event = Event.query.get_or_404(event_id)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('main.event', event_id=event.id))
    expense = Expense.query.get_or_404(expense_id)
    if current_user not in [event.admin, expense.user]:
        flash(_('Your are only allowed to edit your own expenses!'))
        return redirect(url_for('main.event_expenses', event_id=event.id))
    form = ExpenseForm()
    form.currency_id.choices = [(c.id, c.code) for c in Currency.query.order_by('code')]
    form.affected_users_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        expense.currency = Currency.query.get(form.currency_id.data)
        expense.amount = form.amount.data
        expense.affected_users = [User.query.get(user_id) for user_id in form.affected_users_id.data]
        expense.date = form.date.data
        expense.description = form.description.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.event_expenses', event_id=event_id))
    elif request.method == 'GET':
        form.currency_id.data = expense.currency.id
        form.amount.data = expense.amount
        form.affected_users_id.data = [u.id for u in expense.affected_users]
        form.date.data = expense.date
        form.description.data = expense.description
    return render_template('edit_form.html', 
                           title=_('Edit Expense'), 
                           form=form)

@bp.route('/event_edit_settlement/<event_id>/<settlement_id>', methods=['GET', 'POST'])
@login_required
def event_edit_settlement(event_id, settlement_id):
    event = Event.query.get_or_404(event_id)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('main.event', event_id=event.id))
    settlement = Settlement.query.get_or_404(settlement_id)
    if current_user not in [event.admin, settlement.sender]:
        flash(_('Your are only allowed to edit your own settlements!'))
        return redirect(url_for('main.event_settlements', event_id=event.id))
    form = SettlementForm()
    form.currency_id.choices = [(c.id, c.code) for c in Currency.query.order_by('code')]
    form.recipient_id.choices = [(u.id, u.username) for u in event.users if u!=current_user]
    if form.validate_on_submit():
        settlement.currency = Currency.query.get(form.currency_id.data)
        settlement.amount = form.amount.data
        settlement.recipient = User.query.get(form.recipient_id.data)
        settlement.description = form.description.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.event_settlements', event_id=event_id))
    elif request.method == 'GET':
        form.currency_id.data = settlement.currency.id
        form.amount.data = settlement.amount
        form.recipient_id.data = settlement.recipient.id
        form.description.data = settlement.description
    return render_template('edit_form.html', 
                           title=_('Edit Settlement'), 
                           form=form)

@bp.route('/event_remove_expense/<event_id>/<expense_id>')
@login_required
def event_remove_expense(event_id, expense_id):
    event = Event.query.get_or_404(event_id)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('main.event', event_id=event.id))
    expense = Expense.query.get_or_404(expense_id)
    if current_user not in [event.admin, expense.user]:
        flash(_('Your are only allowed to remove your own expenses!'))
        return redirect(url_for('main.event_expenses', event_id=event.id))
    if expense in event.expenses:
        event.expenses.remove(expense)
    db.session.commit()
    flash(_('Expense over %(amount_str)s has been removed from event %(event_name)s.', amount_str=expense.get_amount_str(), event_name=event.name))
    return redirect(url_for('main.event_expenses', event_id=event_id))

@bp.route('/event_remove_settlement/<event_id>/<settlement_id>')
@login_required
def event_remove_settlement(event_id, settlement_id):
    event = Event.query.get_or_404(event_id)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('main.event', event_id=event.id))
    settlement = Settlement.query.get_or_404(settlement_id)
    if current_user not in [event.admin, settlement.sender]:
        flash(_('Your are only allowed to remove your own settlements!'))
        return redirect(url_for('main.event_settlements', settlement_id=settlement.id))
    if settlement in event.settlements:
        event.settlements.remove(settlement)
    db.session.commit()
    flash(_('Settlement over %(amount_str)s has been removed from event %(event_name)s.', amount_str=settlement.get_amount_str(), event_name=event.name))
    return redirect(url_for('main.event_settlements', event_id=event_id))

@bp.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.user', username=user.username, page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.user', username=user.username, page=posts.prev_num) if posts.has_prev else None
    return render_template('user.html', 
                           user=user, 
                           posts=posts.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/user/<username>/popup')
@login_required
def user_popup(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('user_popup.html', user=user)

@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    form.timezone.choices = [(x, x) for x in current_app.config['TIMEZONES']]
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        current_user.locale = form.locale.data
        current_user.timezone = form.timezone.data
        if 'image' in request.files:
            image_filename = images.save(request.files['image'])
            image_path = images.path(image_filename)
            current_user.launch_task('import_image', _('Importing %(filename)s...', filename=image_filename), path=image_path, add_to_class='User', add_to_id=current_user.id)
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.user', username=current_user.username))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
        form.locale.data = current_user.locale
        form.timezone.data = current_user.timezone
    return render_template('edit_form.html', 
                           title=_('Edit Profile'), 
                           form=form)

@bp.route('/messages', methods=['GET', 'POST'])
@login_required
def messages():
    current_user.last_message_read_time = datetime.utcnow()
    current_user.add_notification('unread_message_count', 0)
    db.session.commit()
    users = [(u.id, u.username) for u in User.query.order_by('username') if u != current_user]
    form = MessageForm()
    form.recipient_id.choices = users
    recipient_username = request.args.get('recipient')
    if recipient_username:
        recipient = User.query.filter_by(username=recipient_username).first_or_404()
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
    messages = current_user.messages_received.order_by(
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
    if current_user.get_task_in_progress('export_posts'):
        flash(_('An export task is currently in progress'))
    else:
        current_user.launch_task('export_posts', _('Exporting posts...'))
        db.session.commit()
    return redirect(url_for('main.user', username=current_user.username))

@bp.route('/consume_time/<amount>')
@login_required
def consume_time(amount):
    if current_user.get_task_in_progress('consume_time'):
        flash(_('A time consuming task is currently in progress'))
    else:
        current_user.launch_task('consume_time', _('Consuming time...'))
        db.session.commit()
    return redirect(url_for('main.user', username=current_user.username))

@bp.route('/new_currency', methods=['GET', 'POST'])
@login_required
def new_currency():
    form = CurrencyForm()
    if form.validate_on_submit():
        currency = Currency(code=form.code.data, name=form.name.data, 
                            number=form.number.data, exponent=form.exponent.data, 
                            inCHF=form.inCHF.data, description=form.description.data, 
                            db_created_by=current_user.username)
        
        db.session.add(currency)
        db.session.commit()
        flash(_('Your new currency has been added.'))
        return redirect(url_for('main.currencies'))
    return render_template('edit_form.html', 
                           title=_('New Currency'), 
                           form=form)

@bp.route('/edit_currency/<currency_id>', methods=['GET', 'POST'])
@login_required
def edit_currency(currency_id):
    currency = Currency.query.get_or_404(currency_id)
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

@bp.route('/new_event', methods=['GET', 'POST'])
@login_required
def new_event():
    admins = User.query.filter_by(username='admin').all()
    users = [(u.id, u.username) for u in User.query.order_by('username') if u not in admins]
    form = EventForm()
    form.admin_id.choices = users
    form.admin_id.data = current_user.id
    form.accountant_id.choices = users
    form.accountant_id.data = current_user.id
    form.base_currency_id.choices = [(c.id, c.code) for c in Currency.query.order_by('code')]
    if form.validate_on_submit():
        admin = User.query.get(form.admin_id.data)
        accountant = User.query.get(form.accountant_id.data)
        base_currency = Currency.query.get(form.base_currency_id.data)
        event = Event(name=form.name.data, 
                      date=form.date.data,
                      admin=admin,
                      accountant=accountant,
                      base_currency=base_currency,
                      exchange_fee=form.exchange_fee.data,
                      closed=False,
                      description=form.description.data, 
                      db_created_by=current_user.username)
        event.add_user(admin)
        event.add_user(accountant)
        db.session.add(event)
        try:
            image_filename = images.save(request.files['image'])
            image_path = images.path(image_filename)
            current_user.launch_task('import_image', _('Importing %(filename)s...', filename=image_filename), path=image_path, add_to_class='Event', add_to_id=event.id)
        except UploadNotAllowed:
            flash(_('Invalid or empty image.'))
        
        db.session.commit()
        flash(_('Your new event has been added.'))
        return redirect(url_for('main.event', event_id=event.id))
    return render_template('edit_form.html', 
                           title=_('New Event'), 
                           form=form)

@bp.route('/edit_event/<event_id>', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    if current_user != event.admin:
        flash(_('Your are only allowed to edit your own event!'))
        return redirect(url_for('main.event', event_id=event.id))
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('main.event', event_id=event.id))
    form = EventForm()
    form.admin_id.choices = [(u.id, u.username) for u in event.users.order_by('username')]
    form.accountant_id.choices = [(u.id, u.username) for u in event.users.order_by('username')]
    form.base_currency_id.choices = [(c.id, c.code) for c in Currency.query.order_by('code')]
    if form.validate_on_submit():
        event.name = form.name.data
        event.date = form.date.data
        event.description = form.description.data
        event.admin = User.query.get(form.admin_id.data)
        event.accountant = User.query.get(form.accountant_id.data)
        event.base_currency = Currency.query.get(form.base_currency_id.data)
        event.exchange_fee = form.exchange_fee.data
        try:
            image_filename = images.save(request.files['image'])
            image_path = images.path(image_filename)
            current_user.launch_task('import_image', _('Importing %(filename)s...', filename=image_filename), path=image_path, add_to_class='Event', add_to_id=event.id)
        except UploadNotAllowed:
            flash(_('Invalid or empty image.'))
        
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.event', event_id=event_id))
    elif request.method == 'GET':
        form.name.data = event.name
        form.date.data = event.date
        form.description.data = event.description
        form.admin_id.data = event.admin_id
        form.accountant_id.data = event.accountant_id
        form.base_currency_id.data = event.base_currency_id
        form.exchange_fee.data = event.exchange_fee
    return render_template('edit_form.html', 
                           title=_('Edit Event'), 
                           form=form)

@bp.route('/event_convert_currencies/<event_id>')
@login_required
def event_convert_currencies(event_id):
    event = Event.query.get_or_404(event_id)
    if current_user != event.admin:
        flash(_('Your are only allowed to convert currencies of your own event!'))
        return redirect(url_for('main.event', event_id=event.id))
    event.convert_currencies()
    db.session.commit()
    flash(_('All transaction of this event have been converted to %(code)s.', code=event.base_currency.code))
    return redirect(url_for('main.event', event_id=event.id))

@bp.route('/reopen_event/<event_id>')
@login_required
def reopen_event(event_id):
    event = Event.query.get_or_404(event_id)
    if current_user != event.admin:
        flash(_('Your are only allowed to reopen your own event!'))
        return redirect(url_for('main.event', event_id=event.id))
    event.closed = False
    db.session.commit()
    flash(_('Event has been reopened.'))
    return redirect(url_for('main.event', event_id=event.id))

@bp.route('/close_event/<event_id>')
@login_required
def close_event(event_id):
    event = Event.query.get_or_404(event_id)
    if current_user != event.admin:
        flash(_('Your are only allowed to close your own event!'))
        return redirect(url_for('main.event', event_id=event.id))
    if event.settlements.filter_by(draft=True).all():
        flash(_('Your are only allowed to close an event with no open liabilities!'))
        return redirect(url_for('main.event', event_id=event.id))
    event.closed = True
    db.session.commit()
    flash(_('Event has been closed.'))
    return redirect(url_for('main.event', event_id=event.id))
