import unittest

from flathunter.hunter import Hunter
from flathunter.idmaintainer import IdMaintainer
from flathunter.processor import ProcessorChain
from test.dummy_crawler import DummyCrawler
from test.test_util import count
from test.utils.config import StringConfig


class ProcessorTest(unittest.TestCase):

    DUMMY_CONFIG = """
urls:
  - https://www.example.com/liste/berlin/wohnungen/mieten?roomi=2&prima=1500&wflmi=70&sort=createdate%2Bdesc

google_maps_api:
  key: SOME_KEY
  url: https://maps.googleapis.com/maps/api/distancematrix/json?origins={origin}&destinations={dest}&mode={mode}&sensor=true&key={key}&arrival_time={arrival}
  enable: true
    """

    def test_addresses_are_processed_by_hunter(self) -> None:
        config = StringConfig(string=self.DUMMY_CONFIG)
        config.set_searchers([DummyCrawler(addresses_as_links=True)])
        hunter = Hunter(config, IdMaintainer(":memory:"))
        exposes = hunter.hunt_flats()
        assert count(exposes) > 4, "Expected to find exposes"
        for expose in exposes:
            assert not expose["address"].startswith("http"), "Expected addresses to be processed by default"

    def test_address_processor(self) -> None:
        crawler = DummyCrawler(addresses_as_links=True)
        config = StringConfig(string=self.DUMMY_CONFIG)
        config.set_searchers([crawler])
        exposes = crawler.get_results("https://www.example.com/search")
        for expose in exposes:
            assert expose["address"].startswith("http"), "Expected addresses not yet to be processed"
        chain = ProcessorChain.builder(config) \
            .resolve_addresses() \
            .build()
        exposes = chain.process(exposes)
        for expose in exposes:
            assert not expose["address"].startswith("http"), "Expected addresses to be processed"
