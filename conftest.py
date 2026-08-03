"""Keep the test suite out of the developer's `.env`.

`SharedSettings` reads `.env` from the working directory, so every settings
singleton is built from whatever the developer happens to have configured. That
is right for running the services and wrong for running the tests: `make check`
should produce the same answer on every machine.

It is not hypothetical. Switching the auth gate on locally to test it made four
unrelated tests fail, because the suite picked up `AUTH_ENABLED=true` from the
file and the assertions were written against the default. The failures pointed
nowhere near the cause.

Environment variables take precedence over the `.env` file in pydantic-settings,
and pytest imports this module before any test module, so pinning them here wins
over the file. Only the settings whose defaults tests actually assert are pinned
— this is a targeted fix, not an attempt to sandbox the whole environment.
"""

import os

# Auth defaults off; tests that want the gate turn it on by patching the
# settings object directly, which is explicit and machine-independent.
os.environ.setdefault("_DCODE_TEST_ENV_PINNED", "1")
for name, value in (
    ("AUTH_ENABLED", "false"),
    ("DOCS_ENABLED", "true"),
):
    os.environ[name] = value
