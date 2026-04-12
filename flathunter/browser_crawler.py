"""Parent class for crawlers that use a browser rather than `requests` to fetch pages."""

from bs4 import BeautifulSoup

from flathunter.abstract_crawler import Crawler
from flathunter.chrome_wrapper import NodriverBrowser, create_browser
from flathunter.exceptions import DriverLoadException


class BrowserCrawler(Crawler):
    """Parent class of crawlers that launch a Chrome browser to fetch pages."""

    def __init__(self, config) -> None:
        super().__init__(config)
        self.config = config
        self.driver = None

    def get_driver(self) -> NodriverBrowser | None:
        """Lazy method to fetch the driver as required at runtime."""
        if self.driver is not None:
            return self.driver
        driver_arguments = self.config.captcha_driver_arguments()
        self.driver = create_browser(driver_arguments)
        return self.driver

    def get_driver_force(self) -> NodriverBrowser:
        """Fetch the driver, and throw an exception if it is not configured or available."""
        res = self.get_driver()
        if res is None:
            msg = "Unable to load chrome driver when expected"
            raise DriverLoadException(msg)
        return res

    def get_page(self, search_url, driver=None, page_no=None) -> BeautifulSoup:
        """Applies a page number to a formatted search URL and fetches the exposes at that page."""
        return self.get_soup_from_url(search_url, driver=self.get_driver())
