import unittest
from unittest.mock import Mock

import pytest

from flathunter.config import YamlConfig
from flathunter.heartbeat import Heartbeat, HeartbeatException


class HeartbeatTest(unittest.TestCase):

    def test_invalid_interval_config(self) -> None:
        partial_config = YamlConfig()
        with pytest.raises(HeartbeatException):
            Heartbeat(partial_config, "1 hour")

    def test_heartbeat_without_notifiers(self) -> None:
        partial_config = YamlConfig()
        with pytest.raises(HeartbeatException):
            Heartbeat(partial_config, "hour")

    def test_heartbeat_off_interval_does_nothing(self) -> None:
        partial_config = YamlConfig({ "notifiers": [ "telegram" ]})
        heartbeat = Heartbeat(partial_config, "hour")
        heartbeat.send_heartbeat(5)

    def test_heartbeat_send(self) -> None:
        partial_config = YamlConfig({ "notifiers": [ "telegram" ]})
        heartbeat = Heartbeat(partial_config, "hour")
        notifier = Mock()
        heartbeat.notifier = notifier
        heartbeat.send_heartbeat(6)
        notifier.notify.assert_called_once()
