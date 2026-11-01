import os
from dotenv import load_dotenv

load_dotenv()

public_key = os.getenv("CHECKOUT_PUBLIC_KEY")

if public_key and public_key.startswith("pk_sbox_"):
    print("Sandbox Public Key loaded successfully")
else:
    print("Public Key configuration is missing or invalid")