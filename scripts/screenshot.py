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
            device_scale_factor=1,

            # THIS IS THE IMPORTANT FIX
            timezone_id="Europe/Berlin"
        )

        page = context.new_page()

        # Disable Chromium cache.
        client = context.new_cdp_session(page)

        client.send("Network.enable")
        client.send(
            "Network.setCacheDisabled",
            {"cacheDisabled": True}
        )

        # Cache-busting URL.
        url = (
            DASHBOARD_URL
            + "?_capture="
            + str(int(time.time()))
        )

        log("Opening LIVE dashboard:")
        log(url)

        try:

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            log("Dashboard loaded.")

            # Let dashboard JS fetch data.json.
            page.wait_for_timeout(3000)

            # Wait for departure table.
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

            # Final rendering delay.
            page.wait_for_timeout(2000)

            # Log the timezone/time so we can verify it.
            browser_time = page.evaluate(
                "() => new Date().toString()"
            )

            browser_timezone = page.evaluate(
                "() => Intl.DateTimeFormat().resolvedOptions().timeZone"
            )

            log("Browser time: " + browser_time)
            log("Browser timezone: " + browser_timezone)

            # Save exactly 1600x960.
            page.screenshot(
                path=OUT_PATH,
                full_page=False
            )

            log("Screenshot saved: " + OUT_PATH)

        finally:

            context.close()
            browser.close()


if __name__ == "__main__":
    main()
