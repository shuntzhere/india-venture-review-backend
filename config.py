# Loads Supabase credentials from the .env file and exposes them as constants.
# All modules that need database access import from here rather than reading
# environment variables directly.

import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
