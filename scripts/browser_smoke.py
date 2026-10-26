"""Start both distributions with fresh isolated data and exercise real browser actions.
Use PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium for an installed Chromium.
No device transport is invoked; all operations use synthetic inventory.
"""

import atexit
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
processes = []


def cleanup():
    for process in processes:
        process.terminate()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


data = tempfile.TemporaryDirectory()
atexit.register(data.cleanup)
atexit.register(cleanup)
for folder, port in [("Program1_Interface_Tunnel", 18080), ("Program2_Dot1x_Recovery", 18081)]:
    settings = dict(
        os.environ,
        NETWORK_TOOLS_NO_BROWSER="1",
        NETWORK_TOOLS_PORT=str(port),
        NETWORK_TOOLS_DATA=str(Path(data.name) / folder),
    )
    process = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT / folder, env=settings)
    processes.append(process)
    for attempt in range(100):
        if process.poll() is not None:
            raise RuntimeError("Application failed to start: " + folder)
        try:
            with urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                assert response.status == 200
            break
        except URLError:
            time.sleep(0.1)
    else:
        raise RuntimeError("Readiness timeout: " + folder)
    try:
        urlopen(Request(f"http://127.0.0.1:{port}/", headers={"Origin": "https://external.invalid"}))
        raise AssertionError("Cross-origin request was accepted")
    except HTTPError as exc:
        assert exc.code == 403

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE"), headless=True, args=["--no-sandbox"]
    )
    for port in [18080, 18081]:
        page = browser.new_page()
        errors = []
        page.route(
            "**/*",
            lambda route: (
                route.continue_()
                if route.request.url.startswith(("http://127.0.0.1:", "ws://127.0.0.1:", "data:"))
                else route.abort()
            ),
        )
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"http://127.0.0.1:{port}/")
        page.get_by_label("hostname", exact=True).fill("SW1")
        page.get_by_label("management_ip", exact=True).fill("192.0.2.1")
        page.get_by_label("vendor", exact=True).fill("cisco")
        page.get_by_role("button", name="Save / Add", exact=True).click()
        expect(page.get_by_role("cell", name="SW1", exact=True)).to_be_visible()
        page.get_by_role("row").filter(has=page.get_by_role("cell", name="SW1", exact=True)).get_by_role(
            "checkbox"
        ).click()
        if port == 18080:
            page.get_by_role("button", name="Shutdown", exact=True).click()
            page.get_by_role("button", name="Confirm", exact=True).click()
            expect(page.get_by_text("completed — 1/1 targets", exact=True)).to_be_visible(timeout=10000)
            expect(page.locator("pre")).to_contain_text("ADMIN DOWN")
            page.reload()
            expect(page.locator("pre")).to_contain_text("ADMIN DOWN", timeout=10000)
        else:
            page.get_by_label("Manual per-device/per-port VLAN exceptions:", exact=False).fill(
                "SW1,Gi1/0/1,30"
            )
            page.get_by_role("button", name="Preview recovery diff", exact=True).click()
            page.get_by_role("button", name="Confirm", exact=True).click()
            expect(page.locator("pre")).to_contain_text("RECOVERED", timeout=10000)
            page.get_by_label("Recovery snapshot / interface").click()
            page.get_by_role("option").filter(has_text="recovered").click()
            page.get_by_role("button", name="Restore selected interface", exact=True).click()
            page.get_by_role("button", name="Confirm", exact=True).click()
            expect(page.locator("pre")).to_contain_text("RESTORED", timeout=10000)
        assert not errors, errors
        print(f"PASS browser inventory and device action: {port}")
        page.close()
    browser.close()
