# Network operations dashboard

Both independent applications now use a navy navigation rail, light content canvas, blue accents, compact cards and a shared visual language. Each distribution carries its own frontend implementation; neither imports the other application.

## Navigation

Program 1: Dashboard / Interface Manager, Device Inventory, Connections, Operation Logs and Settings. The operations workspace keeps target selection next to interface controls and the result table. Add/edit opens a dialog; import/export stays on the inventory page. Same/per-device interface controls choose which values are submitted. Credentials remain in memory on the Connections page.

Program 2: Dashboard, Switch Inventory, VLAN Reference, Special Users, Manual Override, Recovery Preview, Restore & Snapshots, Operation Logs and Settings. Override edits are bound to the dashboard form. Recovery Preview shows the last prepared plan's original/proposed configuration and unified diff. Live device recovery remains unavailable, as before.

Both dashboards provide searchable, vendor-filtered, sortable, paginated multi-select inventory, bounded internal scrolling, durable task selection, progress, colored outcome badges, export/copy/clear log controls and a working Light/Dark toggle. Task execution stays in the existing process-owned backend; navigation and page refresh do not cancel it. SQLite schema, transport code, recovery engine, BAT files and localhost binding are unchanged.

## Desktop captures

All devices and addresses in these screenshots are synthetic (`SW1`, `LAB-*`, `192.0.2.0/24`).

| Application | 1366×768 | 1920×1080 |
|---|---|---|
| Interface Manager, light | [Screenshot](screenshots/program1-1366-light.png) | [Screenshot](screenshots/program1-1920-light.png) |
| Interface Manager, dark | [Screenshot](screenshots/program1-1366-dark.png) | [Screenshot](screenshots/program1-1920-dark.png) |
| Recovery Manager, light | [Screenshot](screenshots/program2-1366-light.png) | [Screenshot](screenshots/program2-1920-light.png) |
| Recovery Manager, dark | [Screenshot](screenshots/program2-1366-dark.png) | [Screenshot](screenshots/program2-1920-dark.png) |

Run `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium /workspace/.venvs/network-project/bin/python scripts/browser_smoke.py` in the prepared cloud environment to regenerate all eight screenshots from fresh temporary data. Other environments can install Playwright Chromium and omit the executable override.

The browser test checks real callbacks: inventory creation/import/search, interface shutdown/no-shutdown/check, per-device selection, recovery confirmation/diff, restore, task results after page reload, navigation and theme changes. At each viewport it asserts that primary actions are above the fold, the device picker is bounded and the document has no horizontal overflow. External browser requests are blocked and HTTP cross-origin access is rejected. Screenshots are captured from the actual running applications, not design mockups.
