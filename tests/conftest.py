"""Pytest fixtures shared across unit tests.

By default, override get_current_user so existing tests don't need
to mint JWT tokens. Tests that specifically validate auth behavior
(test_auth_login.py) should disable this override per-test.
"""

from __future__ import annotations

import pytest

from apps.api.auth_deps import get_current_user
from apps.api.main import app
from packages.shared.auth import TokenPayload


def _fake_user() -> TokenPayload:
    return TokenPayload(
        sub="test-user",
        email="test@egg.local",
        role="admin",
        exp=9999999999,
        iat=0,
    )


_AUTH_TEST_FILES = ("test_auth_login", "test_api_skeleton")


@pytest.fixture(autouse=True)
def _override_auth_for_tests(request):
    """Bypass auth for all tests except those that specifically test auth behavior."""
    nodeid = request.node.nodeid
    if any(name in nodeid for name in _AUTH_TEST_FILES):
        yield
        return

    app.dependency_overrides[get_current_user] = _fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
