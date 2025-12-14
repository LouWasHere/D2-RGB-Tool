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
from cryptography.fernet import Fernet
import time
import subprocess
import psutil
import pystray
from PIL import Image, ImageDraw

print("🔵 Starting D2RGBTool...")

# Function to read and decrypt the API key
def get_decrypted_api_key():
    # Determine the path to the key.txt file
    if hasattr(sys, '_MEIPASS'):
        key_file_path = os.path.join(sys._MEIPASS, 'key.txt')
    else:
        key_file_path = 'key.txt'

    with open(key_file_path, 'r') as file:
        lines = file.readlines()
        key = lines[0].strip().split(': ')[1].encode()
        encrypted_api_key = lines[1].strip().split(': ')[1].encode()

    cipher_suite = Fernet(key)
    decrypted_api_key = cipher_suite.decrypt(encrypted_api_key).decode()
    return decrypted_api_key

# Bungie API Client Details
CLIENT_ID = '48933'
API_KEY = get_decrypted_api_key()
REDIRECT_URI = 'https://localhost:8080/callback'

# OAuth Endpoints
authorization_base_url = 'https://www.bungie.net/en/OAuth/Authorize'
token_url = 'https://www.bungie.net/Platform/App/OAuth/token/'

app = Flask(__name__)

# Caching the manifest data to avoid redundant downloads
CACHE_FILE = "subclass_cache.json"

# OpenRGB Client
client = None

def is_process_running(process_name):
    """Check if a process is currently running."""
    for proc in psutil.process_iter(['pid', 'name']):
        if process_name.lower() in proc.info['name'].lower():
            return True
    return False

