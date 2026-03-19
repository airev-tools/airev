import os

api_key = os.environ["API_KEY"]
token = os.getenv("AUTH_TOKEN")
secret = os.getenv("SECRET_KEY", "fallback")
