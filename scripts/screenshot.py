#!/usr/bin/env python3

import http.server
import os
import socketserver
import sys
import threading
import time

from playwright.sync_api import sync_playwright


# ============================================================
# SETTINGS
# ============================================================

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "latest.png")

PORT = 8791

WIDTH = 1600
HEIGHT = 960


def log(*args):
    print(*args, file=sys.stderr)


# ============================================================
# LOCAL HTTP SERVER
# ============================================================

def start_server():

    os.chdir(DOCS_DIR)

    handler = http.server.SimpleHTTPRequestHandler

    httpd = socketserver.TCPServer(
        ("127.0.0.1", PORT),
        handler
    )

    thread = threading.Thread(
        target=httpd.serve_forever,
        daemon=True
    )

    thread.start()

    return httpd


# ============================================================
# MAIN
# ============================================================

def main():

    os.makedirs(DOCS_DIR, exist_ok=True)

    log("Starting local dashboard server...")
    log(f"Serving: {DOCS_DIR}")
    log(f"Port: {PORT}")

    httpd = start_server()

    time.sleep(1)

    try:

        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=True
            )

            # IMPORTANT:
            # GitHub Actions normally runs in UTC.
            # The timetable/dashboard uses German local time.
            context = browser.new_context(

                viewport={
                    "width": WIDTH,
                    "height": HEIGHT
                },

                device_scale_factor=1,

                # Germany / CEST / CET automatically
                timezone_id="Europe/Berlin"
            )

            page = context.new_page()

            # ------------------------------------------------
            # Disable browser cache
            # ------------------------------------------------

            client = context.new_cdp_session(page)

            client.send("Network.enable")

            client.send(
                "Network.setCacheDisabled",
                {
                    "cacheDisabled": True
                }
            )

            # ------------------------------------------------
            # Open LOCAL dashboard
            # ------------------------------------------------

            url = (
                f"http://127.0.0.1:{PORT}/index.html"
                f"?capture={int(time.time())}"
            )

            log("")
            log("Opening LOCAL dashboard:")
            log(url)

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            log("HTML loaded.")

            # ------------------------------------------------
            # Verify browser timezone
            # ------------------------------------------------

            browser_time = page.evaluate(
                "() => new Date().toString()"
            )

            browser_timezone = page.evaluate(
                "() => Intl.DateTimeFormat().resolvedOptions().timeZone"
            )

            log("")
            log("Browser time:")
            log(browser_time)

            log("Browser timezone:")
            log(browser_timezone)

            # ------------------------------------------------
            # Wait for dashboard data
            # ------------------------------------------------

            try:

                page.wait_for_selector(
                    "#dep-body tr",
                    state="attached",
                    timeout=30000
                )

                log("")
                log("Departure rows found.")

            except Exception:

                log("")
                log(
                    "WARNING: Departure rows were "
                    "not detected within 30 seconds."
                )

            # ------------------------------------------------
            # Give rendering a moment to finish
            # ------------------------------------------------

            page.wait_for_timeout(2000)

            # ------------------------------------------------
            # Read the actual displayed departures
            # ------------------------------------------------

            rows = page.locator("#dep-body tr")

            count = rows.count()

            log("")
            log(f"Departure rows: {count}")

            for i in range(min(count, 10)):

                try:

                    text = rows.nth(i).inner_text()

                    log(
                        f"ROW {i + 1}: "
                        + text.replace("\n", " | ")
                    )

                except Exception:
                    pass

            # ------------------------------------------------
            # Screenshot
            # ------------------------------------------------

            page.screenshot(
                path=OUT_PATH,
                full_page=False
            )

            log("")
            log("===================================")
            log("SCREENSHOT CREATED")
            log("===================================")
            log(f"File: {OUT_PATH}")
            log(f"Size: {WIDTH} x {HEIGHT}")
            log("===================================")

            context.close()
            browser.close()

    finally:

        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
