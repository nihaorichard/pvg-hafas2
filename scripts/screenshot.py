#!/usr/bin/env python3

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

DASHBOARD_URL = "https://nihaorichard.github.io/pvg-hafas2/"


def log(*args):
    print(*args, file=sys.stderr)


def main():

    os.makedirs(DOCS_DIR, exist_ok=True)

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            viewport={
                "width": WIDTH,
                "height": HEIGHT
            },
            device_scale_factor=1
        )

        # IMPORTANT:
        # Disable Chromium cache completely.
        context.route(
            "**/*",
            lambda route: route.continue_()
        )

        page = context.new_page()

        # Disable cache through Chromium DevTools.
        client = context.new_cdp_session(page)
        client.send("Network.enable")
        client.send("Network.setCacheDisabled", {"cacheDisabled": True})

        # Unique URL so GitHub Pages itself isn't opened with
        # exactly the same URL every time.
        url = DASHBOARD_URL + "?_capture=" + str(int(time.time()))

        log("Opening LIVE dashboard:")
        log(url)

        try:

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            log("HTML loaded.")

            # Allow the dashboard JavaScript to start its data request.
            page.wait_for_timeout(3000)

            # Wait for the actual departure table.
            try:

                page.wait_for_selector(
                    "#dep-body tr",
                    state="attached",
                    timeout=30000
                )

                log("Departure rows found.")

            except Exception:

                log(
                    "WARNING: departure rows were not detected."
                )

            # Give the dashboard time to finish its live data update.
            page.wait_for_timeout(10000)

            # Force one final repaint.
            page.evaluate("window.dispatchEvent(new Event('resize'))")

            page.wait_for_timeout(1000)

            # Screenshot exactly the visible 1600x960 dashboard.
            page.screenshot(
                path=OUT_PATH,
                full_page=False
            )

            log("Screenshot written:")
            log(OUT_PATH)

        finally:

            context.close()
            browser.close()


if __name__ == "__main__":
    main()
