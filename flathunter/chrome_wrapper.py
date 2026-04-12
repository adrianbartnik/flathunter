"""Chrome browser wrapper using nodriver for anti-detection browsing.

nodriver communicates directly via Chrome DevTools Protocol (CDP),
eliminating the need for a separate chromedriver binary.
"""
import asyncio
import json
import re
import subprocess
import threading
import time
from sys import platform
from typing import Any

import nodriver as uc
from nodriver import cdp

from flathunter.exceptions import ChromeNotFound
from flathunter.logging import logger


def _patch_client_security_state():
    """Monkey-patch nodriver's ClientSecurityState.from_json to handle Chrome's
    renamed CDP field (privateNetworkRequestPolicy → localNetworkAccessRequestPolicy)."""
    cls = cdp.network.ClientSecurityState
    original_from_json = cls.from_json

    @classmethod  # type: ignore[misc]
    def patched_from_json(klass, json):
        policy_key = (
            "privateNetworkRequestPolicy"
            if "privateNetworkRequestPolicy" in json
            else "localNetworkAccessRequestPolicy"
        )
        json["privateNetworkRequestPolicy"] = json.get(
            policy_key, json.get("privateNetworkRequestPolicy"))
        return original_from_json.__func__(klass, json)

    cls.from_json = patched_from_json


_patch_client_security_state()

