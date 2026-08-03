"""Generate an ``AUTH_PASSWORD_HASH`` value.

    python -m dcode_api.hash_password

Prompts without echoing, confirms, and prints the line to paste. Reading the
password from an argument was rejected deliberately: it would put the
credential in shell history and in the process list.
"""

import getpass
import sys

from dcode_api.auth import hash_password


def main() -> int:
    password = getpass.getpass("Password: ")
    if not password:
        print("empty password refused", file=sys.stderr)
        return 1
    if password != getpass.getpass("Confirm:  "):
        print("passwords do not match", file=sys.stderr)
        return 1

    print()
    print("Add to .env.production (never to a committed file):")
    print()
    print(f"AUTH_PASSWORD_HASH={hash_password(password)}")
    print()
    print("And a session secret, at least 32 characters:")
    print()
    print("AUTH_SESSION_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
