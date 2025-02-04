import os
from cryptography.fernet import Fernet

# Retrieve the API key from the environment variable
api_key = os.getenv('BUNGIE_API_KEY')

if not api_key:
    raise ValueError("BUNGIE_API_KEY environment variable not set")

# Convert the API key to bytes
api_key_bytes = api_key.encode()

# Generate a key for encryption
key = Fernet.generate_key()
cipher_suite = Fernet(key)

# Encrypt the API key
encrypted_api_key = cipher_suite.encrypt(api_key_bytes)

# Save the key and encrypted API key to a file
with open('key.txt', 'w') as file:
    file.write(f"key: {key.decode()}\n")
    file.write(f"encrypted_api_key: {encrypted_api_key.decode()}\n")

print("key.txt file has been generated.")