CHROME_VERSION_REGEXP = re.compile(r".* (\d+\.\d+\.\d+\.\d+)( .*)?")
WINDOWS_CHROME_REG_PATH = r"HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon"
WINDOWS_CHROME_REG_REGEXP = re.compile(r"\s*version\s*REG_SZ\s*(\d+)\..*")
CHROME_BINARY_NAMES = ["google-chrome", "chromium", "chrome", "chromium-browser",
                       "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]


def get_command_output(args) -> list[str]:
    """Run a command and return stdout."""
    try:
        with subprocess.Popen(args,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True) as process:
            if process.stdout is None:
                return []
            return process.stdout.readlines()
    except FileNotFoundError:
        return []


def get_chrome_version() -> int:
    """Determine the correct name for the chrome binary."""
    for binary_name in CHROME_BINARY_NAMES:
        try:
            version_output = get_command_output([binary_name, "--version"])
            if not version_output:
                continue
            match = CHROME_VERSION_REGEXP.match(version_output[0])
            if match is None:
                continue
            return int(match.group(1).split(".")[0])
        except FileNotFoundError:
            pass
    try:
        # on Windows, Chrome doesn't respond to --version, but we can find
        # the version in the registry
        output = get_command_output(
            ["reg", "query", WINDOWS_CHROME_REG_PATH, "/v", "version"],
        )
        version_matches = (WINDOWS_CHROME_REG_REGEXP.match(l) for l in output)
        version_matches = [m for m in version_matches if m is not None]
        if version_matches:
            return int(version_matches[0].group(1))
    except FileNotFoundError:
        pass
    raise ChromeNotFound


class NodriverBrowser:
    """Synchronous wrapper around nodriver's async browser API.

    Runs a persistent asyncio event loop in a background thread so that
    CDP messages (WebSocket keepalives, network events, etc.) are always
    processed. Public methods submit coroutines to that loop and block
    until the result is ready.
    """

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._browser: Any = None
        self._tab: Any = None
        self._network_responses: list[dict] = []
        self._user_agent: str | None = None
        self._blocked_urls: list[str] | None = None

    # ── event-loop management ──────────────────────────────────────

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_async(self, coro) -> Any:
        """Submit a coroutine to the event-loop thread and block for the result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=120)

    # ── browser lifecycle ──────────────────────────────────────────

    async def _init_browser(self, headless: bool, browser_args: list[str]) -> None:
        self._browser = await uc.start(
            headless=headless,
            browser_args=browser_args,
        )

    async def _configure_tab(self) -> None:
        """Apply CDP configurations and set up network capture on the current tab."""
        await self._tab.send(cdp.network.enable())
        if self._user_agent:
            await self._tab.send(
                cdp.network.set_user_agent_override(user_agent=self._user_agent))
        if self._blocked_urls:
            try:
                await self._tab.send(
                    cdp.network.set_blocked_ur_ls(urls=self._blocked_urls))
            except (AttributeError, Exception):
                logger.debug("Could not set blocked URLs via CDP")
        self._tab.add_handler(
            cdp.network.ResponseReceived, self._on_network_response)

    async def _on_network_response(self, event: cdp.network.ResponseReceived) -> None:
        self._network_responses.append({
            "request_id": str(event.request_id),
            "url": event.response.url,
            "mime_type": event.response.mime_type,
        })

    def start(self, *, headless: bool = True, browser_args: list[str] | None = None,
              user_agent: str | None = None, blocked_urls: list[str] | None = None) -> None:
        """Launch the browser."""
        self._user_agent = user_agent
        self._blocked_urls = blocked_urls
        self._run_async(self._init_browser(headless, browser_args or []))

    def quit(self) -> None:
        """Close the browser and clean up resources."""
        if self._browser:
            try:
                self._run_async(self._browser.stop())
            except Exception:
                pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop.close()

    # ── navigation ─────────────────────────────────────────────────

    def get(self, url: str) -> None:
        """Navigate to *url* (opens / reuses a tab)."""
        self._network_responses.clear()
        self._tab = self._run_async(self._browser.get(url))
        self._run_async(self._configure_tab())
        # Allow page to settle and network events to arrive
        self._run_async(asyncio.sleep(2))

    def refresh(self) -> None:
        """Reload the current page."""
        self._run_async(self._tab.reload())

    # ── page content ───────────────────────────────────────────────

    @property
    def page_source(self) -> str:
        """Return the current page's HTML."""
        return self._run_async(self._tab.get_content())

    @property
    def current_url(self) -> str:
        """Return the current page URL."""
        return self._tab.target.url

    # ── javascript ─────────────────────────────────────────────────

    def execute_script(self, script: str) -> Any:
        """Execute *script* in the page context and return the result."""
        return self._run_async(self._tab.evaluate(script))

    # ── network capture ────────────────────────────────────────────

    def get_json_responses(self) -> list[dict]:
        """Return captured network responses that have a JSON mime type.

        Each entry is a dict with keys: request_id, url, mime_type.
        """
        return [r for r in self._network_responses if "json" in r["mime_type"]]

    def get_response_body(self, request_id: str) -> str:
        """Fetch the response body for a captured network request by its ID."""
        result = self._run_async(self._tab.send(
            cdp.network.get_response_body(
                request_id=cdp.network.RequestId(request_id))))
        # PyCDP returns (body, base64_encoded) tuple
        if isinstance(result, tuple):
            return result[0]
        return result

    # ── cookies ────────────────────────────────────────────────────

    def get_cookie(self, name: str) -> dict | None:
        """Return a cookie dict or *None*."""
        result = self._run_async(self._tab.send(cdp.network.get_cookies()))
        cookies = result if isinstance(result, list) else result[0]
        for cookie in cookies:
            if cookie.name == name:
                return {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "secure": cookie.secure,
                    "httpOnly": cookie.http_only,
                }
        return None

    def delete_cookie(self, name: str) -> None:
        self._run_async(self._tab.send(cdp.network.delete_cookies(name=name)))

    def add_cookie(self, cookie: dict) -> None:
        self._run_async(self._tab.send(cdp.network.set_cookie(
            name=cookie["name"],
            value=cookie["value"],
            domain=cookie.get("domain", ""),
            path=cookie.get("path", "/"),
            secure=cookie.get("secure", False),
            http_only=cookie.get("httpOnly", False),
        )))

    # ── element queries ────────────────────────────────────────────

    def query_selector(self, css_selector: str):
        """Find the first element matching a CSS selector. Returns raw nodriver element or None."""
        try:
            return self._run_async(self._tab.select(css_selector))
        except Exception:
            return None

    def get_element_attribute(self, css_selector: str, attribute: str) -> str | None:
        """Find element by CSS selector and return the value of the given attribute."""
        elem = self.query_selector(css_selector)
        if elem and elem.attrs:
            return elem.attrs.get(attribute)
        return None

    # ── waiting helpers ────────────────────────────────────────────

    def wait_for_element(self, css_selector: str, timeout: int = 10) -> bool:
        """Poll until an element matching *css_selector* appears. Returns True if found."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.query_selector(css_selector) is not None:
                return True
            self._run_async(asyncio.sleep(0.5))
        return False

    def wait_for_text(self, text: str, timeout: int = 10) -> bool:
        """Poll until *text* appears on the page. Returns True if found."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                elem = self._run_async(self._tab.find(text))
                if elem is not None:
                    return True
            except Exception:
                pass
            self._run_async(asyncio.sleep(0.5))
        return False

    def wait_for_element_invisible(self, css_selector: str, timeout: int = 10) -> bool:
        """Poll until no element matches *css_selector*."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.query_selector(css_selector) is None:
                return True
            self._run_async(asyncio.sleep(0.5))
        return False

    # ── iframe interaction ─────────────────────────────────────────

    def click_in_frame(self, element_selector: str) -> None:
        """Click an element inside a child frame using CDP."""
        self._run_async(self._click_in_frame_impl(element_selector))

    async def _click_in_frame_impl(self, element_selector: str) -> None:
        frame_tree = await self._tab.send(cdp.page.get_frame_tree())
        for child in (frame_tree.child_frames or []):
            frame_id = getattr(child.frame, "id_", None) or child.frame.id
            try:
                ctx_id = await self._tab.send(
                    cdp.page.create_isolated_world(frame_id=frame_id))
                await self._tab.send(cdp.runtime.evaluate(
                    expression=f'document.querySelector("{element_selector}")?.click()',
                    context_id=ctx_id))
            except Exception:
                continue

    def wait_for_element_in_frame(self, element_selector: str, timeout: int = 120) -> bool:
        """Poll child frames until *element_selector* exists."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                if self._run_async(self._check_element_in_frames(element_selector)):
                    return True
            except Exception:
                pass
            self._run_async(asyncio.sleep(1))
        logger.warning("Timeout waiting for '%s' in frames", element_selector)
        return False

    async def _check_element_in_frames(self, selector: str) -> bool:
        frame_tree = await self._tab.send(cdp.page.get_frame_tree())
        for child in (frame_tree.child_frames or []):
            frame_id = getattr(child.frame, "id_", None) or child.frame.id
            try:
                ctx_id = await self._tab.send(
                    cdp.page.create_isolated_world(frame_id=frame_id))
                result = await self._tab.send(cdp.runtime.evaluate(
                    expression=f'!!document.querySelector("{selector}")',
                    context_id=ctx_id))
                # PyCDP returns (RemoteObject, ExceptionDetails | None)
                if isinstance(result, tuple):
                    return bool(result[0].value)  # type: ignore[union-attr]
                if hasattr(result, "value") and result.value:
                    return True
            except Exception:
                continue
        return False


def create_browser(driver_arguments) -> NodriverBrowser:
    """Configure and launch a Chrome browser via nodriver."""
    logger.info("Initializing Chrome browser via nodriver for crawler...")

    browser_args = []
    if driver_arguments is not None:
        for arg in driver_arguments:
            # nodriver manages the debugging port itself
            if arg.startswith("--remote-debugging-port"):
                continue
            browser_args.append(arg)

    user_agent = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                  "AppleWebKit/537.36 (KHTML, like Gecko)"
                  "Chrome/120.0.0.0 Safari/537.36")

    browser = NodriverBrowser()
    browser.start(
        headless=True,
        browser_args=browser_args,
        user_agent=user_agent,
        blocked_urls=["https://api.geetest.com/get.*"],
    )
    return browser
