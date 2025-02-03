import tkinter as tk
from tkinter import messagebox
from requests_oauthlib import OAuth2Session
from flask import Flask, request, redirect
import requests
import webbrowser
import os
import json
import threading

# Bungie API Client Details
CLIENT_ID = '48933'
API_KEY = os.getenv('BUNGIE_API_KEY')
REDIRECT_URI = 'https://localhost:8080/callback'

# OAuth Endpoints
authorization_base_url = 'https://www.bungie.net/en/OAuth/Authorize'
token_url = 'https://www.bungie.net/Platform/App/OAuth/token/'

app = Flask(__name__)

# UI
class App(tk.Tk):    
    def __init__(self):
        super().__init__()
        self.title("Destiny 2 Subclass RGB Sync")
        self.geometry("400x200")

        self.user_name_label = tk.Label(self, text="Please Sign In", font=("Arial", 14))
        self.user_name_label.pack(pady=10)

        self.super_label = tk.Label(self, text="Super: Unknown", font=("Arial", 12))
        self.super_label.pack(pady=10)

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

    def fetch_profile(self, access_token, membership_id, membership_type):
        headers = {
            'X-API-Key': API_KEY,
            'Authorization': f'Bearer {access_token}'
        }

        # Step 1: Get character data
        url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/?components=200"

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return

        response_text = response.content.decode('utf-8-sig')
        profile_data = json.loads(response_text)

        characters = profile_data.get("Response", {}).get("characters", {}).get("data", {})
        if not characters:
            return

        character_id = list(characters.keys())[0]  # Get the first available character ID

        # Step 2: Get subclass details
        subclass_url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/Character/{character_id}/?components=205"

        response = requests.get(subclass_url, headers=headers)
        if response.status_code != 200:
            return

        subclass_data = json.loads(response.content.decode('utf-8-sig'))

        # Extract subclass information
        equipped_subclass = None
        equipped_super = "Unknown Super"

        for item in subclass_data.get("Response", {}).get("equipment", {}).get("data", {}).get("items", []):
            if item["bucketHash"] == 3284755031:  # Subclass bucket
                equipped_subclass = item["itemHash"]
                break

        if equipped_subclass:
            equipped_super = self.get_super_name(equipped_subclass)

        # 🔥 Update UI safely on the main thread
        self.after(0, self.display_super, equipped_super)

        # 🔄 Refresh every 5 seconds on the main thread
        self.after(5000, lambda: threading.Thread(target=self.fetch_profile, args=(access_token, membership_id, membership_type)).start())

    def get_super_name(self, subclass_hash):
        # Mapping of subclass hashes to Supers
        subclass_supers = {
            3628991659: "Golden Gun",        # Gunslinger
            1334959255: "Blade Barrage",     # Way of a Thousand Cuts
            3481861797: "Arc Staff",         # Arcstrider
            2932390016: "Nova Bomb",         # Voidwalker
            3242928811: "Stormtrance",       # Stormcaller
            1751782730: "Chaos Reach",       # Chaos Reach
            3544605070: "Fist of Havoc",     # Striker
            2009185145: "Burning Maul",      # Sunbreaker
            2758933481: "Thundercrash",      # Code of the Missile
            3941205951: "Well of Radiance",  # Dawnblade
            2550323932: "Sentinel Shield",   # Sentinel
            4264096383: "Glacial Quake",     # Behemoth
            1220324104: "Winter's Wrath",    # Shadebinder
        }
        return subclass_supers.get(subclass_hash, "Unknown Super")

    def display_user_user(self, username):
        self.after(0, lambda: self.user_name_label.config(text=f"Welcome, {username}"))

    def display_super(self, super_name):
        self.after(0, lambda: self.super_label.config(text=f"Super: {super_name}"))

@app.route('/callback')
def callback():
    try:
        bungie = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
        authorization_response = request.url

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

        access_token = token.get('access_token', None)
        membership_id = token.get('membership_id', None)
        expires_in = token.get('expires_in', 'Unknown')

        if not access_token:
            raise ValueError("Access token not found in response")

        threading.Thread(target=app_instance.fetch_profile, args=(access_token, membership_id, 3)).start()  # Assuming Steam (3) for now

        return "Authentication successful! You can close this window now."
    except Exception as e:
        messagebox.showerror("Error", "An error occurred during authentication")
        return "An error occurred during authentication."

if __name__ == '__main__':
    app_instance = App()
    app_instance.mainloop()
