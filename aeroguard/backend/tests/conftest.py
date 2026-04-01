import sys
import os
from unittest.mock import MagicMock, patch

# Ensure backend root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Patch create_client before any router/db module is imported
# This prevents the Supabase SDK from validating the API key at import time
_mock_supabase = MagicMock()
_patcher = patch("supabase.create_client", return_value=_mock_supabase)
_patcher.start()

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-key")
os.environ.setdefault("ORS_API_KEY", "test-ors-key")
