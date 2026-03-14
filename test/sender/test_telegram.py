import datetime
import json
import unittest

from requests_mock import Mocker

from flathunter.notifiers import SenderTelegram
from test.utils.config import StringConfig
from test.utils.request_matcher import RequestCounter


class SenderTelegramTest(unittest.TestCase):

    @Mocker()
    def test_send_message(self, m: Mocker) -> None:
        config = StringConfig(string=json.dumps({"telegram": {"bot_token": "dummy_token", "receiver_ids": [123]}}))
        sender = SenderTelegram(config=config)

        mock_response = """{
            "ok":true,
            "result":{
                "message_id":456,
                "from":{"id":1,"is_bot":true,"first_name":"Wohnbot","username":"wohnung_search_bot"},
                "chat":{"id":5,"first_name":"Arthur","last_name":"Taylor","type":"private"},
                "date":1589813130,
                "text":"hello arthur"
            }
        }"""
        m.post("https://api.telegram.org/botdummy_token/sendMessage", text=mock_response)
        assert sender.notify("result") is None, "Expected message to be sent"

    @Mocker()
    def test_send_no_message_if_no_receivers(self, m: Mocker) -> None:
        config = StringConfig(string=json.dumps({"telegram": {"bot_token": "dummy_token", "receiver_ids": None}}))
        sender = SenderTelegram(config=config)
        assert None is sender.notify("result"), "Expected no message to be sent"

    @Mocker()
    def test_send_message_with_image(self, m: Mocker) -> None:
        c = StringConfig(string=json.dumps(
            {"telegram": {"bot_token": "dummy_token", "receiver_ids": [1234567], "notify_with_images": "true"}},
        ))
        sender = SenderTelegram(config=c)

        dummy_expose = {
            "title": "dummy title for test",
            "images": ["https://example.com"],
        }

        mock_message_response = """{
            "ok":true,
            "result":{"message_id":456}
        }"""

        mock_media_group_response = """{
            "ok":true,
            "result":{"message_id":456}
        }"""  # the response has been cut to keep the source code clean

        m.post("https://api.telegram.org/botdummy_token/sendMessage", text=mock_message_response)
        m.post("https://api.telegram.org/botdummy_token/sendMediaGroup", text=mock_media_group_response)

        assert sender.process_expose(expose=dummy_expose) == dummy_expose

    @Mocker()
    def test_images_will_be_chunked(self, m: Mocker) -> None:
        c = StringConfig(string=json.dumps(
            {"telegram": {"bot_token": "dummy_token", "receiver_ids": [1234567], "notify_with_images": "true"}},
        ))

        sender = SenderTelegram(config=c)

        dummy_expose = {
            "title": "dummy title for test",
            "images": ["https://example.com" for _ in range(15)],
        }

        mock_message_response = """{
                "ok":true,
                "result":{"message_id":456}
            }"""

        mock_media_group_response = """{
                "ok":true,
                "result":{"message_id":456}
            }"""  # the response has been cut to keep the source code clean

        counter = RequestCounter()
        m.post("https://api.telegram.org/botdummy_token/sendMessage", text=mock_message_response)
        m.post("https://api.telegram.org/botdummy_token/sendMediaGroup",
               text=mock_media_group_response, additional_matcher=counter.count)

        exposed = sender.process_expose(expose=dummy_expose)

        assert counter.i == 2  # images is being sent in two messages.
        assert exposed == dummy_expose

    @Mocker()
    def test_stampede_protection(self, m: Mocker) -> None:
        c = StringConfig(string=json.dumps(
            {"telegram": {"bot_token": "dummy_token", "receiver_ids": [1234567]}},
        ))

        sender = SenderTelegram(config=c)
        mock_response = """{
            "description": "Warning: Too Many Requests",
            "parameters": {
                "retry_after": 2
            }
        }"""
        m.post("https://api.telegram.org/botdummy_token/sendMessage", text=mock_response, status_code=429)
        before = datetime.datetime.now()
        assert None is sender.notify("result"), "Expected no message to be sent"
        after = datetime.datetime.now()
        assert (after - before).seconds == 2
