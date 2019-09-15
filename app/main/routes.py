# coding=utf-8

from datetime import datetime
from flask import request, render_template, flash, redirect, url_for, jsonify, g, current_app
from flask_login import current_user, login_required
from flask_uploads import UploadNotAllowed
from flask_babel import get_locale, _

from app import db, images
from app.main import bp
from app.main.forms import ImageForm, EditProfileForm, MessageForm, CurrencyForm, NewUserForm, EditUserForm, BankAccountForm
from app.models import Currency, User, Message, Notification, Event, Image, BankAccount

@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
    g.locale = str(get_locale())

# routes for rendered pages
@bp.route('/')
def root():
    return redirect(url_for('event.index'))

@bp.route('/index')
def index():
    return redirect(url_for('event.index'))

@bp.route('/image/<image_id>')
@login_required
def image(image_id):
    image = Image.query.get_or_404(image_id)
    return render_template('image.html', 
                           title=_('Image'), 
                           image=image,
                           allow_turning=(not image.vector))

@bp.route('/rotate_image/<image_id>')
@login_required
def rotate_image(image_id):
    degree = request.args.get('degree', 0, type=int)
    image = Image.query.get_or_404(image_id)
    image.rotate_image(degree)
    db.session.commit()
    return redirect(url_for('main.image', image_id=image.id))

