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
#
# INTERNAL_API_KEY is pinned for a sharper reason. The API and the agent refuse
# to start on the placeholder the settings module defaults to, so on a machine
# with no `.env` — which is exactly what CI is — every test that boots a
# lifespan died with "INTERNAL_API_KEY is still the placeholder". Locally it
# passed, because a developer's `.env` supplies a real value. That asymmetry is
# the whole reason this file exists, and pinning two settings and not the third
# left it in place.
os.environ.setdefault("_DCODE_TEST_ENV_PINNED", "1")
for name, value in (
    ("AUTH_ENABLED", "false"),
    ("DOCS_ENABLED", "true"),
    ("INTERNAL_API_KEY", "test-internal-key-not-the-published-placeholder"),
):
    os.environ[name] = value
