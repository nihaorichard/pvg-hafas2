#!/usr/bin/env python3
"""
Renders docs/index.html in a headless browser at exactly 1600x960 and
saves the result as docs/latest.png.

Needs the dashboard to be reachable over http:// (not file://) because it
fetches data.json - so this script starts a throwaway local web server
first, points a headless Chromium at it, waits for the page's own JS to
finish rendering, then screenshots it.

Run with: python3 scripts/screenshot.py
Requires: pip install playwright && playwright install --with-deps chromium
"""
import http.server
import os
import socketserver
import sys
import threading
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "latest.png")
PORT = 8791
WIDTH = 1600
HEIGHT = 960


def log(*args):
    print(*args, file=sys.stderr)


def start_server():
    os.chdir(DOCS_DIR)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def main():
    log(f"Serving {DOCS_DIR} on port {PORT} ...")
    httpd = start_server()
    time.sleep(0.5)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
            url = f"http://127.0.0.1:{PORT}/index.html"
            log(f"Opening {url} ...")
            page.goto(url, wait_until="networkidle")

            try:
                page.wait_for_selector("#dep-body tr", timeout=8000)
            except Exception:
                log("WARNING: no departure rows appeared in time - screenshotting anyway.")

            page.wait_for_timeout(500)
            page.screenshot(path=OUT_PATH)
            browser.close()
    finally:
        httpd.shutdown()

    log(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
