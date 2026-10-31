import os
import httpx
from dotenv import load_dotenv

load_dotenv()

class CheckoutClient:
    def __init__(self):
        # TODO: Read API key from environment variable
        self.api_key = os.getenv("CHECKOUT_SECRET_KEY")

        # TODO: Read Checkout.com base URL
        self.base_url = os.getenv("CHECKOUT_BASE_URL")