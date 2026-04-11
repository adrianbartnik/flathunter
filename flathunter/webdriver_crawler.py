import asyncio

import nodriver
from bs4 import BeautifulSoup
from nodriver.core.browser import Browser
from nodriver.core.tab import Tab

from flathunter.abstract_crawler import Crawler
from flathunter.exceptions import DriverLoadException


class WebdriverCrawler(Crawler):
    """Parent class of crawlers that use webdriver rather than `requests` to fetch pages."""

    def __init__(self, config) -> None:
        super().__init__(config)
        self.config = config
        self.driver = None

    def get_driver(self) -> Browser | None:
        """Lazy method to fetch the driver as required at runtime."""
        if self.driver is not None:
            return self.driver

        browser: Browser = asyncio.run(nodriver.start(headless=True))

        self.driver = browser
        return self.driver

    def get_driver_force(self) -> Browser:
        """Fetch the driver, and throw an exception if it is not configured or available."""
        res = self.get_driver()
        if res is None:
            msg = "Unable to load chrome driver when expected"
            raise DriverLoadException(msg)

        return res

    def get_page(self, search_url) -> Tab:
        return asyncio.run(self.get_driver_force().get(search_url))