@bp.route('/currencies')
@login_required
def currencies():
    page = request.args.get('page', 1, type=int)
    currencies = Currency.query.order_by(Currency.code.asc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.currencies', page=currencies.next_num) if currencies.has_next else None
    prev_url = url_for('main.currencies', page=currencies.prev_num) if currencies.has_prev else None
    return render_template('currencies.html', 
                           title=_('Current currencies'), 
                           currencies=currencies.items, 
                           allow_new=True,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/new_currency', methods=['GET', 'POST'])
@login_required
def new_currency():
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

@bp.route('/new_bank_account', methods=['GET', 'POST'])
@login_required
def new_bank_account():
    form = BankAccountForm()
    if form.validate_on_submit():
        bank_account = BankAccount(user=current_user, 
                                   iban=form.iban.data, 
                                   bank=form.bank.data, 
                                   name=form.name.data, 
                                   address=form.address.data, 
                                   address_suffix=form.address_suffix.data, 
                                   zip_code=form.zip_code.data, 
                                   city=form.city.data, 
                                   country=form.country.data, 
                                   description=form.description.data, 
                                   db_created_by=current_user.username)
        
        db.session.add(bank_account)
        db.session.commit()
        flash(_('Your new bank account has been added.'))
        return redirect(url_for('main.user', username=current_user.username))
    return render_template('edit_form.html', 
                           title=_('New Bank Account'), 
                           form=form)

@bp.route('/bank_accounts/<username>', methods=['GET', 'POST'])
@login_required
def bank_accounts(username):
    user = User.query.filter_by(username=username).first_or_404()
    if current_user != user and not current_user.is_admin:
        flash(_('Your are only allowed to edit your own bank accounts!'))
        return redirect(url_for('main.user', username=current_user.username))
    form = BankAccountForm()
    if form.validate_on_submit():
        bank_account = BankAccount(user=current_user, 
                                   iban=form.iban.data, 
                                   bank=form.bank.data, 
                                   name=form.name.data, 
                                   address=form.address.data, 
                                   address_suffix=form.address_suffix.data, 
                                   zip_code=form.zip_code.data, 
                                   city=form.city.data, 
                                   country=form.country.data, 
                                   description=form.description.data, 
                                   db_created_by=current_user.username)
        
        db.session.add(bank_account)
        db.session.commit()
        flash(_('Your new bank account has been added.'))
        return redirect(url_for('main.bank_accounts', username=user.username))
    
    page = request.args.get('page', 1, type=int)
    bank_accounts = current_user.bank_accounts.order_by(BankAccount.iban.asc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.bank_accounts', username=current_user.username, page=users.next_num) if bank_accounts.has_next else None
    prev_url = url_for('main.bank_accounts', username=current_user.username, page=users.prev_num) if bank_accounts.has_prev else None
    return render_template('bank_accounts.html', 
                           form=form, 
                           bank_accounts=bank_accounts.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/edit_bank_account/<bank_account_id>', methods=['GET', 'POST'])
@login_required
def edit_bank_account(bank_account_id):
    bank_account = BankAccount.query.get_or_404(bank_account_id)
    if current_user not in [bank_account.user] and not current_user.is_admin:
        flash(_('Your are only allowed to edit your own bank accounts!'))
        return redirect(url_for('main.user', username=current_user.username))
    
    form = BankAccountForm()
    if form.validate_on_submit():
        bank_account.iban = form.iban.data, 
        bank_account.bank = form.bank.data, 
        bank_account.name = form.name.data, 
        bank_account.address = form.address.data, 
        bank_account.address_suffix = form.address_suffix.data, 
        bank_account.zip_code = form.zip_code.data, 
        bank_account.city = form.city.data, 
        bank_account.country = form.country.data, 
        bank_account.description = form.description.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.bank_accounts', username=current_user.username))
    elif request.method == 'GET':
        form.iban.data = bank_account.iban
        form.bank.data = bank_account.bank
        form.name.data = bank_account.name
        form.address.data = bank_account.address
        form.address_suffix.data = bank_account.address_suffix
        form.zip_code.data = bank_account.zip_code
        form.city.data = bank_account.city
        form.country.data = bank_account.country
        form.description.data = bank_account.description
    return render_template('edit_form.html', 
                           title=_('Edit Bank Account'), 
                           form=form)

@bp.route('/remove_bank_account/<bank_account_id>')
@login_required
def remove_bank_account(bank_account_id):
    bank_account = BankAccount.query.get_or_404(bank_account_id)
    user = bank_account.user
    if current_user not in [user] and not current_user.is_admin:
        flash(_('Your are only allowed to remove your own bank accounts!'))
        return redirect(url_for('main.user', username=current_user.username))
    
    if bank_account in user.bank_accounts:
        user.bank_accounts.remove(bank_account)
        db.session.commit()
        flash(_('Bank account %(iban_str)s has been removed from user %(username)s.', iban_str=bank_account.iban, username=user.username))
    return redirect(url_for('main.bank_accounts', username=user.username))

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

@bp.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    events = user.events_admin.order_by(Event.date.desc()).paginate(
        page, current_app.config['ITEMS_PER_PAGE'], False)
    next_url = url_for('main.user', username=user.username, page=events.next_num) if events.has_next else None
    prev_url = url_for('main.user', username=user.username, page=events.prev_num) if events.has_prev else None
    return render_template('user.html', 
                           title= _('User %(username)s', username = user.username), 
                           user=user, 
                           events=events.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/new_user', methods=['GET', 'POST'])
def new_user():
    if not current_user.is_admin:
        flash(_('Only an admin can create new users!'))
        return redirect(url_for('main.users'))
    form = NewUserForm()
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    form.timezone.choices = [(x, x) for x in current_app.config['TIMEZONES']]
    if form.validate_on_submit():
        user = User(username=form.username.data, 
                    email=form.email.data,
                    locale=form.locale.data,
                    timezone=form.timezone.data,
                    about_me=form.about_me.data)
        user.is_admin = form.is_admin.data
        user.set_password(form.password.data)
        user.get_token()
        db.session.add(user)
        db.session.commit()
        flash(_('New user %(username)s created', username = user.username))
        return redirect(url_for('main.users'))
    return render_template('edit_form.html', title=_('New User'), form=form)

@bp.route('/edit_user/<username>', methods=['GET', 'POST'])
def edit_user(username):
    if not current_user.is_admin:
        flash(_('Only an admin can edit users!'))
        return redirect(url_for('main.users'))
    user = User.query.filter_by(username=username).first_or_404()
    admin = User.query.filter_by(username='admin').first()
    if user==admin:
        flash(_('You cannot change the master admin!'))
        return redirect(url_for('main.users'))
    form = EditUserForm(user.username, user.email)
    form.locale.choices = [(x, x) for x in current_app.config['LANGUAGES']]
    form.timezone.choices = [(x, x) for x in current_app.config['TIMEZONES']]
    if form.validate_on_submit():
        user.username=form.username.data, 
        user.email=form.email.data,
        user.locale=form.locale.data,
        user.timezone=form.timezone.data,
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
        form.timezone.data = user.timezone
        form.about_me.data = user.about_me
        form.is_admin.data = user.is_admin
    return render_template('edit_form.html', title=_('Edit User'), form=form)

@bp.route('/set_admin/<username>')
@login_required
def set_admin(username):
    user = User.query.filter_by(username=username).first_or_404()
    if not current_user.is_admin:
        flash(_('Only an admin can set the admin rights!'))
        return redirect(url_for('main.user', username=user.username))
    user.is_admin = True
    db.session.commit()
    return redirect(url_for('main.user', username=user.username))

@bp.route('/revoke_admin/<username>')
@login_required
def revoke_admin(username):
    user = User.query.filter_by(username=username).first_or_404()
    admin = User.query.filter_by(username='admin').first()
    if user==admin:
        flash(_('You cannot change the master admin!'))
        return redirect(url_for('main.user', username=user.username))
    if not current_user.is_admin:
        flash(_('Only an admin can revoke the admin rights!'))
        return redirect(url_for('main.user', username=user.username))
    user.is_admin = True
    db.session.commit()
    return redirect(url_for('main.user', username=user.username))

@bp.route('/administration')
@login_required
def administration():
    return render_template('administration.html',
                           title= _('Administration'))

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

@bp.route('/edit_profile_picture', methods=['GET', 'POST'])
@login_required
def edit_profile_picture():
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
        return redirect(url_for('main.user', username=current_user.username))
    return render_template('edit_form.html', 
                           title=_('Profile Picture'), 
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
