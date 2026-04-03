import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# Load .env relative to this file so it works regardless of cwd
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

url: str = os.environ.get("SUPABASE_URL", "http://localhost")
key: str = os.environ.get("SUPABASE_SERVICE_KEY", "placeholder")

supabase: Client = create_client(url, key)
