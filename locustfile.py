# -*- coding: utf-8 -*-

# locustfile.py
import random
from locust import HttpUser, task, between
from bs4 import BeautifulSoup
from faker import Faker

fake = Faker()

class ExpenseAppUser(HttpUser):
    # Simulate a user taking 2 to 5 seconds to read each page before clicking the next link
    wait_time = between(2, 5)
    
    def on_start(self):
        """Log the user in when they first arrive."""
        self.username = f"loaduser_{random.randint(0, 499)}"
        self.password = "loadtestpassword"
        
        # 1. Fetch the login page to grab the CSRF token!
        # (Flask requires CSRF tokens for all POST requests)
        response = self.client.get("/auth/authenticate_password")
        soup = BeautifulSoup(response.text, 'html.parser')
        csrf_token_input = soup.find('input', {'name': 'csrf_token'})
        
        self.csrf_token = csrf_token_input.get('value') if csrf_token_input else ""

        # 2. Submit the login form
        self.client.post("/auth/authenticate_password", data={
            "username": self.username,
            "password": self.password,
            "remember_me": False,
            "csrf_token": self.csrf_token
        })

    @task
    def full_user_journey(self):
        """Simulate a complete, sequential user session."""
        
        # ---------------------------------------------------------
        # STEP 1: Pagination (Click "Older Events" 0 to 10 times)
        # ---------------------------------------------------------
        pages_to_click = random.randint(0, 10)
        last_response = None
        
        for page in range(1, pages_to_click + 2): 
            # We hit the dashboard. The `name` groups these in the Locust UI.
            last_response = self.client.get(
                f"/event/index?page={page}", 
                name="/event/index?page=[num]"
            )

        # ---------------------------------------------------------
        # STEP 2: Open a random event from the current page
        # ---------------------------------------------------------
        soup = BeautifulSoup(last_response.text, 'html.parser')
        
        # Find all valid event links on the page
        event_links = [a['href'] for a in soup.find_all('a', href=True) if '/event/main/' in a['href']]
        
        if not event_links:
            return # If they clicked so far back there are no events, end the journey and start over
            
        target_event_url = random.choice(event_links)
        event_guid = target_event_url.split('/')[-1]
        
        # Click into the event
        event_response = self.client.get(target_event_url, name="/event/main/[guid]")

        # ---------------------------------------------------------
        # STEP 3: Write 0-1 Post (50% chance)
        # ---------------------------------------------------------
        if random.random() > 0.5:
            # We need to extract the CSRF token from the event page form to submit a post
            event_soup = BeautifulSoup(event_response.text, 'html.parser')
            post_csrf = event_soup.find('input', {'name': 'csrf_token'})
            
            post_data = {
                'body': fake.sentence(),
                'submit': 'Submit', # Standard WTForms submit button
            }
            if post_csrf:
                post_data['csrf_token'] = post_csrf.get('value')
                
            self.client.post(
                target_event_url, 
                data=post_data, 
                name="/event/main/[guid] (POST)"
            )

        # ---------------------------------------------------------
        # STEP 4: Check Expenses and filter for own entries
        # ---------------------------------------------------------
        # First, load the main expenses page
        self.client.get(f"/event/expenses/{event_guid}", name="/event/expenses/[guid]")
        
        # Then, simulate clicking the filter button (assuming it uses a URL parameter like ?user_id=me)
        # Adjust the '?user=' parameter to match whatever your actual route expects!
        self.client.get(
            f"/event/expenses/{event_guid}?user={self.username}", 
            name="/event/expenses/[guid]?user=[username]"
        )

        # ---------------------------------------------------------
        # STEP 5: Open the Balance Sheet
        # ---------------------------------------------------------
        self.client.get(f"/event/balance/{event_guid}", name="/event/balance/[guid]")

        # ---------------------------------------------------------
        # STEP 6: Check User Profile
        # ---------------------------------------------------------
        self.client.get("/edit_profile", name="/edit_profile")