def launch_openrgb():
    """Launch OpenRGB if it's not already running."""
    try:
        if not is_process_running("OpenRGB"):
            print("🟢 Launching OpenRGB...")
            # Try common OpenRGB installation paths
            openrgb_paths = [
                r"C:\Program Files\OpenRGB\OpenRGB.exe",
                r"C:\Program Files (x86)\OpenRGB\OpenRGB.exe",
                r"C:\OpenRGB\OpenRGB.exe",
                "OpenRGB.exe"  # If it's in PATH
            ]
            
            for path in openrgb_paths:
                if os.path.exists(path):
                    # Launch with server enabled
                    subprocess.Popen([path, "--server", "--server-port", "6742"], 
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                    print(f"🟢 OpenRGB launched from: {path}")
                    return True
            
            print("❌ OpenRGB executable not found")
            return False
        else:
            print("🟢 OpenRGB is already running")
            return True
    except Exception as e:
        print(f"❌ Error launching OpenRGB: {e}")
        return False

def connect_to_openrgb():
    """Connect to OpenRGB server with retry logic."""
    global client
    max_retries = 10
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            client = OpenRGBClient()
            print("🟢 Connected to OpenRGB")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"🟡 Attempt {attempt + 1} failed, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                print(f"❌ Failed to connect to OpenRGB after {max_retries} attempts: {e}")
                return False
    return False

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
    if app_instance and hasattr(app_instance, 'show_download_indicator'):
        app_instance.after(0, app_instance.show_download_indicator)
    subclass_data = get_subclass_hashes()
    if app_instance and hasattr(app_instance, 'hide_download_indicator'):
        app_instance.after(0, app_instance.hide_download_indicator)

    return subclass_data

def create_tray_icon():
    """Create a simple tray icon image."""
    # Create a simple icon
    image = Image.new('RGB', (64, 64), color='black')
    draw = ImageDraw.Draw(image)
    draw.ellipse([16, 16, 48, 48], fill='purple')
    return image

# UI
class App(tk.Tk):    
    def __init__(self):
        super().__init__()
        self.title("Destiny 2 Subclass RGB Sync")
        self.geometry("400x250")
        
        # Add prismatic color cycling variables
        self.prismatic_colors = [
            RGBColor(255, 0, 255),    # Void purple
            RGBColor(128, 188, 236),  # Arc blue
            RGBColor(248, 100, 28),   # Solar orange
            RGBColor(33, 54, 255),    # Stasis blue
            RGBColor(56, 228, 100),   # Strand green
        ]
        self.prismatic_color_index = 0
        self.prismatic_cycling = False
        
        # Token storage
        self.token_file = "tokens.txt"
        self.access_token = None
        self.membership_id = None
        self.membership_type = None
        
        # Tray variables
        self.tray_icon = None
        self.is_minimized_to_tray = False
        
        # Active/Inactive mode
        self.active_mode = True

        self.user_name_label = tk.Label(self, text="Please Sign In", font=("Arial", 14))
        self.user_name_label.pack(pady=10)

        self.subclass_label = tk.Label(self, text="Subclass: Unknown", font=("Arial", 12))
        self.subclass_label.pack(pady=5)

        self.sign_in_button = tk.Button(self, text="Sign In with Bungie.net", command=self.sign_in)
        self.sign_in_button.pack(pady=20)

        self.download_label = tk.Label(self, text="", font=("Arial", 12))
        self.download_label.pack(pady=5)
        
        # Add logout button
        self.logout_button = tk.Button(self, text="Logout", command=self.logout)
        self.logout_button.pack(pady=10)
        self.logout_button.pack_forget()  # Initially hidden
        
        # Add toggle mode button
        self.mode_button = tk.Button(self, text="Mode: Active", command=self.toggle_mode)
        self.mode_button.pack(pady=5)
        
        # Override close button to minimize to tray
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        
        # Initialize OpenRGB and auto-login
        self.initialize_app()

    def initialize_app(self):
        """Initialize the app - launch OpenRGB, connect, and auto-login."""
        def init_sequence():
            # Launch OpenRGB
            if launch_openrgb():
                time.sleep(3)  # Give OpenRGB time to start
                
                # Connect to OpenRGB
                if connect_to_openrgb():
                    print("🟢 OpenRGB initialization complete")
                else:
                    print("❌ Failed to connect to OpenRGB")
            
            # Try auto-login
            if self.auto_login():
                # If auto-login successful, minimize to tray after a short delay
                self.after(2000, self.minimize_to_tray)
            
        # Run initialization in a separate thread
        threading.Thread(target=init_sequence, daemon=True).start()

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
            if not client:
                print("❌ OpenRGB client not connected")
                return
                
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
    
            # Schedule next update in 5 seconds only if in active mode
            if self.active_mode:
                self.after(5000, lambda: self.fetch_profile(access_token, membership_id, membership_type))
            else:
                print("🟡 Profile fetching paused (inactive mode)")
    
        threading.Thread(target=fetch_data).start()
    
    def display_user_user(self, display_name):
        """Update the UI to show the signed-in user's Bungie display name."""
        self.user_name_label.config(text=f"Welcome, {display_name}")
        self.sign_in_button.pack_forget()  # Remove the Sign In button once user is logged in
        self.logout_button.pack(pady=10)  # Show logout button
    
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
    
    def toggle_mode(self):
        """Toggle between active and inactive modes."""
        self.active_mode = not self.active_mode
        mode_text = "Active" if self.active_mode else "Inactive"
        self.mode_button.config(text=f"Mode: {mode_text}")
        
        if not self.active_mode:
            # Set to default color when inactive
            self.prismatic_cycling = False
            if client:
                for device in client.devices:
                    device.set_color(RGBColor(255, 0, 255))
            print(f"🟡 Mode switched to: {mode_text}")
        else:
            print(f"🟢 Mode switched to: {mode_text}")
    
    def update_motherboard_led(self, subclass_name):
        """Update the motherboard LED based on the subclass name."""
        if not client or not self.active_mode:
            return
            
        subclass_name = subclass_name.lower()
        
        # Stop prismatic cycling if switching to another subclass
        if "prismatic" not in subclass_name:
            self.prismatic_cycling = False
        
        if subclass_name == "nightstalker" or subclass_name == "voidwalker" or subclass_name == "sentinel":
            for device in client.devices:
                device.set_color(RGBColor(255,0,255))
        elif subclass_name == "arcstrider" or subclass_name == "stormcaller" or subclass_name == "striker":
            for device in client.devices:
                device.set_color(RGBColor(128,188,236))
        elif subclass_name == "gunslinger" or subclass_name == "dawnblade" or subclass_name == "sunbreaker":
            for device in client.devices:
                device.set_color(RGBColor(248,100,28))
        elif subclass_name == "shadebinder" or subclass_name == "revenant" or subclass_name == "behemoth":
            for device in client.devices:
                device.set_color(RGBColor(33,54,255))
        elif subclass_name == "broodweaver" or subclass_name == "beserker" or subclass_name == "threadrunner":
            for device in client.devices:
                device.set_color(RGBColor(56,228,100))
        elif "prismatic" in subclass_name:
            if not self.prismatic_cycling:
                self.prismatic_cycling = True
                self.start_prismatic_cycle()
        else:
            for device in client.devices:
                device.set_color(RGBColor(255,0,255))

    def start_prismatic_cycle(self):
        """Start the prismatic color cycling effect with smooth transitions."""
        self.prismatic_step = 0
        self.prismatic_steps_per_color = 50  # Number of steps to transition between colors
        
        def interpolate_color(color1, color2, factor):
            """Interpolate between two colors. factor should be between 0 and 1."""
            r = int(color1.red + (color2.red - color1.red) * factor)
            g = int(color1.green + (color2.green - color1.green) * factor)
            b = int(color1.blue + (color2.blue - color1.blue) * factor)
            return RGBColor(r, g, b)
        
        def cycle_colors():
            if self.prismatic_cycling and client:
                # Calculate current and next color indices
                current_color_index = self.prismatic_color_index
                next_color_index = (self.prismatic_color_index + 1) % len(self.prismatic_colors)
                
                # Calculate interpolation factor (0 to 1)
                factor = self.prismatic_step / self.prismatic_steps_per_color
                
                # Get interpolated color
                current_color = self.prismatic_colors[current_color_index]
                next_color = self.prismatic_colors[next_color_index]
                interpolated_color = interpolate_color(current_color, next_color, factor)
                
                # Set the color on all devices
                for device in client.devices:
                    device.set_color(interpolated_color)
                
                # Update step counter
                self.prismatic_step += 1
                
                # Check if we've completed the transition to the next color
                if self.prismatic_step >= self.prismatic_steps_per_color:
                    self.prismatic_step = 0
                    self.prismatic_color_index = (self.prismatic_color_index + 1) % len(self.prismatic_colors)
                
                # Schedule the next color change (faster for smooth transitions)
                self.after(100, cycle_colors)  # 100ms = smooth transitions
        
        cycle_colors()

    def show_download_indicator(self):
        """Show the download indicator."""
        self.download_label.config(text="Downloading Data from Bungie...")

    def hide_download_indicator(self):
        """Hide the download indicator."""
        self.download_label.config(text="")
    
    def minimize_to_tray(self):
        """Minimize the app to system tray."""
        self.withdraw()  # Hide the window
        self.is_minimized_to_tray = True
        
        if not self.tray_icon:
            # Create tray menu
            menu = pystray.Menu(
                pystray.MenuItem("Show", self.show_window),
                pystray.MenuItem("Toggle Mode", self.toggle_mode_tray),
                pystray.MenuItem("Logout", self.logout),
                pystray.MenuItem("Exit", self.quit_app)
            )
            
            # Create tray icon
            self.tray_icon = pystray.Icon(
                "D2RGBTool",
                create_tray_icon(),
                "Destiny 2 RGB Sync",
                menu
            )
            
            # Run tray icon in separate thread
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
    
    def toggle_mode_tray(self, icon=None, item=None):
        """Toggle mode from system tray menu."""
        self.toggle_mode()
    
    def show_window(self, icon=None, item=None):
        """Show the main window from tray."""
        self.deiconify()  # Show the window
        self.lift()  # Bring to front
        self.is_minimized_to_tray = False
    
    def quit_app(self, icon=None, item=None):
        """Quit the application."""
        if self.tray_icon:
            self.tray_icon.stop()
        self.quit()
        self.destroy()
    
    def save_tokens(self, access_token, membership_id, membership_type):
        """Save tokens to encrypted file."""
        try:
            # Generate a simple key for token encryption
            key = Fernet.generate_key()
            cipher_suite = Fernet(key)
            
            token_data = {
                "access_token": access_token,
                "membership_id": membership_id,
                "membership_type": membership_type
            }
            
            encrypted_data = cipher_suite.encrypt(json.dumps(token_data).encode())
            
            token_file_path = self.token_file
            if hasattr(sys, '_MEIPASS'):
                # For compiled version, save in the same directory as executable
                token_file_path = os.path.join(os.path.dirname(sys.executable), self.token_file)
            
            with open(token_file_path, 'w') as file:
                file.write(f"key: {key.decode()}\n")
                file.write(f"encrypted_tokens: {encrypted_data.decode()}\n")
                
            print("🟢 Tokens saved successfully")
        except Exception as e:
            print(f"❌ Error saving tokens: {e}")
    
    def load_tokens(self):
        """Load tokens from encrypted file."""
        try:
            token_file_path = self.token_file
            if hasattr(sys, '_MEIPASS'):
                token_file_path = os.path.join(os.path.dirname(sys.executable), self.token_file)
            
            if not os.path.exists(token_file_path):
                return None
                
            with open(token_file_path, 'r') as file:
                lines = file.readlines()
                key = lines[0].strip().split(': ')[1].encode()
                encrypted_data = lines[1].strip().split(': ')[1].encode()
            
            cipher_suite = Fernet(key)
            decrypted_data = cipher_suite.decrypt(encrypted_data).decode()
            token_data = json.loads(decrypted_data)
            
            return token_data
        except Exception as e:
            print(f"❌ Error loading tokens: {e}")
            return None
    
    def validate_token(self, access_token):
        """Validate if the access token is still valid."""
        try:
            headers = {
                'X-API-Key': API_KEY,
                'Authorization': f'Bearer {access_token}'
            }
            
            # Test the token by making a simple API call
            test_url = "https://www.bungie.net/Platform/User/GetMembershipsForCurrentUser/"
            response = requests.get(test_url, headers=headers)
            
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error validating token: {e}")
            return False
    
    def auto_login(self):
        """Try to automatically log in using saved tokens."""
        token_data = self.load_tokens()
        if token_data:
            access_token = token_data.get('access_token')
            if access_token and self.validate_token(access_token):
                self.access_token = access_token
                self.membership_id = token_data.get('membership_id')
                self.membership_type = token_data.get('membership_type')
                
                print("🟢 Auto-login successful")
                
                # Start profile fetching
                self.fetch_profile(self.access_token, self.membership_id, self.membership_type)
                return True
            else:
                print("🟡 Saved token is invalid or expired")
        
        return False
    
    def clear_tokens(self):
        """Clear saved tokens (for logout functionality)."""
        try:
            token_file_path = self.token_file
            if hasattr(sys, '_MEIPASS'):
                token_file_path = os.path.join(os.path.dirname(sys.executable), self.token_file)
            
            if os.path.exists(token_file_path):
                os.remove(token_file_path)
                print("🟢 Tokens cleared")
        except Exception as e:
            print(f"❌ Error clearing tokens: {e}")

    def logout(self, icon=None, item=None):
        """Manually log out and clear saved tokens."""
        self.clear_tokens()
        self.user_name_label.config(text="Please Sign In")
        self.subclass_label.config(text="Subclass: Unknown")
        self.sign_in_button.pack(pady=20)
        self.logout_button.pack_forget()
        self.prismatic_cycling = False
        
        # Show window if called from tray
        if self.is_minimized_to_tray:
            self.show_window()

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
        
        # Save tokens for persistent login
        app_instance.after(0, lambda: app_instance.save_tokens(access_token, membership_id, membership_type))

        # Start the profile fetch with the correct membership ID and type
        app_instance.after(0, lambda: app_instance.fetch_profile(access_token, membership_id, membership_type))
        
        # Minimize to tray after successful login
        app_instance.after(2000, app_instance.minimize_to_tray)

        return "Authentication successful! You can close this window now."
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
        return "An error occurred during authentication."


if __name__ == '__main__':
    app_instance = App()
    app_instance.mainloop()