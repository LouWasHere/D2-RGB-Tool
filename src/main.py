import tkinter as tk
from tkinter import messagebox
from requests_oauthlib import OAuth2Session
from flask import Flask, request, redirect
import requests
import webbrowser
import os

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
        app.run(ssl_context='adhoc', port=8080)
        
    def fetch_profile(self, access_token):
        headers = {
            'X-API-Key': API_KEY,
            'Authorization': f'Bearer {access_token}'
        }
        
        url = f"https://www.bungie.net/Platform/User/GetBungieAccountInfo/"
        response = requests.get(url, headers=headers)
        profile_data = response.json()
        
        #Extract the user's display name and membership ID
        if 'Response' in profile_data:
            bungie_account = profile_data['Response'][0]
            membership_id = bungie_account['membershipId']
            membership_type = bungie_account['membershipType']
            username = bungie_account['displayName']
            
            self.display_user_user(username)
            
            print(f"Membership ID: {membership_id}")
            print(f"Membership Type: {membership_type}")
            print(f"Username: {username}")
        else:
            messagebox.showerror("Error", "Failed to fetch profile data")
        
    def display_user_user(self, username):
        self.user_name_label.config(text=f"Welcome, {username}")
        
@app.route('/callback')
def callback():
    try:
        bungie = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
        authorization_response = request.url
        token = bungie.fetch_token(token_url, authorization_response=authorization_response)
        access_token = token['access_token']
        print(f"Access Token: {access_token}")
        
        app_instance = App()
        app_instance.fetch_profile(access_token)
        
        return "Authentication successful! You can close this window now."
    except Exception as e:
        print(f"An error occurred: {e}")
        messagebox.showerror("Error", "An error occurred during authentication")
        return "An error occurred during authentication"

if __name__ == '__main__':
    app_instance = App()
    app_instance.mainloop()