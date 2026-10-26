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


def inventory_ui():
    ui.label("Device inventory — local only").classes("text-xl")
    selected = {}
    fields = {}
    with ui.row().classes("w-full flex-wrap"):
        for name in ["hostname", "management_ip", "wan_ip", "vendor", "model", "site", "notes"]:
            fields[name] = ui.input(name)
    table = ui.table(
        columns=[{"name": k, "label": k, "field": k, "sortable": True} for k in fields],
        rows=store.rows("inventory"),
        row_key="id",
        selection="multiple",
    ).classes("w-full")

    def refresh():
        table.rows = store.rows("inventory")
        table.update()

    def save():
        try:
            store.save_device(
                dict(id=selected.get("id", ""), **{k: v.value or "" for k, v in fields.items()})
            )
            selected.clear()
            for field in fields.values():
                field.value = ""
            refresh()
        except ValueError as exc:
            ui.notify(str(exc), type="negative")

    def edit():
        if len(table.selected) != 1:
            ui.notify("Select one device to edit")
            return
        selected["id"] = table.selected[0]["id"]
        for k, field in fields.items():
            field.value = table.selected[0].get(k, "")

    async def remove():
        names = ", ".join(row["hostname"] for row in table.selected)
        if not table.selected or not await confirm("Delete selected inventory: " + names):
            return
        for row in table.selected:
            store.delete_device(row["id"])
        table.selected = []
        refresh()

    async def upload(event):
        try:
            content = await event.file.read()
            store.import_inventory(content, event.file.name.lower().endswith(".xlsx"))
            refresh()
            ui.notify("Inventory imported")
        except Exception:
            ui.notify("Import rejected: verify inventory columns and file format", type="negative")

    with ui.row():
        ui.button("Save / Add", on_click=save)
        ui.button("Edit selected", on_click=edit)
        ui.button("Delete selected", on_click=remove)
        ui.button("Export CSV", on_click=lambda: ui.download(store.export_inventory(), "inventory.csv"))
        ui.button("Export XLSX", on_click=lambda: ui.download(store.export_inventory(True), "inventory.xlsx"))
        ui.button("Refresh inventory", on_click=refresh)
    ui.input("Search inventory").bind_value_to(table, "filter")
    ui.upload(label="Import inventory CSV/XLSX", on_upload=upload, auto_upload=True).props(
        "accept=.csv,.xlsx"
    )
    return table


async def confirm(message):
    with ui.dialog() as dialog, ui.card():
        ui.label(message).classes("whitespace-pre-wrap")
        ui.label("Cancel stops queued work only; it does not roll back commands already sent.")
        with ui.row():
            ui.button("Confirm", on_click=lambda: dialog.submit(True))
            ui.button("Cancel", on_click=lambda: dialog.submit(False))
    return await dialog


def history_ui():
    ui.label("Task history / reconnect").classes("text-xl")
    history = ui.select({}, label="Task ID").classes("w-full")
    state = ui.label()
    progress = ui.linear_progress(0)
    results = ui.code("[]", language="json").classes("w-full")

    seen_tasks = set()

    def refresh():
        rows = store.rows("tasks")
        identifiers = {row["id"] for row in rows}
        if identifiers - seen_tasks and rows:
            history.value = rows[-1]["id"]
        seen_tasks.update(identifiers)
        history.options = {
            row["id"]: row["created"] + " " + row["label"] + " " + row["state"] for row in rows
        }
        history.update()
        key = history.value
        if not key and rows:
            history.value = rows[-1]["id"]
            key = history.value
        row = next((r for r in rows if r["id"] == key), rows[-1] if rows else None)
        if row:
            state.text = f"{row['state']} — {len(row['results'])}/{row['total']} targets"
            progress.value = len(row["results"]) / max(row["total"], 1)
            results.content = json.dumps(row, indent=2)

    ui.timer(1, refresh)
    with ui.row():
        ui.button("Cancel selected task", on_click=lambda: tasks.cancel(history.value))
        ui.button(
            "Export redacted task history",
            on_click=lambda: ui.download(json.dumps(store.rows("tasks"), indent=2).encode(), "history.json"),
        )
        ui.button("Copy displayed log", on_click=lambda: ui.clipboard.write(results.content))
        ui.button("Clear displayed log", on_click=lambda: setattr(results, "content", "[]"))


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
