import sys, os
from pathlib import Path

# Load .env manually
for line in (Path(__file__).parents[1] / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

from supabase import create_client
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

user_id = "31ac09ed-f4f7-45a3-9eb4-16261f1a539e"
new_password = sys.argv[1] if len(sys.argv) > 1 else None

if not new_password:
    print("Usage: python scripts/set_password.py <new_password>")
    sys.exit(1)

result = sb.auth.admin.update_user_by_id(user_id, {"password": new_password})
print("Done:", result.user.email)
