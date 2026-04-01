import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.environ.get("SUPABASE_URL", "http://localhost")
key: str = os.environ.get("SUPABASE_SERVICE_KEY", "placeholder")

supabase: Client = create_client(url, key)
