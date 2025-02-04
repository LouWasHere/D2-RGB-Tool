import tkinter as tk
from tkinter import messagebox
from requests_oauthlib import OAuth2Session
from flask import Flask, request, redirect
import requests
import webbrowser
import os
import sys
import json
import threading
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor

# Bungie API Client Details
CLIENT_ID = '48933'
API_KEY = os.getenv('BUNGIE_API_KEY')
REDIRECT_URI = 'https://localhost:8080/callback'

# OAuth Endpoints
authorization_base_url = 'https://www.bungie.net/en/OAuth/Authorize'
token_url = 'https://www.bungie.net/Platform/App/OAuth/token/'

app = Flask(__name__)

# Caching the manifest data to avoid redundant downloads
CACHE_FILE = "subclass_cache.json"

# OpenRGB Client
client = OpenRGBClient()

def get_manifest_url():
    print("🟢 Fetching Bungie's manifest URL...")
    """Fetches Bungie's manifest URL and returns the DestinyInventoryItemDefinition URL."""
    headers = {'X-API-Key': API_KEY}
    url = "https://www.bungie.net/Platform/Destiny2/Manifest/"

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise ValueError("Failed to fetch manifest")

    manifest = response.json()
    manifest_data = manifest['Response']['jsonWorldComponentContentPaths']['en']
    
    return manifest_data['DestinyInventoryItemDefinition']

def get_subclass_hashes():
    print("🟢 Fetching Subclass Hashes...")
    """Scrape DestinyInventoryItemDefinition for subclasses and their hashes."""
    # Get the correct URL for DestinyInventoryItemDefinition
    inventory_item_url = "https://www.bungie.net" + get_manifest_url()

    # Fetch the actual data from DestinyInventoryItemDefinition
    response = requests.get(inventory_item_url)
    if response.status_code != 200:
        raise ValueError("Failed to fetch subclass data from manifest")

    item_definitions = response.json()

    subclass_supers = {}

    # Loop through all items in the inventory item definition to find subclasses
    for item in item_definitions.values():
        if "itemType" in item and item["itemType"] == 16:  # Subclass item type
            subclass_name = item["displayProperties"]["name"]
            # Record subclass hash and name
            subclass_supers[item["hash"]] = subclass_name

    # Cache the subclass hash-to-name data
    with open(CACHE_FILE, "w") as f:
        json.dump(subclass_supers, f)

    print(f"🟢 Found {len(subclass_supers)} Subclasses")
    return subclass_supers

