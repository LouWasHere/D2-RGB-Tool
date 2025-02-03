import tkinter as tk
from tkinter import messagebox
from requests_oauthlib import OAuth2Session
from flask import Flask, request, redirect
import requests
import webbrowser
import os
import json
import threading

#Bungie API Client Details
CLIENT_ID = '48933'
API_KEY = os.getenv('BUNGIE_API_KEY')
REDIRECT_URI = 'https://localhost:8080/callback'

#OAuth Endpoints
authorization_base_url = 'https://www.bungie.net/en/OAuth/Authorize'
token_url = 'https://www.bungie.net/Platform/App/OAuth/token/'

app = Flask(__name__)

#UI
class App(tk.Tk):    
    def __init__(self):
        super().__init__()
        self.title("Destiny 2 Subclass RGB Sync")
        self.geometry("400x200")
        self.user_name_label = tk.Label(self, text="Please Sign In", font=("Arial", 14))
        self.user_name_label.pack(pady=20)
        
        self.sign_in_button = tk.Button(self, text="Sign In with Bungie.net", command=self.sign_in)
        self.sign_in_button.pack(pady=20)
        
    def sign_in(self):
        bungie = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
        authorization_url, state = bungie.authorization_url(authorization_base_url)
        self.redirect_to_bungie(authorization_url)
        
    def redirect_to_bungie(self, url):
        webbrowser.open(url)
        self.wait_for_callback()
        
    def wait_for_callback(self):
        flask_thread = threading.Thread(target=app.run, kwargs={'ssl_context': 'adhoc', 'port': 8080})
        flask_thread.daemon = True
        flask_thread.start()
        
    def fetch_profile(self, access_token):
        headers = {
            'X-API-Key': API_KEY,
            'Authorization': f'Bearer {access_token}'
        }
    
        url = "https://www.bungie.net/Platform/User/GetMembershipsForCurrentUser/"
    
        # Debug: Print access token before making the request
        print(f"Using Access Token: {access_token}")
    
        response = requests.get(url, headers=headers)
    
        # Print response details for debugging
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Content: {response.text}")
    
        if response.status_code == 401:
            raise ValueError("Unauthorized: Access token is invalid or expired.")
    
        if response.status_code != 200:
            raise ValueError(f"API request failed! Status Code: {response.status_code}, Response: {response.text}")
    
        if not response.content.strip():
            raise ValueError("Bungie API returned an empty response!")
    
        try:
            response_text = response.content.decode('utf-8-sig')
            profile_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}, Raw Response: {response_text}")
    
        print(f"Parsed Profile Data: {json.dumps(profile_data, indent=2)}")
    
        if 'Response' in profile_data and 'destinyMemberships' in profile_data['Response']:
            destiny_membership = profile_data['Response']['destinyMemberships']
            if destiny_membership:
                membership_id = destiny_membership[0]['membershipId']
                membership_type = destiny_membership[0]['membershipType']
                username = destiny_membership[0].get('displayName', 'Unknown')
    
                self.display_user_user(username)
    
                print(f"Membership ID: {membership_id}")
                print(f"Membership Type: {membership_type}")
                print(f"Username: {username}")
            else:
                raise ValueError("No Destiny memberships found in response!")
        else:
            raise ValueError("Invalid API response format: Missing expected keys.")

        
    def display_user_user(self, username):
        self.user_name_label.config(text=f"Welcome, {username}")
        
@app.route('/callback')
@app.route('/callback')
def callback():
    try:
        bungie = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
        authorization_response = request.url

        print(f"Authorization Response: {authorization_response}")

        data = {
            'grant_type': 'authorization_code',
            'code': request.args['code'],
            'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT_URI
        }        

        response = requests.post(token_url, data=data)

        if response.status_code != 200:
            raise ValueError(f"Failed to get token: {response.text}")

        token = response.json()
        print(f"Token Response: {json.dumps(token, indent=2)}")  # Print full response

        access_token = token.get('access_token', None)
        expires_in = token.get('expires_in', 'Unknown')

        if not access_token:
            raise ValueError("Access token not found in response")

        print(f"Access Token: {access_token}")
        print(f"Access Token Expires In: {expires_in} seconds")

        app_instance = App()
        app_instance.fetch_profile(access_token)

        return "Authentication successful! You can close this window now."
    except Exception as e:
        print(f"An error occurred: {e}")
        messagebox.showerror("Error", "An error occurred during authentication")
        return "An error occurred during authentication."


if __name__ == '__main__':
    app_instance = App()
    app_instance.mainloop()
