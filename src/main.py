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

# Caching the manifest data to avoid redundant downloads
CACHE_FILE = "subclass_cache.json"

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

def get_cached_subclass_hashes():
    """Load subclass hashes from a local cache file if available, otherwise fetch new data."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)

    # If no cache exists, fetch fresh data
    print("🟢 No cache found. Fetching subclass hashes...")
    subclass_data = get_subclass_hashes()

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
    
            # Print full response to check the structure
            print(f"🔴 Full Membership Data: {json.dumps(profile_data, indent=2)}")
    
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
    
            if equipped_subclass:
                # Fetch subclass name from the cached data
                subclass_name = self.get_subclass_name_from_cache(equipped_subclass)
    
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
        subclass_supers = get_cached_subclass_hashes()

        subclass_data = subclass_supers.get(str(subclass_hash), None)
        if subclass_data:
            return subclass_data
        else:
            print(f"❌ Subclass Hash Not Found: {subclass_hash}")
            return "Unknown Subclass"

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
