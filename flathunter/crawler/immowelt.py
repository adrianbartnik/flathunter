import datetime
import hashlib
import re
import asyncio
import nodriver as uc

from flathunter.abstract_crawler import Crawler
from flathunter.logging import logger
from flathunter.webdriver_crawler import WebdriverCrawler


# Note: We likely can't inherit from the standard WebdriverCrawler
# if it's strictly synchronous. 
class Immowelt(WebdriverCrawler):
    """Implementation of Crawler interface for ImmoWelt using nodriver."""

    URL_PATTERN = re.compile(r"https://www\.immowelt\.de")

    def __init__(self, config) -> None:
        super().__init__(config)
        self.config = config
        self.browser = None

    async def get_expose_details(self, expose):
        """Loads additional details using the nodriver page object."""
        page = await self.get_page(expose["url"])
        
        # Default date
        date = datetime.datetime.now().strftime("%d.%m.%Y")
        
        # Look for the information container
        # nodriver.select returns the first match or None
        info_div = await page.select("app-estate-object-informations")
        if not info_div:
            return date

        equipment_div = await page.select("div.equipment.ng-star-inserted")
        if not equipment_div:
            return date

        # Find all <p> tags
        paragraphs = await equipment_div.select_all("p")
        for i, p in enumerate(paragraphs):
            text = p.text.strip()
            if text == "Bezug":
                # Get the next paragraph text
                if i + 1 < len(paragraphs):
                    raw_date = paragraphs[i+1].text.strip()
                    no_exact_date_given = re.match(
                        r".*sofort.*|.*Nach Vereinbarung.*",
                        raw_date,
                        re.MULTILINE | re.DOTALL | re.IGNORECASE,
                    )
                    if not no_exact_date_given:
                        date = raw_date
                break
        
        return date

    async def extract_data(self, page: uc.Tab):
        """Extracts all exposes directly from the nodriver Tab/Page."""
        entries = []

        # Wait for the main list to load
        core_list = await page.select('div[data-testid="serp-core-scrollablelistview-testid"]')
        if not core_list:
            return []

        # Find all advertisement cards
        advertisements = await core_list.select_all('div.css-79elbk')
        
        for adv in advertisements:
            try:
                # nodriver allows CSS selectors directly on the element
                title_el = await adv.select('div.css-1cbj9xw')
                title = title_el.text.strip() if title_el else ""

                price_el = await adv.select('div[data-testid="cardmfe-price-testid"]')
                price = price_el.text.strip() if price_el else ""

                # Key facts (Size, Rooms)
                facts_container = await adv.select('div[data-testid="cardmfe-keyfacts-testid"]')
                descriptions = []
                if facts_container:
                    # Get all direct children
                    children = await facts_container.select_all("div")
                    descriptions = [c.text for c in children]

                size = next((x for x in descriptions if "m²" in x), "")
                rooms = next((x for x in descriptions if "Zimmer" in x), "")

                # URL and ID
                anchor = await adv.select("a")
                if not anchor:
                    continue
                
                url = anchor.attributes.get("href")
                if url and "https" not in url:
                    url = "https://www.immowelt.de" + url
                
                # Image
                img_el = await adv.select("img")
                image = img_el.attributes.get("src") if img_el else None

                # Address
                addr_el = await adv.select('div[data-testid="cardmfe-description-box-address"]')
                address = addr_el.text.strip() if addr_el else ""

                # Process ID
                ad_id = url.split("/")[-1]
                processed_id = int(
                    hashlib.sha256(ad_id.encode("utf-8")).hexdigest(), 16
                ) % 10**16

                entries.append({
                    "id": processed_id,
                    "image": image,
                    "url": url,
                    "title": title,
                    "rooms": rooms,
                    "price": price,
                    "size": size,
                    "address": address,
                    "crawler": self.get_name(),
                })
            except Exception as e:
                logger.error(f"Error parsing advertisement: {e}")
                continue

        logger.debug("Number of entries found: %d", len(entries))
        return entries
