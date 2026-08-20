from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import NotFound, ValidationFailed
from app.domains.channels.schemas import ChannelUpdate
from app.domains.channels.service import ChannelService


def test_update_empty_raises_validation() -> None:
    db = MagicMock()
    with pytest.raises(ValidationFailed):
        ChannelService.update_channel(db, "u1", "c1", ChannelUpdate())


def test_get_missing_raises_not_found() -> None:
    db = MagicMock()
    with patch("app.domains.channels.service.ChannelRepository") as Repo:
        Repo.return_value.get.return_value = None
        with pytest.raises(NotFound):
            ChannelService.delete_channel(db, "u1", "missing")


def test_test_channel_ok_message() -> None:
    db = MagicMock()
    channel = SimpleNamespace(id="c1", name="组群")
    with (
        patch("app.domains.channels.service.ChannelRepository") as Repo,
        patch(
            "app.domains.channels.service.notify_delivery.send_to_channel",
            return_value=(True, ""),
        ),
    ):
        Repo.return_value.get.return_value = channel
        out = ChannelService.test_channel(db, "u1", "c1")
    assert out.ok is True
    assert "成功" in out.message
