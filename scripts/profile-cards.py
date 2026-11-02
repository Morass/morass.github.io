"""Render the homepage's seven destinations as images for the GitHub profile README.

    python3.13 scripts/profile-cards.py ../morass-profile/cards

Captures the live https://morass.github.io/ in both site themes (the README picks one by
the viewer's GitHub colour scheme), so deploy site changes first. Needs Playwright and system Chrome.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE = "https://morass.github.io/"
NAMES = ["games", "prints", "small-games", "mobile", "youtube", "music", "tools"]
PAD = 8


def capture(page, out, theme):
    page.goto(SITE, wait_until="networkidle")
    page.evaluate("document.querySelectorAll('.header nav, .theme-toggle').forEach(e => e.style.visibility = 'hidden')")
    page.wait_for_timeout(1000)
    title = page.eval_on_selector(".home-crossroads .section-title", "e => e.getBoundingClientRect().bottom")
    page.screenshot(path=out / f"banner-{theme}.jpg", quality=90, clip={"x": 0, "y": 0, "width": 1280, "height": title + 24})
    boxes = page.eval_on_selector_all(".crossroads > .card, .home-tools", "els => els.map(e => e.getBoundingClientRect().toJSON())")
    assert len(boxes) == len(NAMES), f"homepage has {len(boxes)} destinations, expected {len(NAMES)}"
    for name, b in zip(NAMES, boxes):
        clip = {"x": b["x"] - PAD, "y": b["y"] - PAD, "width": b["width"] + 2 * PAD, "height": b["height"] + 2 * PAD}
        page.screenshot(path=out / f"{name}-{theme}.jpg", quality=88, clip=clip, full_page=True)


def main():
    out = Path(sys.argv[1]).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        for theme in ("dark", "light"):
            page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
            page.add_init_script(f"localStorage.setItem('morass-theme', '{theme}')")
            capture(page, out, theme)
            page.close()


if __name__ == "__main__":
    main()
