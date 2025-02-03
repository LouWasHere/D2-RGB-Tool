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

def get_manifest_url():
    headers = {'X-API-Key': API_KEY}
    url = "https://www.bungie.net/Platform/Destiny2/Manifest/"
        
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise ValueError("Failed to fetch manifest URL")
        
    manifest = response.json()
    
    print(f"Manfiest Keys: {json.dumps(manifest, indent=2)}")
    
    manifest_data = manifest['Response']['jsonWorldComponentContentPaths']['en']
        
    return manifest_data
    
def get_subclass_hashes():
    manifest_url = get_manifest_url()
    response = requests.get(manifest_url)
    if response.status_code != 200:
        raise ValueError("Failed to getch subclass data")
        
    item_definitions = response.json()
    
    subclass_supers = {}
        
    for item in item_definitions.values():
        if "hash" not in item or "displayProperties" not in item:
            continue
        
        if item.get("itemType") == 21:  # Subclass item type
            subclass_name = item["displayProperties"]["name"]
            super_abilities = item.get("talentGrid", {}).get("gridName", "Unknown Super")
                
            subclass_supers[item["hash"]] = {"subclass_name": subclass_name, "supers": super_abilities}
            
    return subclass_supers

def get_cached_subclass_hashes():
    cache_file = "subclass_hashes.json"
    
    if not os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return json.load(f)
        
    subclass_data = get_subclass_hashes()
    
    with open(cache_file, "w") as f:
        json.dump(subclass_data, f)

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

        self.super_label = tk.Label(self, text="Super: Unknown", font=("Arial", 12))
        self.super_label.pack(pady=5)

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
            print("🟢 Thread started for fetching profile data.")
    
            headers = {
                'X-API-Key': API_KEY,
                'Authorization': f'Bearer {access_token}'
            }
    
            # Step 1: Get character data
            url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/?components=200"
            print(f"🔵 Fetching character data from: {url}")
    
            try:
                response = requests.get(url, headers=headers, timeout=10)  # Set a timeout in case it hangs
            except requests.RequestException as e:
                print(f"❌ Request failed: {e}")
                return
    
            print(f"🔴 API Response Status: {response.status_code}")
            print(f"🔴 API Response Content: {response.text}")
    
            if response.status_code != 200:
                print(f"❌ API request failed! Status: {response.status_code}")
                return
    
            response_text = response.content.decode('utf-8-sig')
            profile_data = json.loads(response_text)
    
            characters = profile_data.get("Response", {}).get("characters", {}).get("data", {})
            if not characters:
                print("❌ No characters found!")
                return
    
            character_id = list(characters.keys())[0]  # Get the first available character ID
            print(f"🟢 Active Character ID: {character_id}")
    
            # Step 2: Get subclass details
            subclass_url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/Character/{character_id}/?components=205"
            print(f"🔵 Fetching subclass data from: {subclass_url}")
    
            response = requests.get(subclass_url, headers=headers)
            if response.status_code != 200:
                print(f"❌ Failed to fetch subclass data! Status: {response.status_code}")
                return
    
            subclass_data = json.loads(response.content.decode('utf-8-sig'))
    
            # Extract subclass information
            equipped_subclass = None
            subclass_name = "Unknown Subclass"
            equipped_super = "Unknown Super"
    
            for item in subclass_data.get("Response", {}).get("equipment", {}).get("data", {}).get("items", []):
                if item["bucketHash"] == 3284755031:  # Subclass bucket
                    equipped_subclass = item["itemHash"]
                    break
    
            if equipped_subclass:
                subclass_name, equipped_super = self.get_subclass_and_super(equipped_subclass)
    
            print(f"✅ Subclass: {subclass_name}, Super: {equipped_super}")
    
            # 🔥 Update UI safely on the main thread
            self.after(0, lambda: self.display_subclass_and_super(subclass_name, equipped_super))
    
            # 🔄 Schedule next update in 5 seconds
            self.after(5000, lambda: self.fetch_profile(access_token, membership_id, membership_type))
    
        threading.Thread(target=fetch_data).start()

    def get_subclass_and_super(self, subclass_hash):
        subclass_supers = get_subclass_hashes()
        subclass_data = subclass_supers.get(subclass_hash, None)
        if not subclass_data:
            return "Unknown Subclass", "Unknown Super"
            
        subclass_name = subclass_data["subclass_name"]
        super_name = subclass_data["supers"]
            
        if "Prismatic" in subclass_name or "Light and Dark" in subclass_name:
            subclass_name = " (Prismatic)"
            
        return subclass_name, super_name

    def display_user_user(self, username):
        self.after(0, lambda: self.user_name_label.config(text=f"Welcome, {username}"))

    def display_subclass_and_super(self, subclass_name, super_name):
        self.after(0, lambda: self.subclass_label.config(text=f"Subclass: {subclass_name}"))
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

        if not access_token:
            raise ValueError("Access token missing from response")

        # 🔍 Fetch the correct Destiny 2 membership ID
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

        # Get the **correct** membership ID and type
        membership_id = memberships[0]['membershipId']
        membership_type = memberships[0]['membershipType']  # Auto-detect platform

        print(f"🟢 Correct Membership ID: {membership_id}, Type: {membership_type}")

        # 🔥 Start the profile fetch with the correct membership ID and type
        app_instance.after(0, lambda: app_instance.fetch_profile(access_token, membership_id, membership_type))

        return "Authentication successful! You can close this window now."
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
        return "An error occurred during authentication."


if __name__ == '__main__':
    app_instance = App()
    app_instance.mainloop()
