"""Generate local-only random Airflow/DB secrets without printing them."""

import json
import os
import secrets
from pathlib import Path

root = Path("data/processed/airflow")
root.mkdir(parents=True, exist_ok=True)
for name, value in {
    "postgres_password": secrets.token_hex(32),
    "jwt_secret": secrets.token_hex(32),
    "passwords.json": json.dumps({"admin": secrets.token_urlsafe(32)}),
}.items():
    path = root / name
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(value)
print("Local secret files are ready; values were not printed.")
