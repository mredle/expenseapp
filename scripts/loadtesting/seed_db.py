# -*- coding: utf-8 -*-

import sys
import os
import random
from faker import Faker
from datetime import datetime, timezone

# Add the root project directory to the Python path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models import User, Event, EventUser, Expense, Currency, Post, Settlement
from config import Config

fake = Faker()

# Configuration
NUM_USERS = 500
NUM_EVENTS = 100
EXPENSES_PER_EVENT = 20
STANDARD_PASSWORD = 'loadtestpassword'

class LoadTestConfig(Config):
    # Use your local Postgres or MySQL database for the load test!
    # Do NOT use SQLite for load testing!
    pass

app = create_app(LoadTestConfig)

def seed():
    with app.app_context():
        print("🌱 Starting database seed...")
        
        # 1. Get a default currency (Assuming CHF exists from your init scripts)
        currency = Currency.query.filter_by(code='CHF').first()
        if not currency:
            currency = Currency(code='CHF', name='Swiss Franc')
            db.session.add(currency)
            db.session.commit()

        # 2. Create Users
        print(f"👤 Creating {NUM_USERS} users...")
        users = []
        for i in range(NUM_USERS):
            # We use a predictable username pattern so Locust knows exactly how to log in!
            user = User(
                username=f'loaduser_{i}',
                email=fake.unique.email(),
                locale='en'
            )
            user.set_password(STANDARD_PASSWORD)
            db.session.add(user)
            users.append(user)
        db.session.commit()

        # 3. Create Events
        print(f"🎉 Creating {NUM_EVENTS} events...")
        events = []
        
        # Wrap the generation loop so SQLAlchemy doesn't panic over uncommitted relationships
        with db.session.no_autoflush:
            for i in range(NUM_EVENTS):
                admin = random.choice(users)
                event = Event(
                    name=fake.catch_phrase(),
                    base_currency=currency,
                    admin=admin,
                    date=datetime.now(timezone.utc),
                    currencies=[currency],
                    exchange_fee=0.0,
                    fileshare_link=""
                )
                db.session.add(event)
                events.append(event)
                
                # Add 2 to 10 random users to this event
                event_participants = random.sample(users, random.randint(2, 10))
                if admin not in event_participants:
                    event_participants.append(admin)
                    
                for p in event_participants:
                    eu = EventUser(username=p.username, email=p.email, weighting=1.0, locale='en')
                    event.add_user(eu)
                    
        db.session.commit()

        # 4. Create Expenses, Posts, and Settlements
        print(f"💸 Creating Expenses, Posts, and Settlements...")
        
        # We use no_autoflush to prevent SQLAlchemy relationship warnings
        with db.session.no_autoflush:
            for event in events:
                participants = event.users.all()
                if len(participants) < 2:
                    continue
                    
                # --- A. Generate Expenses ---
                for _ in range(EXPENSES_PER_EVENT):
                    purchaser = random.choice(participants)
                    consumers = random.sample(participants, random.randint(1, len(participants)))
                    
                    expense = Expense(
                        user=purchaser,
                        event=event,
                        currency=currency,
                        amount=round(random.uniform(5.0, 500.0), 2),
                        affected_users=consumers,
                        date=fake.date_time_this_year(tzinfo=timezone.utc),
                        description=fake.word()
                    )
                    db.session.add(expense)

                # --- B. Generate 2 to 10 Posts ---
                num_posts = random.randint(2, 10)
                for _ in range(num_posts):
                    post_author = random.choice(participants)
                    post = Post(
                        body=fake.sentence(),
                        timestamp=fake.date_time_this_year(tzinfo=timezone.utc),
                        author=post_author,
                        event=event
                    )
                    db.session.add(post)

                # --- C. Generate random Settlements (Payments) ---
                # Let's generate a random number of payments per event (e.g., 2 to 8)
                num_settlements = random.randint(2, 8)
                for _ in range(num_settlements):
                    # Pick two distinct users for the sender and recipient
                    sender, recipient = random.sample(participants, 2)
                    
                    settlement = Settlement(
                        sender=sender,
                        recipient=recipient,
                        event=event,
                        currency=currency,
                        amount=round(random.uniform(10.0, 200.0), 2),
                        draft=False, # Set to False so it counts as a real, completed payment
                        date=fake.date_time_this_year(tzinfo=timezone.utc),
                        description=fake.word()
                    )
                    db.session.add(settlement)
                    
        db.session.commit()
        print("✅ Seeding complete!")

if __name__ == '__main__':
    seed()