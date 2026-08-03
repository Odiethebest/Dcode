"""Keep the API test suite off the network.

`POST /repos` resolves the submitted hostname to check that it is not a private
address (F-06). Left alone, every test that submits a URL would perform a real
DNS lookup: the suite would need the network, run slower, and fail occasionally
for a reason unrelated to what it is testing.

This stubs the lookup to one public address by default. Tests that care about
resolution replace it themselves.
"""

from collections.abc import Iterator

import pytest
from dcode_api.routes import repos


@pytest.fixture(autouse=True)
def stub_host_resolution(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    async def public_address(_host: str) -> list[str]:
        return ["140.82.121.4"]

    monkeypatch.setattr(repos, "resolve_host", public_address)
    yield