def get_cached_subclass_hashes(app_instance):
    """Load subclass hashes from a local cache file if available, otherwise fetch new data."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)

    # If no cache exists, fetch fresh data
    print("🟢 No cache found. Fetching subclass hashes...")
    app_instance.after(0, app_instance.show_download_indicator)
    subclass_data = get_subclass_hashes()
    app_instance.after(0, app_instance.hide_download_indicator)

    return subclass_data

# UI
class App(tk.Tk):    
    def __init__(self):
        super().__init__()
        self.title("Destiny 2 Subclass RGB Sync")
        self.geometry("400x250")

        self.user_name_label = tk.Label(self, text="Please Sign In", font=("Arial", 14))
        self.user_name_label.pack(pady=10)

        self.subclass_label = tk.Label(self, text="Subclass: Unknown", font=("Arial", 12))
        self.subclass_label.pack(pady=5)

        self.sign_in_button = tk.Button(self, text="Sign In with Bungie.net", command=self.sign_in)
        self.sign_in_button.pack(pady=20)

        self.download_label = tk.Label(self, text="", font=("Arial", 12))
        self.download_label.pack(pady=5)

    def sign_in(self):
        bungie = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
        authorization_url, state = bungie.authorization_url(authorization_base_url)
        self.redirect_to_bungie(authorization_url)

    def redirect_to_bungie(self, url):
        webbrowser.open(url)
        self.wait_for_callback()

    def wait_for_callback(self):
        if hasattr(sys, '_MEIPASS'):
            cert_path = os.path.join(sys._MEIPASS, 'cert.pem')
            key_path = os.path.join(sys._MEIPASS, 'key.pem')
        else:
            cert_path = 'cert.pem'
            key_path = 'key.pem'
        
        flask_thread = threading.Thread(target=app.run, kwargs={'ssl_context': (cert_path, key_path), 'port': 8080})
        flask_thread.daemon = True
        flask_thread.start()

    def fetch_profile(self, access_token, membership_id, membership_type):
        def fetch_data():
            headers = {
                'X-API-Key': API_KEY,
                'Authorization': f'Bearer {access_token}'
            }
    
            # Step 1: Get the Bungie membership information (Display Name)
            membership_url = "https://www.bungie.net/Platform/User/GetMembershipsForCurrentUser/"
            response = requests.get(membership_url, headers=headers)
    
            # Check for errors in the response
            if response.status_code != 200:
                print(f"❌ Error fetching membership data: {response.status_code}")
                return
    
            response_text = response.content.decode('utf-8-sig')
            profile_data = json.loads(response_text)
    
            # Extract the Bungie display name
            try:
                display_name = profile_data["Response"]["destinyMemberships"][0]["displayName"]
                print(f"🟢 User Display Name: {display_name}")
            except (KeyError, IndexError) as e:
                print(f"❌ Error extracting display name: {e}")
                display_name = "Unknown User"
    
            # Update UI with the user's display name
            self.after(0, self.display_user_user, display_name)
    
            # Step 2: Get subclass details from character profile
            subclass_url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/?components=200"
            response = requests.get(subclass_url, headers=headers)
    
            if response.status_code != 200:
                print(f"❌ Error fetching subclass data: {response.status_code}")
                return
    
            response_text = response.content.decode('utf-8-sig')
            profile_data = json.loads(response_text)
    
            # Extract character data
            characters = profile_data.get("Response", {}).get("characters", {}).get("data", {})
            if not characters:
                print("❌ No characters found!")
                return
    
            character_id = list(characters.keys())[0]  # Get the first available character ID
            print(f"🟢 Active Character ID: {character_id}")
    
            # Step 3: Get subclass details (with definitions=true)
            subclass_url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/Character/{character_id}/?components=205"
            response = requests.get(subclass_url, headers=headers)
            if response.status_code != 200:
                print(f"❌ Error fetching subclass data: {response.status_code}")
                return
    
            subclass_data = json.loads(response.content.decode('utf-8-sig'))
    
            # Extract subclass information
            equipped_subclass = None
            subclass_name = "Unknown Subclass"
    
            for item in subclass_data.get("Response", {}).get("equipment", {}).get("data", {}).get("items", []):
                if item["bucketHash"] == 3284755031:  # Subclass bucket
                    equipped_subclass = item["itemHash"]
                    break
    
            print(f"🟢 Equipped Subclass Hash: {equipped_subclass}")
    
            if equipped_subclass:
                # Fetch subclass name from the cached data
                subclass_name = self.get_subclass_name_from_cache(equipped_subclass)
            
            # Update the motherboard LED based on the subclass name
            self.after(0, lambda: self.update_motherboard_led(subclass_name))
    
            # Update UI safely on the main thread
            self.after(0, self.display_subclass, subclass_name)
    
            # Schedule next update in 5 seconds
            self.after(5000, lambda: self.fetch_profile(access_token, membership_id, membership_type))
    
        threading.Thread(target=fetch_data).start()
    
    def display_user_user(self, display_name):
        """Update the UI to show the signed-in user's Bungie display name."""
        self.user_name_label.config(text=f"Welcome, {display_name}")
        self.sign_in_button.pack_forget()  # Remove the Sign In button once user is logged in
    
    def display_subclass(self, subclass_name):
        """Update the UI to show the current subclass."""
        self.after(0, lambda: self.subclass_label.config(text=f"Subclass: {subclass_name}"))

    def get_subclass_name_from_cache(self, subclass_hash):
        """Fetch the subclass name from the cached subclass data."""
        subclass_supers = get_cached_subclass_hashes(self)

        subclass_data = subclass_supers.get(str(subclass_hash), None)
        if subclass_data:
            return subclass_data
        else:
            print(f"❌ Subclass Hash Not Found: {subclass_hash}")
            return "Unknown Subclass"
    
    def update_motherboard_led(self, subclass_name):
        """Update the motherboard LED based on the subclass name."""
        subclass_name = subclass_name.lower()
        if subclass_name == "nightstalker" or subclass_name == "voidwalker" or subclass_name == "sentinel":
            for device in client.devices:
                device.set_color(RGBColor(135,82,171))
        elif subclass_name == "arcstrider" or subclass_name == "stormcaller" or subclass_name == "striker":
            for device in client.devices:
                device.set_color(RGBColor(128,188,236))
        elif subclass_name == "gunslinger" or subclass_name == "dawnblade" or subclass_name == "sunbreaker":#
            for device in client.devices:
                device.set_color(RGBColor(248,100,28))
        elif subclass_name == "shadebinder" or subclass_name == "revenant" or subclass_name == "behemoth":
            for device in client.devices:
                device.set_color(RGBColor(33,54,156))
        elif subclass_name == "broodweaver" or subclass_name == "beserker" or subclass_name == "threadrunner":
            for device in client.devices:
                device.set_color(RGBColor(56,228,100))
        elif "prismatic" in subclass_name:
            for device in client.devices:
                device.set_color(RGBColor(250,72,183))
        else:
            for device in client.devices:
                device.set_color(RGBColor(158,24,227))

    def show_download_indicator(self):
        """Show the download indicator."""
        self.download_label.config(text="Downloading Data from Bungie...")

    def hide_download_indicator(self):
        """Hide the download indicator."""
        self.download_label.config(text="")

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

        if not access_token:
            raise ValueError("Access token missing from response")

        # Fetch the correct Destiny 2 membership ID
        headers = {
            'X-API-Key': API_KEY,
            'Authorization': f'Bearer {access_token}'
        }

        membership_url = "https://www.bungie.net/Platform/User/GetMembershipsForCurrentUser/"
        response = requests.get(membership_url, headers=headers)

        if response.status_code != 200:
            raise ValueError("Failed to fetch membership details")

        membership_data = response.json()
        memberships = membership_data.get("Response", {}).get("destinyMemberships", [])

        if not memberships:
            raise ValueError("No linked Destiny 2 accounts found!")

        # Get the correct membership ID and type
        membership_id = memberships[0]['membershipId']
        membership_type = memberships[0]['membershipType']  # Auto-detect platform

        print(f"🟢 Correct Membership ID: {membership_id}, Type: {membership_type}")

        # Start the profile fetch with the correct membership ID and type
        app_instance.after(0, lambda: app_instance.fetch_profile(access_token, membership_id, membership_type))

        return "Authentication successful! You can close this window now."
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
        return "An error occurred during authentication."


if __name__ == '__main__':
    app_instance = App()
    app_instance.mainloop()