# coding=utf-8

from datetime import datetime
from flask import request, render_template, flash, redirect, url_for, current_app
from flask_login import current_user, login_required
from flask_uploads import UploadNotAllowed
from flask_babel import _

from app import db, images
from app.event import bp
from app.main.forms import ImageForm
from app.event.forms import PostForm, EventForm, EventUserForm, ExpenseAddUserForm, ExpenseForm, SettlementForm, SetRateForm
from app.models import Currency, Event, EventUser, EventCurrency, Expense, Settlement, Post, Image
from app.db_logging import log_page_access, log_page_access_denied

# routes for rendered pages
@bp.route('/index')
@login_required
def index():
    log_page_access(request, current_user)
    page = request.args.get('page', 1, type=int)
    if current_user.is_admin:
        events = Event.query.order_by(Event.closed.asc(), Event.date.desc()).paginate(
            page, current_app.config['ITEMS_PER_PAGE'], False)
    else:
        events = current_user.events_admin.order_by(Event.closed.asc(), Event.date.desc()).paginate(
            page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.index', page=events.next_num) if events.has_next else None
    prev_url = url_for('event.index', page=events.prev_num) if events.has_prev else None
    return render_template('event/index.html', 
                           title=_('Hi %(username)s, your events:', username=current_user.username), 
                           events=events.items, 
                           next_url=next_url, prev_url=prev_url)

@bp.route('/user/<guid>')
def user(guid):
    user = EventUser.get_by_guid_or_404(guid)
    log_page_access(request, current_user)
    return render_template('event/user.html', 
                           title= _('User %(username)s', username = user.username), 
                           user=user)

@bp.route('/main/<guid>', methods=['GET', 'POST'])
def main(guid):
    event = Event.get_by_guid_or_404(guid)
    log_page_access(request, current_user)
    form = PostForm()
    form.user_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        post = Post(body=form.post.data, 
                    author=EventUser.query.get(form.user_id.data), 
                    timestamp=datetime.utcnow(), 
                    event=event)
        db.session.add(post)
        db.session.commit()
        flash(_('Your post is now live!'))
        return redirect(url_for('event.main', guid=guid))
    
    page = request.args.get('page', 1, type=int)
    posts = event.posts.order_by(Post.timestamp.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.main', guid=event.guid, page=posts.next_num) if posts.has_next else None
    prev_url = url_for('event.main', guid=event.guid, page=posts.prev_num) if posts.has_prev else None
    return render_template('event/main.html', 
                           form=form, 
                           event=event, 
                           stats=event.get_stats(),
                           posts=posts.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/currencies/<guid>')
def currencies(guid):
    event = Event.get_by_guid_or_404(guid)
    log_page_access(request, current_user)
    page = request.args.get('page', 1, type=int)
    eventcurrencies = event.eventcurrencies.paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.currencies', page=eventcurrencies.next_num) if eventcurrencies.has_next else None
    prev_url = url_for('event.currencies', page=eventcurrencies.prev_num) if eventcurrencies.has_prev else None
    return render_template('event/eventcurrencies.html', 
                           title=_('Allowed currencies'), 
                           event=event, 
                           eventcurrencies=eventcurrencies.items, 
                           next_url=next_url, prev_url=prev_url)

@bp.route('/set_rate/<guid>/<currency_guid>', methods=['GET', 'POST'])
@login_required
def set_rate(guid, currency_guid):
    event = Event.get_by_guid_or_404(guid)
    currency = Currency.get_by_guid_or_404(currency_guid)
    eventcurrency = EventCurrency.query.filter_by(currency_id=currency.id, event_id=event.id).first_or_404()
    print(eventcurrency, eventcurrency.event_id, eventcurrency.currency_id, eventcurrency.inCHF)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.currencies', guid=event.guid))
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    
    form = SetRateForm()
    if form.validate_on_submit():
        eventcurrency.inCHF = form.inCHF.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.currencies', guid=event.guid))
    elif request.method == 'GET':
        form.inCHF.data = eventcurrency.inCHF
    return render_template('edit_form.html', 
                           title=_('Set rate'), 
                           form=form)
  
@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    log_page_access(request, current_user)
    form = EventForm()
    form.base_currency_id.choices = [(c.id, c.code) for c in Currency.query.order_by(Currency.code.asc())]
    form.currency_id.choices = form.base_currency_id.choices
    if form.validate_on_submit():
        base_currency = Currency.query.get(form.base_currency_id.data)
        currencies = [Currency.query.get(currency_id) for currency_id in form.currency_id.data]
        event = Event(name=form.name.data, 
                      date=form.date.data,
                      admin=current_user,
                      base_currency=base_currency,
                      currencies=currencies,
                      exchange_fee=form.exchange_fee.data,
                      closed=False,
                      fileshare_link=form.fileshare_link.data, 
                      description=form.description.data, 
                      db_created_by=current_user.username)
        user = EventUser(username=current_user.username,
                         email=current_user.email, 
                         locale=current_user.locale, 
                         about_me=current_user.about_me, 
                         db_created_by=current_user.username)
        
        event.add_user(user)
        event.add_currency(base_currency)
        db.session.add(event)
        db.session.commit()
        event.accountant = user
        db.session.commit()
        flash(_('Your new event has been added.'))
        return redirect(url_for('event.main', guid=event.guid))
    
    CHF = Currency.query.filter_by(code='CHF').first()
    form.base_currency_id.data = CHF.id
    form.currency_id.data = [CHF.id]
    return render_template('edit_form.html', 
                           title=_('New Event'), 
                           form=form)

@bp.route('/edit/<guid>', methods=['GET', 'POST'])
@login_required
def edit(guid):
    event = Event.get_by_guid_or_404(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=event.guid))
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    form = EventForm()
    form.base_currency_id.choices = [(c.id, c.code) for c in event.currencies]
    form.currency_id.choices = [(c.id, c.code) for c in Currency.query.order_by(Currency.code.asc())]
    if form.validate_on_submit():
        event.name = form.name.data
        event.date = form.date.data
        event.fileshare_link = form.fileshare_link.data
        event.description = form.description.data
        event.base_currency = Currency.query.get(form.base_currency_id.data)
        event.exchange_fee = form.exchange_fee.data
        
        # add new currencies
        for currency_id in form.currency_id.data:
            currency = Currency.query.get(currency_id)
            if currency not in event.currencies:
                event.currencies.append(currency)
        
        # remove currencies
        for currency in event.currencies:
            if currency.id not in form.currency_id.data:
                eventcurrency = event.eventcurrencies.filter(EventCurrency.currency_id==currency.id).first()
                event.eventcurrencies.remove(eventcurrency)
        
        event.add_currency(event.base_currency)
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.main', guid=guid))
    elif request.method == 'GET':
        form.name.data = event.name
        form.date.data = event.date
        form.fileshare_link.data = event.fileshare_link
        form.description.data = event.description
        form.base_currency_id.data = event.base_currency_id
        form.currency_id.data = [c.id for c in event.currencies]
        form.exchange_fee.data = event.exchange_fee
    return render_template('edit_form.html', 
                           title=_('Edit Event'), 
                           form=form)

@bp.route('/edit_picture/<guid>', methods=['GET', 'POST'])
@login_required
def edit_picture(guid):
    event = Event.get_by_guid_or_404(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=event.guid))
    log_page_access(request, current_user)
    form = ImageForm()
    if form.validate_on_submit():
        try:
            image_filename = images.save(request.files['image'])
            image_path = images.path(image_filename)
            event.admin.launch_task('import_image', _('Importing %(filename)s...', filename=image_filename), path=image_path, add_to_class='Event', add_to_id=event.id)
            db.session.commit()
            flash(_('Your changes have been saved.'))
        except UploadNotAllowed:
            flash(_('Invalid or empty image.'))
        return redirect(url_for('event.main', guid=guid))
    return render_template('edit_form.html', 
                           title=_('Event Picture'), 
                           form=form)
    
@bp.route('/users/<guid>', methods=['GET', 'POST'])
def users(guid):
    event = Event.get_by_guid_or_404(guid)
    log_page_access(request, current_user)
    form = EventUserForm()
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', guid=event.guid))
        user = EventUser(username=form.username.data, 
                         email=form.email.data,
                         locale=form.locale.data,
                         about_me=form.about_me.data)
        event.add_user(user)
        db.session.commit()
        flash(_('User %(username)s has been added to event %(event_name)s.', username=user.username, event_name=event.name))
        return redirect(url_for('event.users', guid=guid))
    
    page = request.args.get('page', 1, type=int)
    users = event.users.order_by(EventUser.username.asc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.users', guid=guid, page=users.next_num) if users.has_next else None
    prev_url = url_for('event.users', guid=guid, page=users.prev_num) if users.has_prev else None
    return render_template('event/users.html', 
                           form=form,
                           event=event,
                           can_edit=event.can_edit(current_user),
                           users=users.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/add_user/<guid>/<user_guid>')
@login_required
def add_user(guid, user_guid):
    event = Event.get_by_guid_or_404(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.users', guid=event.guid))
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('main.event', guid=event.guid))
    user = EventUser.get_by_guid_or_404(user_guid)
    event.add_user(user)
    db.session.commit()
    flash(_('User %(username)s has been added to event %(event_name)s.', username=user.username, event_name=event.name))
    return redirect(url_for('event.users', guid=guid))

@bp.route('/remove_user/<guid>/<user_guid>')
@login_required
def remove_user(guid, user_guid):
    event = Event.get_by_guid_or_404(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.users', guid=event.guid))
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    user = EventUser.get_by_guid_or_404(user_guid)
    if event.remove_user(user):
        flash(_('User %(username)s cannot be removed from event %(event_name)s.', username=user.username, event_name=event.name))
        return redirect(url_for('event.users', guid=guid))
    db.session.commit()
    flash(_('User %(username)s has been removed from event %(event_name)s.', username=user.username, event_name=event.name))
    return redirect(url_for('event.users', guid=guid))

@bp.route('/edit_profile/<guid>', methods=['GET', 'POST'])
def edit_profile(guid):
    eventuser = EventUser.get_by_guid_or_404(guid)
    log_page_access(request, current_user)
    form = EventUserForm()
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    if form.validate_on_submit():
        eventuser.username = form.username.data
        eventuser.email = form.email.data
        eventuser.about_me = form.about_me.data
        eventuser.locale = form.locale.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.user', guid=eventuser.guid))
    elif request.method == 'GET':
        form.username.data = eventuser.username
        form.email.data = eventuser.email
        form.about_me.data = eventuser.about_me
        form.locale.data = eventuser.locale
    return render_template('edit_form.html', 
                           title=_('Edit Profile'), 
                           form=form)

@bp.route('/edit_profile_picture/<guid>', methods=['GET', 'POST'])
def edit_profile_picture(guid):
    eventuser = EventUser.get_by_guid_or_404(guid)
    log_page_access(request, current_user)
    form = ImageForm()
    if form.validate_on_submit():
        try:
            image_filename = images.save(request.files['image'])
            image_path = images.path(image_filename)
            eventuser.event.admin.launch_task('import_image', _('Importing %(filename)s...', filename=image_filename), path=image_path, add_to_class='EventUser', add_to_id=eventuser.id)
            db.session.commit()
            flash(_('Your changes have been saved.'))
        except UploadNotAllowed:
            flash(_('Invalid or empty image.'))
        return redirect(url_for('event.user', guid=eventuser.guid))
    return render_template('edit_form.html', 
                           title=_('Profile Picture'), 
                           form=form)

@bp.route('/balance/<guid>', methods=['GET'])
def balance(guid):
    event = Event.get_by_guid_or_404(guid)
    log_page_access(request, current_user)
    
    draft_settlements = event.calculate_balance()
    balances_str, total_expenses_str = event.get_balance()
    return render_template('event/balance.html', 
                           event=event, 
                           draft_settlements=draft_settlements,
                           balances_str=balances_str, 
                           total_expenses_str=total_expenses_str)

@bp.route('/expenses/<guid>', methods=['GET', 'POST'])
def expenses(guid):
    event = Event.get_by_guid_or_404(guid)
    log_page_access(request, current_user)
    form = ExpenseForm()
    form.user_id.choices = [(u.id, u.username) for u in event.users]
    form.currency_id.choices = [(c.id, c.code) for c in event.currencies]
    form.affected_users_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', guid=event.guid))
        expense = Expense(user=EventUser.query.get(form.user_id.data), 
                          event=event, 
                          currency=Currency.query.get(form.currency_id.data), 
                          amount=form.amount.data, 
                          affected_users=[EventUser.query.get(user_id) for user_id in form.affected_users_id.data], 
                          date=form.date.data,
                          description=form.description.data, 
                          db_created_by=(current_user.username if current_user.is_anonymous else 'anonymous'))
        image = Image.query.filter_by(name='expense').first()
        if image:
            expense.image = image
        db.session.add(expense)
        db.session.commit()
        flash(_('Your new expense has been added to event %(event_name)s.', event_name=event.name))
        return redirect(url_for('event.expenses', guid=guid))
    
    form.currency_id.data = event.base_currency.id
    page = request.args.get('page', 1, type=int)
    expenses = event.expenses.order_by(Expense.date.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.expenses', guid=event.guid, page=expenses.next_num) if expenses.has_next else None
    prev_url = url_for('event.expenses', guid=event.guid, page=expenses.prev_num) if expenses.has_prev else None
    return render_template('event/expenses.html', 
                           form=form, 
                           event=event, 
                           expenses=expenses.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/add_receipt/<guid>', methods=['GET', 'POST'])
def add_receipt(guid):
    expense = Expense.get_by_guid_or_404(guid)
    event = expense.event
    log_page_access(request, current_user)
    if expense.event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=expense.event.guid))
    
    form = ImageForm()
    if form.validate_on_submit():
        try:
            image_filename = images.save(request.files['image'])
            image_path = images.path(image_filename)
            event.admin.launch_task('import_image', _('Importing %(filename)s...', filename=image_filename), path=image_path, add_to_class='Expense', add_to_id=expense.id)
            db.session.commit()
            flash(_('Your changes have been saved.'))
        except UploadNotAllowed:
            flash(_('Invalid or empty image.'))
        return redirect(url_for('event.expenses', guid=expense.event.guid))
    return render_template('edit_form.html', 
                           title=_('Add Receipt'), 
                           form=form)
    
@bp.route('/edit_expense/<guid>', methods=['GET', 'POST'])
def edit_expense(guid):
    expense = Expense.get_by_guid_or_404(guid)
    event = expense.event
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    
    form = ExpenseForm()
    form.user_id.choices = [(expense.user.id, expense.user.username)]
    form.currency_id.choices = [(c.id, c.code) for c in event.currencies]
    form.affected_users_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        expense.user=EventUser.query.get(form.user_id.data)
        expense.currency = Currency.query.get(form.currency_id.data)
        expense.amount = form.amount.data
        expense.affected_users = [EventUser.query.get(user_id) for user_id in form.affected_users_id.data]
        expense.date = form.date.data
        expense.description = form.description.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.expenses', guid=event.guid))
    elif request.method == 'GET':
        form.user_id.data = expense.user.id
        form.currency_id.data = expense.currency.id
        form.amount.data = expense.amount
        form.affected_users_id.data = [u.id for u in expense.affected_users]
        form.date.data = expense.date
        form.description.data = expense.description
    return render_template('edit_form.html', 
                           title=_('Edit Expense'), 
                           form=form)

@bp.route('/remove_expense/<guid>')
def remove_expense(guid):
    expense = Expense.get_by_guid_or_404(guid)
    event = expense.event
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    
    if expense in event.expenses:
        amount_str = expense.get_amount_str()
        event.expenses.remove(expense)
        db.session.commit()
        flash(_('Expense over %(amount_str)s has been removed from event %(event_name)s.', amount_str=amount_str, event_name=event.name))
    return redirect(url_for('event.expenses', guid=event.guid))

@bp.route('/expense_users/<guid>', methods=['GET', 'POST'])
def expense_users(guid):
    expense = Expense.get_by_guid_or_404(guid)
    event = expense.event
    log_page_access(request, current_user)
    form = ExpenseAddUserForm()
    form.user_id.choices = [(u.id, u.username) for u in event.users.order_by(EventUser.username.asc()) if u not in expense.affected_users]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', guid=event.guid))
        users = [EventUser.query.get(user_id) for user_id in form.user_id.data]
        expense.add_users(users)
        db.session.commit()
        flash(_('User %(username)s has been added to the expense.', username=' and '.join([u.username for u in users])))
        return redirect(url_for('event.expense_users', guid=guid))
    
    page = request.args.get('page', 1, type=int)
    users = expense.affected_users.order_by(EventUser.username.asc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.expense_users', guid=guid, page=users.next_num) if users.has_next else None
    prev_url = url_for('event.expense_users', guid=guid, page=users.prev_num) if users.has_prev else None
    return render_template('event/expense_users.html', 
                           form=form,
                           expense=expense,
                           can_edit=True,
                           users=users.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/expense_add_user/<guid>/<user_guid>')
def expense_add_user(guid, user_guid):
    expense = Expense.get_by_guid_or_404(guid)
    event = expense.event
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    
    user = EventUser.get_by_guid_or_404(user_guid)
    expense.add_user(user)
    db.session.commit()
    flash(_('User %(username)s has been added to the expense.', username=user.username))
    return redirect(url_for('event.expense_users', guid=guid))

@bp.route('/expense_remove_user/<guid>/<user_guid>')
def expense_remove_user(guid, user_guid):
    expense = Expense.get_by_guid_or_404(guid)
    event = expense.event
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    
    user = EventUser.get_by_guid_or_404(user_guid)
    if expense.remove_user(user):
        flash(_('User %(username)s cannot be removed from the expense.', username=user.username))
        return redirect(url_for('event.expense_users', guid=guid))
    db.session.commit()
    flash(_('User %(username)s has been removed from the expense.', username=user.username))
    return redirect(url_for('event.expense_users', guid=guid))

@bp.route('/settlements/<guid>', methods=['GET', 'POST'])
def settlements(guid):
    event = Event.get_by_guid_or_404(guid)
    log_page_access(request, current_user)
    form = SettlementForm()
    form.sender_id.choices = [(u.id, u.username) for u in event.users]
    form.currency_id.choices = [(c.id, c.code) for c in event.currencies]
    form.recipient_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', guid=event.guid))
        settlement = Settlement(sender=EventUser.query.get(form.sender_id.data), 
                                recipient=EventUser.query.get(form.recipient_id.data), 
                                event=event, 
                                currency=Currency.query.get(form.currency_id.data), 
                                amount=form.amount.data, 
                                draft=False,
                                date=datetime.utcnow(),
                                description=form.description.data, 
                                db_created_by=(current_user.username if current_user.is_anonymous else 'anonymous'))
        image = Image.query.filter_by(name='settlement').first()
        if image:
            settlement.image = image
        db.session.add(settlement)
        db.session.commit()
        flash(_('Your new settlement has been added to event %(event_name)s.', event_name=event.name))
        return redirect(url_for('event.settlements', guid=guid))
    
    form.currency_id.data = event.base_currency.id
    page = request.args.get('page', 1, type=int)
    settlements = event.settlements.filter_by(draft=False).order_by(Settlement.date.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.settlements', guid=event.guid, page=settlements.next_num) if settlements.has_next else None
    prev_url = url_for('event.settlements', guid=event.guid, page=settlements.prev_num) if settlements.has_prev else None
    return render_template('event/settlements.html', 
                           form=form, 
                           event=event, 
                           settlements=settlements.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/edit_settlement/<guid>', methods=['GET', 'POST'])
def edit_settlement(guid):
    settlement = Settlement.get_by_guid_or_404(guid)
    event = settlement.event
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    
    form = SettlementForm()
    form.sender_id.choices = [(u.id, u.username) for u in event.users]
    form.currency_id.choices = [(c.id, c.code) for c in event.currencies]
    form.recipient_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        settlement.sender=EventUser.query.get(form.sender_id.data)
        settlement.currency = Currency.query.get(form.currency_id.data)
        settlement.amount = form.amount.data
        settlement.recipient = EventUser.query.get(form.recipient_id.data)
        settlement.description = form.description.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.settlements', guid=event.guid))
    elif request.method == 'GET':
        form.sender_id.data = settlement.sender.id
        form.currency_id.data = settlement.currency.id
        form.amount.data = settlement.amount
        form.recipient_id.data = settlement.recipient.id
        form.description.data = settlement.description
    return render_template('edit_form.html', 
                           title=_('Edit Settlement'), 
                           form=form)

@bp.route('/balance/pay/<guid>', methods=['GET'])
def settlement_execute(guid):
    settlement = Settlement.get_by_guid_or_404(guid)
    event = settlement.event
    log_page_access(request, current_user)
    settlement.draft = False
    settlement.description = _('Confirmed by user %(username)s', username = current_user.username)
    db.session.commit()
    return redirect(url_for('event.balance', guid=event.guid))
    
@bp.route('/remove_settlement/<guid>')
def remove_settlement(guid):
    settlement = Settlement.get_by_guid_or_404(guid)
    event = settlement.event
    log_page_access(request, current_user)
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', guid=event.guid))
    
    if settlement in event.settlements:
        amount_str = settlement.get_amount_str()
        event.settlements.remove(settlement)
        db.session.commit()
        flash(_('Settlement over %(amount_str)s has been removed from event %(event_name)s.', amount_str=amount_str, event_name=event.name))
    return redirect(url_for('event.settlements', guid=event.guid))

@bp.route('/send_payment_reminders/<guid>')
@login_required
def send_payment_reminders(guid):
    event = Event.get_by_guid_or_404(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to send payment reminders of your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=event.guid))
    log_page_access(request, current_user)
    event.admin.launch_task('send_reminders', _('Sending balance reports...'), event_guid=guid)
    db.session.commit()
    flash(_('All users have been reminded of their duties!'))
    return redirect(url_for('event.main', guid=event.guid))

@bp.route('/request_balance/<guid>')
def request_balance(guid):
    event = Event.get_by_guid_or_404(guid)
    log_page_access(request, current_user)
    event.admin.launch_task('request_balance', _('Sending balance reports...'), event_guid=guid)
    db.session.commit()
    flash(_('The balance has been sent to your email'))
    return redirect(url_for('event.main', guid=event.guid))

@bp.route('/convert_currencies/<guid>')
@login_required
def convert_currencies(guid):
    event = Event.get_by_guid_or_404(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to convert currencies of your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=event.guid))
    log_page_access(request, current_user)
    event.convert_currencies()
    db.session.commit()
    flash(_('All transaction of this event have been converted to %(code)s.', code=event.base_currency.code))
    return redirect(url_for('event.main', guid=event.guid))

@bp.route('/reopen/<guid>')
@login_required
def reopen(guid):
    event = Event.get_by_guid_or_404(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to reopen your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=event.guid))
    log_page_access(request, current_user)
    event.closed = False
    db.session.commit()
    flash(_('Event has been reopened.'))
    return redirect(url_for('event.main', guid=event.guid))

@bp.route('/close/<guid>')
@login_required
def close(guid):
    event = Event.get_by_guid_or_404(guid)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to close your own event!'))
        log_page_access_denied(request, current_user)
        return redirect(url_for('event.main', guid=event.guid))
    log_page_access(request, current_user)
    if event.settlements.filter_by(draft=True).all():
        flash(_('Your are only allowed to close an event with no open liabilities!'))
        return redirect(url_for('event.main', guid=event.guid))
    event.closed = True
    db.session.commit()
    flash(_('Event has been closed.'))
    return redirect(url_for('event.main', guid=event.guid))
