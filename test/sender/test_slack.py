import unittest

import requests_mock

from flathunter.config import YamlConfig
from flathunter.notifiers import SenderSlack


class SenderSlackTest(unittest.TestCase):

    @requests_mock.Mocker()
    def test_send_message(self, m) -> None:
        sender = SenderSlack(YamlConfig({"slack": {
            "webhook_url": "http://hooks.slack.com/dummy_webhook_url"}}))

        m.post("http://hooks.slack.com/dummy_webhook_url")
        assert None is sender.notify("result"), "Expected message to be sent"
