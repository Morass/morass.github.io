"""Bounded reads in an owned tab of the existing logged-in Chrome."""
import contextlib
import json
import os
import time
import urllib.request
import uuid


def devtools(endpoint, route, method='GET'):
    request = urllib.request.Request(endpoint.rstrip('/') + route, method=method)
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


@contextlib.contextmanager
def open_page(endpoint=None):
    from playwright.sync_api import sync_playwright
    endpoint = endpoint or os.environ.get('STORE_LINKS_CDP', 'http://127.0.0.1:9222')
    with sync_playwright() as playwright:
        page = None
        target = None
        try:
            # A seed target avoids Chrome's zero-tab context-management failure.
            marker = 'about:blank?pages-links=' + uuid.uuid4().hex
            target = devtools(endpoint, '/json/new?' + marker, 'PUT')['id']
            browser = None
            for attempt in range(2):
                try:
                    browser = playwright.chromium.connect_over_cdp(endpoint, timeout=20_000)
                    break
                except Exception:
                    if attempt:
                        raise
                    time.sleep(1)
            page = next((p for c in browser.contexts for p in c.pages if p.url == marker), None)
            if page is None:
                raise RuntimeError('CDP did not expose the owned seed target')
            page.set_default_timeout(12_000)
            page.set_default_navigation_timeout(15_000)
            yield page
        finally:
            if page is not None:
                with contextlib.suppress(Exception):
                    page.close(run_before_unload=False)
            if target:
                with contextlib.suppress(Exception):
                    # /json/close returns text, not JSON.
                    with urllib.request.urlopen(endpoint.rstrip('/') + '/json/close/' + target, timeout=5):
                        pass


def goto(page, url):
    for attempt in range(2):
        try:
            response = page.goto(url, wait_until='domcontentloaded', timeout=15_000)
            if response is not None and response.status >= 400:
                raise RuntimeError(f'HTTP {response.status}: {url}')
            return
        except Exception:
            if attempt:
                raise
