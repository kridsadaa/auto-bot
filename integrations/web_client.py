"""
Playwright web automation
ต้องรัน: playwright install chromium
"""
from playwright.sync_api import sync_playwright, Page, Browser


class WebClient:
    def __init__(self, headless: bool = False):
        self._headless = headless
        self._playwright = None
        self._browser: Browser = None
        self._page: Page = None

    def start(self, browser_type: str = "chromium"):
        self._playwright = sync_playwright().start()
        browser_cls = getattr(self._playwright, browser_type)
        self._browser = browser_cls.launch(headless=self._headless)
        self._page = self._browser.new_page()

    def stop(self):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def goto(self, url: str):
        self._page.goto(url)

    def click(self, selector: str):
        self._page.click(selector)

    def fill(self, selector: str, value: str):
        self._page.fill(selector, value)

    def press_key(self, selector: str, key: str):
        self._page.press(selector, key)

    def screenshot(self, path: str):
        self._page.screenshot(path=path)

    def wait_for(self, selector: str, timeout: int = 10000):
        self._page.wait_for_selector(selector, timeout=timeout)

    def get_text(self, selector: str) -> str:
        return self._page.inner_text(selector)
