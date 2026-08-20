from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import Forbidden, RateLimited, Unauthorized
from app.core.security import hash_password
from app.domains.auth.service import AuthService


def test_login_success_returns_token() -> None:
    db = MagicMock()
    user = SimpleNamespace(
        id="u1",
        username="demo",
        display_name="Demo",
        password_hash=hash_password("demo-pass"),
        is_active=True,
    )
    with (
        patch("app.domains.auth.service.login_guard.is_locked", return_value=False),
        patch("app.domains.auth.service.login_guard.reset") as reset,
        patch("app.domains.auth.service.UserRepository") as Repo,
        patch("app.domains.auth.service.create_access_token", return_value="tok"),
    ):
        Repo.return_value.get_by_username.return_value = user
        out = AuthService.login(db, username="demo", password="demo-pass", ip="1.1.1.1")
    assert out.access_token == "tok"
    assert out.user.username == "demo"
    reset.assert_called_once()


def test_login_locked_raises_rate_limited() -> None:
    db = MagicMock()
    with patch("app.domains.auth.service.login_guard.is_locked", return_value=True):
        with pytest.raises(RateLimited):
            AuthService.login(db, username="demo", password="x", ip=None)


def test_login_bad_password_raises_unauthorized() -> None:
    db = MagicMock()
    user = SimpleNamespace(
        id="u1",
        username="demo",
        display_name="Demo",
        password_hash=hash_password("demo-pass"),
        is_active=True,
    )
    with (
        patch("app.domains.auth.service.login_guard.is_locked", return_value=False),
        patch("app.domains.auth.service.login_guard.record_failure") as fail,
        patch("app.domains.auth.service.UserRepository") as Repo,
    ):
        Repo.return_value.get_by_username.return_value = user
        with pytest.raises(Unauthorized):
            AuthService.login(db, username="demo", password="wrong", ip="1.1.1.1")
    fail.assert_called_once()


def test_login_disabled_raises_forbidden() -> None:
    db = MagicMock()
    user = SimpleNamespace(
        id="u1",
        username="demo",
        display_name="Demo",
        password_hash=hash_password("demo-pass"),
        is_active=False,
    )
    with (
        patch("app.domains.auth.service.login_guard.is_locked", return_value=False),
        patch("app.domains.auth.service.UserRepository") as Repo,
    ):
        Repo.return_value.get_by_username.return_value = user
        with pytest.raises(Forbidden):
            AuthService.login(db, username="demo", password="demo-pass", ip=None)
