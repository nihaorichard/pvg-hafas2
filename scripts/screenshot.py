#!/usr/bin/env python3

"""
Takes a screenshot of the LIVE GitHub Pages dashboard
https://nihaorichard.github.io/pvg-hafas2/

The screenshot is rendered at exactly 1600x960 and saved as:

docs/latest.png

The live website is used instead of the local docs/index.html,
so the screenshot shows the same current departures that visitors
see on the GitHub Pages dashboard.
"""

import os
import sys
import time

from playwright.sync_api import sync_playwright


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "latest.png")

WIDTH = 1600
HEIGHT = 960

# LIVE GitHub Pages dashboard
DASHBOARD_URL = "https://nihaorichard.github.io/pvg-hafas2/"


def log(*args):
    print(*args, file=sys.stderr)


def main():

    os.makedirs(DOCS_DIR, exist_ok=True)

    # Cache-busting URL.
    # This prevents the browser from simply using an old cached page/data.
    cache_buster = int(time.time())
    url = f"{DASHBOARD_URL}?screenshot={cache_buster}"

    log("Opening LIVE dashboard:")
    log(url)

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": WIDTH,
                "height": HEIGHT
            },
            device_scale_factor=1
        )

        # Disable browser cache for this page.
        page.route(
            "**/*",
            lambda route: route.continue_()
        )

        try:

            # Open the actual live GitHub Pages website.
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000
            )

            log("Dashboard HTML loaded.")

            # Give the dashboard JavaScript time to fetch the
            # current departure data.
            page.wait_for_timeout(5000)

            # Wait for departure rows if the dashboard has them.
            try:
                page.wait_for_selector(
                    "#dep-body tr",
                    timeout=15000
                )

                log("Departure rows detected.")

            except Exception:

                log(
                    "WARNING: #dep-body tr was not found. "
                    "Continuing anyway."
                )

            # Extra time for the live dashboard to finish rendering.
            page.wait_for_timeout(3000)

            # Take the screenshot.
            page.screenshot(
                path=OUT_PATH,
                full_page=False
            )

            log(f"Screenshot saved to: {OUT_PATH}")

        finally:

            browser.close()


if __name__ == "__main__":
    main()
