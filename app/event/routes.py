# coding=utf-8

from datetime import datetime
from flask import request, render_template, flash, redirect, url_for, current_app
from flask_login import current_user, login_required
from flask_uploads import UploadNotAllowed
from flask_babel import _

from app import db, images
from app.event import bp
from app.main.forms import ImageForm
from app.event.forms import PostForm, EventForm, EventAddUserForm, ExpenseForm, SettlementForm
from app.event.email import send_reminder_email
from app.models import Currency, Event, Expense, Settlement, Post, User, Image
      
# routes for rendered pages
@bp.route('/index')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    events = current_user.events.order_by(Event.date.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.index', page=events.next_num) if events.has_next else None
    prev_url = url_for('event.index', page=events.prev_num) if events.has_prev else None
    return render_template('event/index.html', 
                           title=_('Hi %(username)s, your events:', username=current_user.username), 
                           events=events.items, 
                           next_url=next_url, prev_url=prev_url)

@bp.route('/main/<event_id>', methods=['GET', 'POST'])
@login_required
def main(event_id):
    event = Event.query.get_or_404(event_id)
    if not event.can_view(current_user):
        flash(_('Your are only allowed to view your events!'))
        return redirect(url_for('event.index'))
    
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body=form.post.data, author=current_user, timestamp=datetime.utcnow(), event=event)
        db.session.add(post)
        db.session.commit()
        flash(_('Your post is now live!'))
        return redirect(url_for('event.main', event_id=event_id))
    
    page = request.args.get('page', 1, type=int)
    posts = event.posts.order_by(Post.timestamp.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.main', event_id=event.id, page=posts.next_num) if posts.has_next else None
    prev_url = url_for('event.main', event_id=event.id, page=posts.prev_num) if posts.has_prev else None
    return render_template('event/main.html', 
                           form=form, 
                           event=event, 
                           stats=event.get_stats(),
                           posts=posts.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/currencies/<event_id>')
@login_required
def currencies(event_id):
    event = Event.query.get_or_404(event_id)
    page = request.args.get('page', 1, type=int)
    currencies = event.allowed_currencies.order_by(Currency.code.asc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.currencies', page=currencies.next_num) if currencies.has_next else None
    prev_url = url_for('event.currencies', page=currencies.prev_num) if currencies.has_prev else None
    return render_template('currencies.html', 
                           title=_('Allowed currencies'), 
                           currencies=currencies.items, 
                           allow_new=False,
                           next_url=next_url, prev_url=prev_url)
    
@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    admins = User.query.filter_by(username='admin').all()
    users = [(u.id, u.username) for u in User.query.order_by('username') if u not in admins]
    form = EventForm()
    form.admin_id.choices = users
    if current_user.username != 'admin':
        form.admin_id.data = current_user.id
    form.accountant_id.choices = users
    if current_user.username != 'admin':
        form.accountant_id.data = current_user.id
    form.base_currency_id.choices = [(c.id, c.code) for c in Currency.query.order_by('code')]
    CHF = Currency.query.filter_by(code='CHF').first()
    form.base_currency_id.data = CHF.id
    form.allowed_currency_id.choices = form.base_currency_id.choices
    form.allowed_currency_id.data = [CHF.id]
    if form.validate_on_submit():
        admin = User.query.get(form.admin_id.data)
        accountant = User.query.get(form.accountant_id.data)
        base_currency = Currency.query.get(form.base_currency_id.data)
        event = Event(name=form.name.data, 
                      date=form.date.data,
                      admin=admin,
                      accountant=accountant,
                      base_currency=base_currency,
                      allowed_currencies=[Currency.query.get(currency_id) for currency_id in form.allowed_currency_id.data],
                      exchange_fee=form.exchange_fee.data,
                      closed=False,
                      fileshare_link=form.fileshare_link.data, 
                      description=form.description.data, 
                      db_created_by=current_user.username)
        event.add_user(admin)
        event.add_user(accountant)
        event.add_currency(base_currency)
        db.session.add(event)
        db.session.commit()
        flash(_('Your new event has been added.'))
        return redirect(url_for('event.main', event_id=event.id))
    return render_template('edit_form.html', 
                           title=_('New Event'), 
                           form=form)

@bp.route('/edit/<event_id>', methods=['GET', 'POST'])
@login_required
def edit(event_id):
    event = Event.query.get_or_404(event_id)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        return redirect(url_for('event.main', event_id=event.id))
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', event_id=event.id))
    form = EventForm()
    form.admin_id.choices = [(u.id, u.username) for u in event.users.order_by('username')]
    form.accountant_id.choices = [(u.id, u.username) for u in event.users.order_by('username')]
    form.base_currency_id.choices = [(c.id, c.code) for c in event.allowed_currencies.order_by('code')]
    form.allowed_currency_id.choices = [(c.id, c.code) for c in Currency.query.order_by('code')]
    if form.validate_on_submit():
        event.name = form.name.data
        event.date = form.date.data
        event.fileshare_link = form.fileshare_link.data
        event.description = form.description.data
        event.admin = User.query.get(form.admin_id.data)
        event.accountant = User.query.get(form.accountant_id.data)
        event.base_currency = Currency.query.get(form.base_currency_id.data)
        event.allowed_currencies = [Currency.query.get(currency_id) for currency_id in form.allowed_currency_id.data]
        event.exchange_fee = form.exchange_fee.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.main', event_id=event_id))
    elif request.method == 'GET':
        form.name.data = event.name
        form.date.data = event.date
        form.fileshare_link.data = event.fileshare_link
        form.description.data = event.description
        form.admin_id.data = event.admin_id
        form.accountant_id.data = event.accountant_id
        form.base_currency_id.data = event.base_currency_id
        form.allowed_currency_id.data = [c.id for c in event.allowed_currencies]
        form.exchange_fee.data = event.exchange_fee
    return render_template('edit_form.html', 
                           title=_('Edit Event'), 
                           form=form)

@bp.route('/edit_picture/<event_id>', methods=['GET', 'POST'])
@login_required
def edit_picture(event_id):
    event = Event.query.get_or_404(event_id)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        return redirect(url_for('event.main', event_id=event.id))
    form = ImageForm()
    if form.validate_on_submit():
        try:
            image_filename = images.save(request.files['image'])
            image_path = images.path(image_filename)
            current_user.launch_task('import_image', _('Importing %(filename)s...', filename=image_filename), path=image_path, add_to_class='Event', add_to_id=event.id)
            db.session.commit()
            flash(_('Your changes have been saved.'))
        except UploadNotAllowed:
            flash(_('Invalid or empty image.'))
        return redirect(url_for('event.main', event_id=event_id))
    return render_template('edit_form.html', 
                           title=_('Event Picture'), 
                           form=form)
    
@bp.route('/users/<event_id>', methods=['GET', 'POST'])
@login_required
def users(event_id):
    event = Event.query.get_or_404(event_id)
    admins = User.query.filter_by(username='admin').all()
    admins.append(event.admin)
    if not event.can_view(current_user):
        flash(_('Your are only allowed to view your own event!'))
        return redirect(url_for('event.users', event_id=event.id))
    form = EventAddUserForm()
    form.user_id.choices = [(u.id, u.username) for u in User.query.order_by('username') if u not in admins and u not in event.users]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', event_id=event.id))
        user = User.query.get(form.user_id.data)
        event.add_user(user)
        db.session.commit()
        flash(_('User %(username)s has been added to event %(event_name)s.', username=user.username, event_name=event.name))
        return redirect(url_for('event.users', event_id=event_id))
    
    page = request.args.get('page', 1, type=int)
    users = event.users.order_by(User.username.asc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.users', event_id=event_id, page=users.next_num) if users.has_next else None
    prev_url = url_for('event.users', event_id=event_id, page=users.prev_num) if users.has_prev else None
    return render_template('event/users.html', 
                           form=form,
                           event=event,
                           can_edit=event.can_edit(current_user),
                           users=users.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/add_user/<event_id>/<username>')
@login_required
def add_user(event_id, username):
    event = Event.query.get_or_404(event_id)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        return redirect(url_for('event.users', event_id=event.id))
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('main.event', event_id=event.id))
    user = User.query.filter_by(username=username).first_or_404()
    event.add_user(user)
    db.session.commit()
    flash(_('User %(username)s has been added to event %(event_name)s.', username=user.username, event_name=event.name))
    return redirect(url_for('event.users', event_id=event_id))

@bp.route('/remove_user/<event_id>/<username>')
@login_required
def remove_user(event_id, username):
    event = Event.query.get_or_404(event_id)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to edit your own event!'))
        return redirect(url_for('event.users', event_id=event.id))
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', event_id=event.id))
    user = User.query.filter_by(username=username).first_or_404()
    if user == event.admin:
        flash(_('You cannot remove the event admin!'))
        return redirect(url_for('event.users', event_id=event.id))
    if event.remove_user(user):
        flash(_('User %(username)s cannot be removed from event %(event_name)s.', username=user.username, event_name=event.name))
        return redirect(url_for('event.users', event_id=event_id))
    db.session.commit()
    flash(_('User %(username)s has been removed from event %(event_name)s.', username=user.username, event_name=event.name))
    return redirect(url_for('event.users', event_id=event_id))

@bp.route('/balance/<event_id>', methods=['GET'])
@login_required
def balance(event_id):
    event = Event.query.get_or_404(event_id)
    if not event.can_view(current_user):
        flash(_('Your are only allowed to view your events!'))
        return redirect(url_for('event.index'))
    
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
    return render_template('event/balance.html', 
                           event=event, 
                           draft_settlements=draft_settlements,
                           balances_str=balances_str, 
                           total_expenses_str=total_expenses_str)

@bp.route('/expenses/<event_id>', methods=['GET', 'POST'])
@login_required
def expenses(event_id):
    event = Event.query.get_or_404(event_id)
    if not event.can_view(current_user):
        flash(_('Your are only allowed to view your events!'))
        return redirect(url_for('event.index'))
    
    form = ExpenseForm()
    if event.can_edit(current_user):
        form.user_id.choices = [(u.id, u.username) for u in event.users]
    else:
        form.user_id.choices = [(current_user.id, current_user.username)]
    form.currency_id.choices = [(c.id, c.code) for c in event.allowed_currencies.order_by('code')]
    form.affected_users_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', event_id=event.id))
        expense = Expense(user=User.query.get(form.user_id.data), 
                          event=event, 
                          currency=Currency.query.get(form.currency_id.data), 
                          amount=form.amount.data, 
                          affected_users=[User.query.get(user_id) for user_id in form.affected_users_id.data], 
                          date=form.date.data,
                          description=form.description.data, 
                          db_created_by=current_user.username)
        image = Image.query.filter_by(name='expense').first()
        if image:
            expense.image = image
        db.session.add(expense)
        db.session.commit()
        flash(_('Your new expense has been added to event %(event_name)s.', event_name=event.name))
        return redirect(url_for('event.expenses', event_id=event_id))
    
    form.user_id.data = current_user.id
    form.currency_id.data = event.base_currency.id
    page = request.args.get('page', 1, type=int)
    expenses = event.expenses.order_by(Expense.date.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.expenses', event_id=event.id, page=expenses.next_num) if expenses.has_next else None
    prev_url = url_for('event.expenses', event_id=event.id, page=expenses.prev_num) if expenses.has_prev else None
    return render_template('event/expenses.html', 
                           form=form, 
                           event=event, 
                           expenses=expenses.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/add_receipt/<expense_id>', methods=['GET', 'POST'])
@login_required
def add_receipt(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if not expense.can_edit(current_user):
        flash(_('Your are only allowed to edit your own expenses!'))
        return redirect(url_for('event.expenses', event_id=expense.event.id))
    if expense.event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', event_id=expense.event.id))
    
    form = ImageForm()
    if form.validate_on_submit():
        try:
            image_filename = images.save(request.files['image'])
            image_path = images.path(image_filename)
            current_user.launch_task('import_image', _('Importing %(filename)s...', filename=image_filename), path=image_path, add_to_class='Expense', add_to_id=expense.id)
            db.session.commit()
            flash(_('Your changes have been saved.'))
        except UploadNotAllowed:
            flash(_('Invalid or empty image.'))
        return redirect(url_for('event.expenses', event_id=expense.event.id))
    return render_template('edit_form.html', 
                           title=_('Add Receipt'), 
                           form=form)
    
@bp.route('/edit_expense/<expense_id>', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    event = expense.event
    if not expense.can_edit(current_user):
        flash(_('Your are only allowed to edit your own expenses!'))
        return redirect(url_for('event.expenses', event_id=event.id))
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', event_id=event.id))
    
    form = ExpenseForm()
    if event.can_edit(current_user):
        form.user_id.choices = [(u.id, u.username) for u in event.users]
    else:
        form.user_id.choices = [(expense.user.id, expense.user.username)]
    
    form.currency_id.choices = [(c.id, c.code) for c in event.allowed_currencies.order_by('code')]
    form.affected_users_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        expense.user=User.query.get(form.user_id.data)
        expense.currency = Currency.query.get(form.currency_id.data)
        expense.amount = form.amount.data
        expense.affected_users = [User.query.get(user_id) for user_id in form.affected_users_id.data]
        expense.date = form.date.data
        expense.description = form.description.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.expenses', event_id=event.id))
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

@bp.route('/remove_expense/<expense_id>')
@login_required
def remove_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    event = expense.event
    if not expense.can_edit(current_user):
        flash(_('Your are only allowed to remove your own expenses!'))
        return redirect(url_for('event.expenses', event_id=event.id))
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', event_id=event.id))
    
    if expense in event.expenses:
        amount_str = expense.get_amount_str()
        event.expenses.remove(expense)
        db.session.commit()
        flash(_('Expense over %(amount_str)s has been removed from event %(event_name)s.', amount_str=amount_str, event_name=event.name))
    return redirect(url_for('event.expenses', event_id=event.id))

@bp.route('/expense_users/<expense_id>', methods=['GET', 'POST'])
@login_required
def expense_users(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    event = expense.event
    if not expense.can_view(current_user):
        flash(_('Your are only allowed to view your own expense!'))
        return redirect(url_for('event.users', event_id=event.id))
    form = EventAddUserForm()
    admins = User.query.filter_by(username='admin').all()
    form.user_id.choices = [(u.id, u.username) for u in User.query.order_by('username') if u not in admins and u not in expense.affected_users]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', event_id=event.id))
        user = User.query.get(form.user_id.data)
        expense.add_user(user)
        db.session.commit()
        flash(_('User %(username)s has been added to expense over %(expense_str)s.', username=user.username, expense_str=expense.get_amount_str()))
        return redirect(url_for('event.expense_users', expense_id=expense_id))
    
    page = request.args.get('page', 1, type=int)
    users = expense.affected_users.order_by(User.username.asc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.expense_users', expense_id=expense_id, page=users.next_num) if users.has_next else None
    prev_url = url_for('event.expense_users', expense_id=expense_id, page=users.prev_num) if users.has_prev else None
    return render_template('event/expense_users.html', 
                           form=form,
                           expense=expense,
                           can_edit=expense.can_edit(current_user),
                           users=users.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/expense_add_user/<expense_id>/<username>')
@login_required
def expense_add_user(expense_id, username):
    expense = Expense.query.get_or_404(expense_id)
    event = expense.event
    if not expense.can_edit(current_user):
        flash(_('Your are only allowed to edit your own expenses!'))
        return redirect(url_for('event.expenses', event_id=event.id))
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', event_id=event.id))
    
    user = User.query.filter_by(username=username).first_or_404()
    expense.add_user(user)
    db.session.commit()
    flash(_('User %(username)s has been added to expense over %(expense_str)s.', username=user.username, expense_str=expense.get_amount_str()))
    return redirect(url_for('event.expense_users', expense_id=expense_id))

@bp.route('/expense_remove_user/<expense_id>/<username>')
@login_required
def expense_remove_user(expense_id, username):
    expense = Expense.query.get_or_404(expense_id)
    event = expense.event
    if not expense.can_edit(current_user):
        flash(_('Your are only allowed to edit your own expenses!'))
        return redirect(url_for('event.expenses', event_id=event.id))
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', event_id=event.id))
    
    user = User.query.filter_by(username=username).first_or_404()
    if expense.remove_user(user):
        flash(_('User %(username)s cannot be removed from expense over %(expense_str)s.', username=user.username, expense_str=expense.get_amount_str()))
        return redirect(url_for('event.expense_users', expense_id=expense_id))
    db.session.commit()
    flash(_('User %(username)s has been removed from expense over %(expense_str)s.', username=user.username, expense_str=expense.get_amount_str()))
    return redirect(url_for('event.expense_users', expense_id=expense_id))

@bp.route('/settlements/<event_id>', methods=['GET', 'POST'])
@login_required
def settlements(event_id):
    event = Event.query.get_or_404(event_id)
    if not event.can_view(current_user):
        flash(_('Your are only allowed to view your events!'))
        return redirect(url_for('event.index'))
    form = SettlementForm()
    if event.can_edit(current_user):
        form.sender_id.choices = [(u.id, u.username) for u in event.users]
    else:
        form.sender_id.choices = [(current_user.id, current_user.username)]
    form.currency_id.choices = [(c.id, c.code) for c in event.allowed_currencies.order_by('code')]
    form.recipient_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        if event.closed:
            flash(_('Your are only allowed to edit an open event!'))
            return redirect(url_for('main.event', event_id=event.id))
        settlement = Settlement(sender=User.query.get(form.sender_id.data), 
                                recipient=User.query.get(form.recipient_id.data), 
                                event=event, 
                                currency=Currency.query.get(form.currency_id.data), 
                                amount=form.amount.data, 
                                draft=False,
                                date=datetime.utcnow(),
                                description=form.description.data, 
                                db_created_by=current_user.username)
        image = Image.query.filter_by(name='settlement').first()
        if image:
            settlement.image = image
        db.session.add(settlement)
        db.session.commit()
        flash(_('Your new settlement has been added to event %(event_name)s.', event_name=event.name))
        return redirect(url_for('event.settlements', event_id=event_id))
    
    form.sender_id.data = current_user.id
    form.currency_id.data = event.base_currency.id
    page = request.args.get('page', 1, type=int)
    settlements = event.settlements.filter_by(draft=False).order_by(Settlement.date.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('event.settlements', event_id=event.id, page=settlements.next_num) if settlements.has_next else None
    prev_url = url_for('event.settlements', event_id=event.id, page=settlements.prev_num) if settlements.has_prev else None
    return render_template('event/settlements.html', 
                           form=form, 
                           event=event, 
                           settlements=settlements.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/edit_settlement/<settlement_id>', methods=['GET', 'POST'])
@login_required
def edit_settlement(settlement_id):
    settlement = Settlement.query.get_or_404(settlement_id)
    event = settlement.event
    if not settlement.can_edit(current_user):
        flash(_('Your are only allowed to edit your own settlements!'))
        return redirect(url_for('event.settlements', event_id=event.id))
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', event_id=event.id))
    
    form = SettlementForm()
    if event.can_edit(current_user):
        form.sender_id.choices = [(u.id, u.username) for u in event.users]
    else:
        form.sender_id.choices = [(settlement.sender.id, settlement.sender.username)]
    form.currency_id.choices = [(c.id, c.code) for c in event.allowed_currencies.order_by('code')]
    form.recipient_id.choices = [(u.id, u.username) for u in event.users]
    if form.validate_on_submit():
        settlement.sender=User.query.get(form.sender_id.data)
        settlement.currency = Currency.query.get(form.currency_id.data)
        settlement.amount = form.amount.data
        settlement.recipient = User.query.get(form.recipient_id.data)
        settlement.description = form.description.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('event.settlements', event_id=event.id))
    elif request.method == 'GET':
        form.sender_id.data = settlement.sender.id
        form.currency_id.data = settlement.currency.id
        form.amount.data = settlement.amount
        form.recipient_id.data = settlement.recipient.id
        form.description.data = settlement.description
    return render_template('edit_form.html', 
                           title=_('Edit Settlement'), 
                           form=form)

@bp.route('/balance/pay/<settlement_id>', methods=['GET'])
@login_required
def settlement_execute(settlement_id):
    settlement = Settlement.query.get_or_404(settlement_id)
    event = settlement.event
    if not settlement.can_confirm(current_user):
        flash(_('Your are only allowed to add settlements directed to you!'))
        return redirect(url_for('event.settlements', settlement_id=settlement.id))
    settlement.draft = False
    settlement.description = _('Confirmed by user %(username)s', username = current_user.username)
    db.session.commit()
    return redirect(url_for('event.balance', event_id=event.id))
    
@bp.route('/remove_settlement/<settlement_id>')
@login_required
def remove_settlement(settlement_id):
    settlement = Settlement.query.get_or_404(settlement_id)
    event = settlement.event
    if not settlement.can_edit(current_user):
        flash(_('Your are only allowed to remove your own settlements!'))
        return redirect(url_for('event.settlements', settlement_id=settlement.id))
    if event.closed:
        flash(_('Your are only allowed to edit an open event!'))
        return redirect(url_for('event.main', event_id=event.id))
    
    if settlement in event.settlements:
        amount_str = settlement.get_amount_str()
        event.settlements.remove(settlement)
        db.session.commit()
        flash(_('Settlement over %(amount_str)s has been removed from event %(event_name)s.', amount_str=amount_str, event_name=event.name))
    return redirect(url_for('event.settlements', event_id=event.id))

@bp.route('/send_payment_reminders/<event_id>')
@login_required
def send_payment_reminders(event_id):
    event = Event.query.get_or_404(event_id)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to send payment reminders of your own event!'))
        return redirect(url_for('event.main', event_id=event.id))
    event.settlements.filter_by(draft=True).delete()
    draft_settlements = event.get_compensation_settlements_accountant()
    db.session.add_all(draft_settlements)
    db.session.commit()
    send_reminder_email(draft_settlements)
    flash(_('All users have been reminded of their duties!'))
    return redirect(url_for('event.main', event_id=event.id))

@bp.route('/convert_currencies/<event_id>')
@login_required
def convert_currencies(event_id):
    event = Event.query.get_or_404(event_id)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to convert currencies of your own event!'))
        return redirect(url_for('event.main', event_id=event.id))
    event.convert_currencies()
    db.session.commit()
    flash(_('All transaction of this event have been converted to %(code)s.', code=event.base_currency.code))
    return redirect(url_for('event.main', event_id=event.id))

@bp.route('/reopen/<event_id>')
@login_required
def reopen(event_id):
    event = Event.query.get_or_404(event_id)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to reopen your own event!'))
        return redirect(url_for('event.main', event_id=event.id))
    event.closed = False
    db.session.commit()
    flash(_('Event has been reopened.'))
    return redirect(url_for('event.main', event_id=event.id))

@bp.route('/close/<event_id>')
@login_required
def close(event_id):
    event = Event.query.get_or_404(event_id)
    if not event.can_edit(current_user):
        flash(_('Your are only allowed to close your own event!'))
        return redirect(url_for('event.main', event_id=event.id))
    if event.settlements.filter_by(draft=True).all():
        flash(_('Your are only allowed to close an event with no open liabilities!'))
        return redirect(url_for('event.main', event_id=event.id))
    event.closed = True
    db.session.commit()
    flash(_('Event has been closed.'))
    return redirect(url_for('event.main', event_id=event.id))
