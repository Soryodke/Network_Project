"""Start both distributions with fresh isolated data and exercise real browser actions.
Use PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium for an installed Chromium.
No device transport is invoked; all operations use synthetic inventory.
"""

import atexit
import os
import re
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


SCREENSHOTS = ROOT / "docs" / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE"), headless=True, args=["--no-sandbox"]
    )
    for port in (18080, 18081):
        program = "program1" if port == 18080 else "program2"
        page = browser.new_page(viewport={"width": 1366, "height": 768}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route(
            "**/*",
            lambda route: (
                route.continue_()
                if route.request.url.startswith(("http://127.0.0.1:", "ws://127.0.0.1:", "data:"))
                else route.abort()
            ),
        )
        page.goto(f"http://127.0.0.1:{port}/")
        page.get_by_role("button", name="Add device", exact=True).click()
        page.get_by_label("hostname", exact=True).fill("SW1")
        page.get_by_label("management_ip", exact=True).fill("192.0.2.1")
        page.get_by_label("vendor", exact=True).fill("cisco")
        page.get_by_role("button", name="Save / Add", exact=True).click()
        row = page.get_by_role("row").filter(has=page.get_by_role("cell", name="SW1", exact=True))
        expect(row).to_be_visible()
        row.get_by_role("checkbox").click()
        if port == 18080:
            page.get_by_role("button", name="Shutdown", exact=True).click()
            page.get_by_role("button", name="Confirm", exact=True).click()
            expect(page.get_by_role("status").filter(has_text=re.compile("^ADMIN DOWN$"))).to_be_visible(
                timeout=10000
            )
            page.reload()
            expect(page.get_by_role("status").filter(has_text=re.compile("^ADMIN DOWN$"))).to_be_visible(
                timeout=10000
            )
            row = page.get_by_role("row").filter(has=page.get_by_role("cell", name="SW1", exact=True))
            row.get_by_role("checkbox").click()
            page.get_by_role("button", name="No Shutdown", exact=True).click()
            page.get_by_role("button", name="Confirm", exact=True).click()
            expect(page.get_by_role("status").filter(has_text=re.compile("^UP$"))).to_be_visible(
                timeout=10000
            )
            page.get_by_role("button", name="Connections", exact=True).click()
            expect(page.get_by_label("Runtime password", exact=True)).to_be_visible()
            page.get_by_role("button", name="Interface Manager", exact=True).click()
            page.get_by_role("button", name="Per-Device Interface", exact=True).click()
            page.get_by_label("Per-device overrides:", exact=False).fill("SW1=Tunnel90")
            page.get_by_role("button", name="Check Status", exact=True).click()
            expect(page.get_by_role("status").filter(has_text=re.compile("^UP$"))).to_be_visible(
                timeout=10000
            )
            page.get_by_role("button", name="Same Interface", exact=True).click()
        else:
            page.get_by_label("Manual per-device/per-port VLAN exceptions:", exact=False).fill(
                "SW1,Gi1/0/1,30"
            )
            page.get_by_role("button", name="Preview recovery diff", exact=True).click()
            expect(page.get_by_role("dialog")).to_contain_text("data_vlan")
            page.get_by_role("button", name="Confirm", exact=True).click()
            expect(page.get_by_role("status").filter(has_text=re.compile("^RECOVERED$"))).to_be_visible(
                timeout=10000
            )
            page.get_by_role("button", name="Recovery Preview", exact=True).click()
            expect(page.locator("pre:visible").first).to_contain_text("voice_vlan")
            page.get_by_role("button", name="Manual Override", exact=True).click()
            expect(page.get_by_label("Manual override entries")).to_have_value("SW1,Gi1/0/1,30")
            page.get_by_role("button", name="Restore & Snapshots", exact=True).click()
            page.get_by_label("Recovery snapshot / interface").click()
            page.get_by_role("option").filter(has_text="recovered").click()
            page.get_by_role("button", name="Restore selected interface", exact=True).click()
            page.get_by_role("button", name="Confirm", exact=True).click()
            page.get_by_role("button", name="Dashboard", exact=True).click()
            expect(page.get_by_role("status").filter(has_text=re.compile("^RESTORED$"))).to_be_visible(
                timeout=10000
            )
            page.reload()
            expect(page.get_by_role("status").filter(has_text=re.compile("^RESTORED$"))).to_be_visible(
                timeout=10000
            )
        # Exercise the complete management surface using synthetic CSV only.
        inventory_nav = "Device Inventory" if port == 18080 else "Switch Inventory"
        page.get_by_role("button", name=inventory_nav, exact=True).click()
        # Explicit newline construction keeps uploaded file portable.
        csv = (
            "hostname,management_ip,vendor,site"
            + chr(10)
            + "".join(f"LAB-{i:02},192.0.2.{i},cisco,Simulation" + chr(10) for i in range(10, 18))
        )
        page.locator(".q-uploader:visible input[type=file]").set_input_files(
            {"name": "synthetic.csv", "mimeType": "text/csv", "buffer": csv.encode()}
        )
        expect(page.get_by_text("Inventory imported", exact=True)).to_be_visible()
        search = page.locator('input[aria-label="Search devices"]:visible')
        search.fill("LAB-10")
        expect(page.get_by_role("cell", name="LAB-10", exact=True)).to_be_visible()
        expect(page.get_by_role("cell", name="SW1", exact=True)).not_to_be_visible()
        search.fill("")
        page.get_by_role("button", name="Dashboard", exact=True).click()
        expect(page.get_by_text("Select targets", exact=True)).to_be_visible()
        page.locator('input[aria-label="Search devices"]:visible').fill("")
        expect(page.locator(".picker:visible tbody tr")).to_have_count(6)
        for index in (0, 1):
            checkbox = page.locator(".picker:visible tbody tr").nth(index).get_by_role("checkbox")
            if not checkbox.is_checked():
                checkbox.click()
        page.wait_for_function("document.querySelectorAll('.q-notification').length === 0", timeout=15000)
        for width, height in [(1366, 768), (1920, 1080)]:
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(700)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                "Horizontal overflow"
            )
            action = page.get_by_role(
                "button", name="Check Status" if port == 18080 else "Preview recovery diff", exact=True
            )
            box = action.bounding_box()
            assert box and box["y"] + box["height"] <= height, "Primary action below fold"
            table = page.locator(".picker .q-table__middle:visible")
            assert table.bounding_box()["height"] <= 330, "Unbounded picker"
            page.screenshot(path=str(SCREENSHOTS / f"{program}-{width}-light.png"), full_page=False)
            page.get_by_role("button", name="Toggle theme", exact=True).click()
            expect(page.locator("body")).to_have_class(re.compile(".*body--dark.*"))
            page.mouse.move(600, 100)
            page.wait_for_timeout(400)
            page.screenshot(path=str(SCREENSHOTS / f"{program}-{width}-dark.png"), full_page=False)
            page.get_by_role("button", name="Toggle theme", exact=True).click()
        page.get_by_role("button", name="Operation Logs", exact=True).click()
        expect(page.get_by_role("button", name="Copy log", exact=True)).to_be_visible()
        page.get_by_role("button", name="Settings", exact=True).click()
        expect(page.get_by_text("Dark mode", exact=True)).to_be_visible()
        assert not errors, errors
        print("PASS", program, "operations, refresh, navigation, import/search and 4 desktop screenshots")
        page.close()
    browser.close()
