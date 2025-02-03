def fetch_profile(self, access_token, membership_id, membership_type):
    def fetch_data():
        headers = {
            'X-API-Key': API_KEY,
            'Authorization': f'Bearer {access_token}'
        }

        # Step 1: Get character data (with definitions=true)
        url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/?components=200&definitions=true"
        print(f"🔵 Fetching character data from: {url}")

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
        subclass_url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/Character/{character_id}/?components=205&definitions=true"
        print(f"🔵 Fetching subclass data from: {subclass_url}")

        response = requests.get(subclass_url, headers=headers)
        if response.status_code != 200:
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
            # Using definitions from the API response
            subclass_name = equipped_subclass.get('displayProperties', {}).get('name', "Unknown Subclass")
            equipped_super = equipped_subclass.get('superAbility', "Unknown Super")

        # 🔥 Update UI safely on the main thread
        self.after(0, lambda: self.display_subclass_and_super(subclass_name, equipped_super))

        # 🔄 Schedule next update in 5 seconds
        self.after(5000, lambda: self.fetch_profile(access_token, membership_id, membership_type))

    threading.Thread(target=fetch_data).start()
