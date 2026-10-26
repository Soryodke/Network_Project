"""Loopback-only local UI. Each distribution contains its own runtime and database."""

import atexit
import json
import os
import socket
from pathlib import Path
from urllib.parse import urlsplit

from local_runtime import Store, Tasks
from nicegui import app, ui


class LocalOriginGuard:
    """Reject cross-origin browser requests, WebSockets and DNS-rebinding hosts."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        headers = {key.lower(): value.decode("latin1") for key, value in scope["headers"]}
        host = headers.get(b"host", "")
        origin = headers.get(b"origin")
        allowed = urlsplit("http://" + host).hostname in {"127.0.0.1", "localhost"}
        if origin:
            parsed = urlsplit(origin)
            allowed = allowed and parsed.scheme == "http" and parsed.netloc == host
        if not allowed:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            else:
                await send({"type": "http.response.start", "status": 403, "headers": []})
                await send({"type": "http.response.body", "body": b"Local same-origin access required"})
            return
        return await self.app(scope, receive, send)


app.add_middleware(LocalOriginGuard)

BASE = Path(__file__).resolve().parent
store = Store(Path(os.environ.get("NETWORK_TOOLS_DATA", str(BASE / "data"))) / "state.sqlite3")
tasks = Tasks(store)
atexit.register(tasks.close)


CSS = """
:root {--canvas:#f3f6fb;--panel:#fff;--line:#e3e9f2;--ink:#17243b;--muted:#7a879b}
body {font-family:Inter,'Segoe UI',Arial,sans-serif;color:var(--ink);background:var(--canvas)}
body.body--dark {--canvas:#101827;--panel:#192438;--line:#2b3a52;--ink:#e5edf9;--muted:#9aabc4}
.q-page {background:var(--canvas)} .q-page-container {background:var(--canvas)}
.nicegui-content {padding:22px 26px;gap:16px;max-width:1800px;margin:auto}
.sidebar {gap:2px!important;background:#111e35!important;color:#96a8c4}.sidebar .q-drawer__content {padding:25px 16px}
.brand {color:#fff;font-size:19px;font-weight:750;letter-spacing:-.6px}.brand-icon{background:#3275f5;border-radius:11px;padding:9px;color:white}
.sidebar .nav-item.q-btn {width:100%;justify-content:flex-start;text-transform:none;font-size:13px;letter-spacing:.1px;padding:10px 12px;border-radius:9px;color:#9dadc7!important;margin:3px 0}
.sidebar .nav-item.q-btn.active {background:#243c63;color:#fff!important;box-shadow:inset 3px 0 #4b8aff}
.nav-item .q-btn__content{flex-wrap:nowrap!important}.nav-item .block{white-space:nowrap;font-size:12px}.nav-item .q-icon{font-size:20px;margin-right:11px}.section-caption{font-size:10px;letter-spacing:1.6px;color:#687f9f;font-weight:700;margin:26px 12px 10px}
.topbar{background:var(--panel)!important;color:var(--ink);border-bottom:1px solid var(--line);height:68px;box-shadow:none}
.topbar .q-toolbar{padding:0 26px}.page-title{font-size:23px;font-weight:720;letter-spacing:-.65px;line-height:1.3}
.subtitle{color:var(--muted);font-size:12px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:13px;box-shadow:0 3px 14px #14254104;padding:17px;width:100%;gap:12px}
.panel-title{font-size:14px;font-weight:700;letter-spacing:-.2px}.eyebrow{font-size:10px;letter-spacing:1px;font-weight:700;color:var(--muted)}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;width:100%}.stat{display:flex;flex-direction:row;align-items:center;justify-content:space-between;padding:15px 18px}
.stat-value{font-size:25px;font-weight:730;line-height:1.25}.stat-icon{padding:10px;border-radius:11px;background:#edf3ff;color:#3977eb}
.workspace{display:grid;grid-template-columns:340px minmax(0,1fr);gap:16px;width:100%;align-items:start}.stack{display:flex;flex-direction:column;gap:16px;min-width:0}
.q-field--outlined .q-field__control:before{border-color:var(--line)}.q-field--outlined .q-field__control{border-radius:8px}.q-field--dense .q-field__control{min-height:38px}.q-field__label{font-size:12px}
.q-btn{border-radius:7px;text-transform:none;letter-spacing:0;font-weight:600;font-size:12px}.q-table__container{background:transparent;box-shadow:none!important;border:0;border-radius:0;color:var(--ink)}
.q-table th{font-size:10px!important;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);font-weight:700;background:var(--canvas)}.q-table td{font-size:12px!important;height:39px!important;border-color:var(--line)!important}.q-table__middle{max-height:260px;overflow:auto}.q-table thead th{position:sticky;top:0;z-index:1}.q-table__bottom{min-height:38px;padding:0 5px;font-size:11px}.q-table__control .q-field{font-size:11px}
.picker .q-table__middle{height:240px}.picker .q-table__bottom .q-table__control:first-child{display:none}.q-badge{font-size:10px;font-weight:700;letter-spacing:.3px;padding:5px 8px;border-radius:5px}.q-separator{background:var(--line)}
.log-console{background:#111e35;color:#b6c9e7;border-radius:8px;max-height:180px;overflow:auto;font:11px/1.7 Consolas,monospace;padding:12px;white-space:pre-wrap;width:100%}.q-dialog__inner>.q-card{max-width:860px;width:90vw}.q-dialog .q-card{max-height:85vh;overflow:auto;background:var(--panel);color:var(--ink);padding:24px}
.grid-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;width:100%}.w-full{min-width:0}.q-tab{min-height:34px;font-size:12px}.q-tab__label{font-size:12px}.q-expansion-item__container>.q-item{min-height:36px;padding:0 4px;font-size:12px}
@media(min-width:1600px){.workspace{grid-template-columns:390px minmax(0,1fr)}.picker .q-table__middle{height:320px}}
@media(max-width:1050px){.nicegui-content{padding:16px}.workspace{grid-template-columns:290px minmax(0,1fr)}.grid-fields{grid-template-columns:1fr}.stats{gap:8px}.stat{padding:12px}}
@media(max-width:760px){.workspace{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}}
"""


def field(label, value=""):
    return ui.input(label, value=value).props("outlined dense").classes("w-full")


def panel_title(title, icon=None, caption=None):
    with ui.row().classes("items-center justify-between w-full no-wrap"):
        with ui.row().classes("items-center gap-2 no-wrap"):
            if icon:
                ui.icon(icon, size="18px").classes("text-blue-500")
            ui.label(title).classes("panel-title")
        if caption:
            ui.label(caption).classes("subtitle")


class Shell:
    def __init__(self, program, title, navigation):
        ui.add_css(CSS)
        ui.colors(primary="#3275f5", positive="#169c72", negative="#df5265", warning="#d79229")
        self.dark = ui.dark_mode()
        self.dashboard_title = title
        self.views = {}
        self.buttons = {}
        with (
            ui.left_drawer(value=True, fixed=True)
            .props("width=218 breakpoint=900")
            .classes("sidebar") as drawer
        ):
            with ui.row().classes("items-center gap-3 no-wrap"):
                ui.icon("hub", size="25px").classes("brand-icon")
                with ui.column().classes("gap-0"):
                    ui.label("NETOPS").classes("brand")
                    ui.label("AUTOMATION SUITE").style("font-size:8px;letter-spacing:1.7px;color:#7188aa")
            ui.label("WORKSPACE").classes("section-caption")
            for name, icon in navigation:
                self.buttons[name] = (
                    ui.button(name, icon=icon, color=None, on_click=lambda _, n=name: self.navigate(n))
                    .props("flat align=left")
                    .classes("nav-item")
                )
            ui.space()
            with (
                ui.column()
                .classes("gap-2")
                .style("border-top:1px solid #27354b;padding:18px 10px 0;width:100%")
            ):
                ui.badge("LOCAL WORKSPACE", color="blue-grey-9")
                ui.label(program).style("font-size:11px;color:#c1cde0")
                ui.label("127.0.0.1 • Isolated runtime").style("font-size:10px;color:#7188aa")
        with ui.header().classes("topbar"):
            with ui.row().classes("items-center justify-between w-full h-full no-wrap"):
                with ui.row().classes("items-center gap-3"):
                    ui.button(icon="menu", on_click=drawer.toggle).props("flat round dense").tooltip(
                        "Toggle navigation"
                    )
                    ui.label("Workspace").classes("subtitle")
                    ui.icon("chevron_right", size="16px").classes("text-slate-400")
                    self.crumb = ui.label("Dashboard").classes("text-sm font-semibold")
                with ui.row().classes("items-center gap-3"):
                    self.mode = ui.badge("SIMULATED", color="blue-1", text_color="blue-8")
                    self.task_badge = ui.badge("IDLE", color="grey-2", text_color="grey-7")
                    ui.button(icon="contrast", on_click=self.dark.toggle).props(
                        'flat round dense aria-label="Toggle theme"'
                    ).tooltip("Toggle dark / light mode").mark("theme-toggle")
        with ui.row().classes("items-end justify-between w-full"):
            with ui.column().classes("gap-1"):
                self.title = ui.label(title).classes("page-title")
                ui.label("Network operations, with every change accounted for.").classes("subtitle")
            ui.badge("●  LOCAL ONLY", color="green-1", text_color="green-8")
        self.stats = []
        with ui.element("div").classes("stats") as self.stats_area:
            for label, icon in [
                ("MANAGED DEVICES", "dns"),
                ("ACTIVE TASKS", "sync"),
                ("COMPLETED TASKS", "task_alt"),
                ("NEEDS ATTENTION", "report_gmailerrorred"),
            ]:
                with ui.card().classes("panel stat"):
                    with ui.column().classes("gap-1"):
                        ui.label(label).classes("eyebrow")
                        self.stats.append(ui.label("0").classes("stat-value"))
                    ui.icon(icon, size="23px").classes("stat-icon")

        def metrics():
            rows = store.rows("tasks")
            active = sum(r["state"] in {"queued", "running"} for r in rows)
            for item, value in zip(
                self.stats,
                [
                    len(store.rows("inventory")),
                    active,
                    sum(r["state"] == "completed" for r in rows),
                    sum(r["state"] in {"failed", "interrupted"} for r in rows),
                ],
            ):
                item.text = str(value)
            self.task_badge.text = "RUNNING" if active else "IDLE"

        metrics()
        ui.timer(1, metrics)

    def view(self, name):
        self.views[name] = ui.column().classes("w-full gap-4")
        return self.views[name]

    def navigate(self, name):
        self.title.text = self.dashboard_title if name == "Dashboard" else name
        self.stats_area.set_visibility(name == "Dashboard")
        for key, view in self.views.items():
            view.set_visibility(view is self.views.get(name))
        for key, button in self.buttons.items():
            button.classes(add="active" if key == name else "", remove="" if key == name else "active")
        self.crumb.text = name


def inventory_ui(manage=False):
    panel_title("Device inventory" if manage else "Select targets", "dns")
    with ui.row().classes("w-full items-center no-wrap gap-2"):
        search = field("Search devices")
        vendor = (
            ui.select(["All vendors", "cisco", "huawei"], value="All vendors")
            .props("outlined dense options-dense")
            .classes("w-32")
        )
    columns = [
        {"name": k, "label": label, "field": k, "sortable": True}
        for k, label in [("hostname", "Device"), ("management_ip", "Address"), ("vendor", "Platform")]
    ]
    if manage:
        columns += [
            {"name": k, "label": k.replace("_", " ").title(), "field": k, "sortable": True}
            for k in ["wan_ip", "model", "site", "notes"]
        ]
    table = (
        ui.table(
            columns=columns, rows=store.rows("inventory"), row_key="id", selection="multiple", pagination=6
        )
        .props("dense flat bordered")
        .classes("w-full" + ("" if manage else " picker"))
    )
    search.bind_value_to(table, "filter")
    cache = [None]

    def refresh(force=False):
        rows = store.rows("inventory")
        if vendor.value != "All vendors":
            rows = [r for r in rows if r.get("vendor", "").lower() == vendor.value]
        if rows != cache[0] or force:
            ids = {r["id"] for r in table.selected}
            table.rows = rows
            table.selected = [r for r in rows if r["id"] in ids]
            table.update()
            cache[0] = rows

    vendor.on_value_change(lambda _: refresh(True))
    ui.timer(1, refresh)
    with ui.dialog() as editor, ui.card():
        panel_title("Device details", "edit_note", "Local inventory • no credentials")
        fields = {}
        with ui.element("div").classes("grid-fields"):
            for name in ["hostname", "management_ip", "wan_ip", "vendor", "model", "site", "notes"]:
                fields[name] = field(name)
        selected = {}

        def save():
            try:
                store.save_device(
                    dict(id=selected.get("id", ""), **{k: v.value or "" for k, v in fields.items()})
                )
                refresh(True)
                editor.close()
                ui.notify("Device saved", type="positive")
            except ValueError as exc:
                ui.notify(str(exc), type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=editor.close).props("flat")
            ui.button("Save / Add", icon="check", on_click=save)

    def add():
        selected.clear()
        for control in fields.values():
            control.value = ""
        editor.open()

    def edit():
        if len(table.selected) != 1:
            ui.notify("Select one device to edit")
            return
        row = table.selected[0]
        selected["id"] = row["id"]
        for key, control in fields.items():
            control.value = row.get(key, "")
        editor.open()

    async def remove():
        if table.selected and await confirm(
            "Delete selected inventory: " + ", ".join(r["hostname"] for r in table.selected)
        ):
            for row in table.selected:
                store.delete_device(row["id"])
            table.selected = []
            refresh(True)

    async def upload(event):
        try:
            store.import_inventory(await event.file.read(), event.file.name.lower().endswith(".xlsx"))
            refresh(True)
            ui.notify("Inventory imported", type="positive")
        except Exception:
            ui.notify("Import rejected: verify inventory columns and format", type="negative")

    with ui.row().classes("w-full gap-2"):
        ui.button("Add device", icon="add", on_click=add).props("unelevated")
        ui.button("Edit", icon="edit", on_click=edit).props("flat dense")
        ui.button(icon="delete_outline", on_click=remove).props("flat dense color=negative").tooltip(
            "Delete selected"
        )
    if manage:
        with ui.row().classes("gap-2"):
            ui.button(
                "Export CSV",
                icon="download",
                on_click=lambda: ui.download(store.export_inventory(), "inventory.csv"),
            ).props("outline")
            ui.button(
                "Export XLSX",
                icon="download",
                on_click=lambda: ui.download(store.export_inventory(True), "inventory.xlsx"),
            ).props("outline")
            ui.button("Refresh inventory", icon="refresh", on_click=lambda: refresh(True)).props("flat")
        ui.upload(label="Import inventory CSV/XLSX", on_upload=upload, auto_upload=True).props(
            "accept=.csv,.xlsx flat bordered"
        ).classes("w-full")
    else:
        selected_label = ui.label("Select one or more devices to start an operation.").classes("subtitle")
        table.on("selection", lambda _: selected_label.set_text(f"{len(table.selected)} targets selected"))
    return table


async def confirm(message):
    with ui.dialog() as dialog, ui.card():
        panel_title("Review & confirm", "verified_user")
        ui.label(message).classes("whitespace-pre-wrap text-sm").style(
            "max-height:52vh;overflow:auto;width:100%;font-family:Consolas,monospace"
        )
        ui.label("Cancel stops queued work; it does not roll back commands already sent.").classes("subtitle")
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=lambda: dialog.submit(False)).props("flat")
            ui.button("Confirm", icon="check", on_click=lambda: dialog.submit(True))
    return await dialog


def history_ui(expanded=False):
    panel_title("Operation results", "receipt_long", "Durable task history")
    with ui.row().classes("w-full items-center no-wrap gap-3"):
        history = ui.select({}, label="Task ID").props("outlined dense options-dense").classes("grow")
        state = ui.badge("IDLE", color="grey")
        ui.button(icon="stop_circle", on_click=lambda: tasks.cancel(history.value)).props(
            "flat dense color=negative"
        ).tooltip("Cancel selected task")
        ui.button(
            icon="download",
            on_click=lambda: ui.download(json.dumps(store.rows("tasks"), indent=2).encode(), "history.json"),
        ).props("flat dense").tooltip("Export task history")
    progress = ui.linear_progress(0).props("rounded size=4px")
    table = (
        ui.table(
            columns=[
                {"name": k, "label": label, "field": k, "sortable": True}
                for k, label in [
                    ("target", "Device"),
                    ("interface", "Interface"),
                    ("action", "Action"),
                    ("status", "Status"),
                    ("timestamp", "Time"),
                ]
            ],
            rows=[],
            pagination=5,
        )
        .props("dense flat")
        .classes("w-full")
    )
    table.add_slot(
        "body-cell-status",
        r"""<q-td :props="props"><q-badge :color="({'UP':'green-1','RECOVERED':'green-1','RESTORED':'blue-1','DOWN':'red-1','ADMIN DOWN':'orange-1','UP/DOWN':'amber-1','FAILED':'red-1','UNKNOWN':'grey-3'})[props.value] || 'grey-2'" :text-color="({'UP':'green-9','RECOVERED':'green-9','RESTORED':'blue-9','DOWN':'red-9','ADMIN DOWN':'orange-9','UP/DOWN':'amber-9','FAILED':'red-9'})[props.value] || 'grey-8'">{{props.value}}</q-badge></q-td>""",
    )
    with ui.expansion("Live operation log", icon="terminal", value=expanded).classes("w-full"):
        logs = ui.label("No operations yet. Select targets to begin.").classes("log-console")
        with ui.row():
            ui.button("Copy log", icon="content_copy", on_click=lambda: ui.clipboard.write(logs.text)).props(
                "flat dense"
            )
            ui.button("Clear display", icon="clear_all", on_click=lambda: logs.set_text("")).props(
                "flat dense"
            )
    seen = set()
    cached = [None]

    def refresh():
        rows = store.rows("tasks")
        ids = {row["id"] for row in rows}
        select_latest = bool(ids - seen and rows)
        seen.update(ids)
        options = {r["id"]: r["created"][11:19] + " · " + r["label"] for r in rows}
        if history.options != options:
            history.options = options
            history.update()
        if select_latest:
            history.value = rows[-1]["id"]
        row = next((r for r in rows if r["id"] == history.value), None)
        if row and row != cached[0]:
            state.text = row["state"].upper()
            state.props(
                "color="
                + ("green" if row["state"] == "completed" else "red" if row["state"] == "failed" else "blue")
            )
            progress.value = len(row["results"]) / max(1, row["total"])
            table.rows = [
                dict(r, target=r.get("device", r.get("target", "")), timestamp=r.get("timestamp", "")[11:19])
                for r in row["results"]
            ]
            table.update()
            logs.text = json.dumps(row, indent=2)
            cached[0] = row

    refresh()
    ui.timer(0.5, refresh)


def settings_ui(shell):
    with ui.card().classes("panel"):
        panel_title("Workspace preferences", "tune")
        ui.switch("Dark mode").bind_value(shell.dark, "value")
        ui.label("Local data is stored independently in this application’s data/state.sqlite3.").classes(
            "subtitle"
        )
        ui.label("Browser refresh keeps backend tasks running. Stopping Python closes sessions.").classes(
            "subtitle"
        )
        ui.label("Servers bind only to 127.0.0.1. No production jobs start automatically.").classes(
            "subtitle"
        )


def run(title, default_port):
    port = int(os.environ.get("NETWORK_TOOLS_PORT", default_port))
    if not 1024 <= port <= 65535:
        raise SystemExit("Port must be between 1024 and 65535")
    with socket.socket() as probe:
        if os.name != "nt":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(
                f"Port {port} is in use. Close the previous application or configure NETWORK_TOOLS_PORT."
            )
    app.on_shutdown(tasks.close)
    ui.run(
        host="127.0.0.1",
        port=port,
        reload=False,
        show=os.environ.get("NETWORK_TOOLS_NO_BROWSER") != "1",
        title=title,
    )
