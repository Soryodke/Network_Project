import json
import uuid

from desktop_ui import (
    Shell,
    confirm,
    field,
    history_ui,
    inventory_ui,
    panel_title,
    run,
    settings_ui,
    store,
    tasks,
)
from engine import Mapping, Recovery
from nicegui import ui

recovery = Recovery(store)
mapping = Mapping()


@ui.page("/")
def page():
    shell = Shell(
        "802.1X Recovery • Internal IT",
        "Access recovery workspace",
        [
            ("Dashboard", "space_dashboard"),
            ("Switch Inventory", "dns"),
            ("VLAN Reference", "account_tree"),
            ("Special Users", "verified_user"),
            ("Manual Override", "edit_note"),
            ("Recovery Preview", "difference"),
            ("Restore & Snapshots", "restore"),
            ("Operation Logs", "terminal"),
            ("Settings", "tune"),
        ],
    )
    with shell.view("Switch Inventory"):
        with ui.card().classes("panel"):
            inventory_ui(manage=True)
    with shell.view("Settings"):
        settings_ui(shell)
    with shell.view("Operation Logs"):
        with ui.card().classes("panel"):
            history_ui(expanded=True)
    with shell.view("VLAN Reference"):
        with ui.card().classes("panel"):
            panel_title("VLAN reference mapping", "account_tree", "Local workbook import")
            upload_area = ui.column().classes("w-full")
            refs = (
                ui.table(
                    columns=[
                        {"name": k, "label": k.title(), "field": k, "sortable": True}
                        for k in ["switch", "vlan", "source"]
                    ],
                    rows=[],
                    pagination=8,
                )
                .props("dense flat")
                .classes("w-full")
            )
            field("Search VLAN mappings").bind_value_to(refs, "filter")
            ui.label(
                "Priority: manual interface override → special-user VLAN 27 → reference. Ambiguous mappings are refused."
            ).classes("subtitle")
    with shell.view("Special Users"):
        with ui.card().classes("panel"):
            panel_title("Special user assignment", "verified_user", "VLAN 27")
            special = (
                ui.table(
                    columns=[
                        {"name": k, "label": k.title(), "field": k, "sortable": True}
                        for k in ["switch", "interface", "vlan"]
                    ],
                    rows=[],
                    pagination=8,
                )
                .props("dense flat")
                .classes("w-full")
            )
            field("Search special users").bind_value_to(special, "filter")
            ui.button(
                "Import workbook", icon="upload_file", on_click=lambda: shell.navigate("VLAN Reference")
            )
    with shell.view("Restore & Snapshots"):
        with ui.card().classes("panel"):
            panel_title("Restore original configuration", "restore", "Integrity checked • conflict aware")
            snapshots = (
                ui.select({}, label="Recovery snapshot / interface")
                .props("outlined dense options-dense")
                .classes("w-full")
            )
            snapshot_table = (
                ui.table(
                    columns=[
                        {"name": k, "label": k.title(), "field": k, "sortable": True}
                        for k in ["device", "port", "state", "created"]
                    ],
                    rows=[],
                    pagination=8,
                )
                .props("dense flat")
                .classes("w-full")
            )
            restore_actions = ui.row().classes("gap-3")
            ui.label(
                "Process restart loses simulated device state; unknown current configurations block restore."
            ).classes("subtitle")
    workspace = shell.view("Dashboard")
    with workspace:
        with ui.element("div").classes("workspace"):
            with ui.card().classes("panel"):
                inventory = inventory_ui()
            with ui.element("div").classes("stack"):
                with ui.card().classes("panel"):
                    panel_title("Recovery plan", "health_and_safety", "01 / Resolve & review")
                    with ui.row().classes("w-full items-center no-wrap gap-3"):
                        ports = field("Explicit access ports (comma separated)", "Gi1/0/1")
                        ui.button(
                            "VLAN mappings",
                            icon="account_tree",
                            on_click=lambda: shell.navigate("VLAN Reference"),
                        ).props("flat dense")
                    manual = (
                        ui.textarea(
                            "Manual per-device/per-port VLAN exceptions: hostname,interface,vlan (one per line)"
                        )
                        .props("outlined dense rows=2")
                        .classes("w-full")
                    )
                    with ui.row().classes("items-center w-full justify-between"):
                        preview_actions = ui.row()
                        ui.badge("SIMULATION ONLY", color="blue-1", text_color="blue-8")
                    preview = (
                        ui.table(
                            columns=[
                                {"name": k, "label": k.title(), "field": k}
                                for k in ["device", "port", "vlan", "source"]
                            ],
                            rows=[],
                            pagination=3,
                        )
                        .props("dense flat")
                        .classes("w-full")
                    )
                with ui.card().classes("panel"):
                    history_ui()

    with shell.view("Manual Override"):
        with ui.card().classes("panel"):
            panel_title("Manual interface override", "edit_note", "Highest priority • individual ports only")
            ui.label(
                "Format: hostname,interface,vlan — one exception per line. Changes here update the recovery workspace."
            ).classes("subtitle")
            ui.textarea("Manual override entries").props("outlined dense rows=8").classes(
                "w-full"
            ).bind_value(manual, "value")
            ui.button(
                "Choose targets & preview", icon="arrow_forward", on_click=lambda: shell.navigate("Dashboard")
            )
    with shell.view("Recovery Preview"):
        with ui.card().classes("panel"):
            panel_title(
                "Before / after configuration", "difference", "Last prepared plan • no writes until confirmed"
            )
            plan_summary = ui.label(
                "Prepare a recovery plan from the Dashboard to inspect configuration here."
            ).classes("subtitle")
            with ui.element("div").classes("grid-fields"):
                with ui.column().classes("w-full"):
                    ui.label("ORIGINAL CONFIGURATION").classes("eyebrow")
                    before_code = (
                        ui.code("{}", language="json")
                        .classes("w-full")
                        .style("max-height:350px;overflow:auto")
                    )
                with ui.column().classes("w-full"):
                    ui.label("PROPOSED CONFIGURATION").classes("eyebrow")
                    after_code = (
                        ui.code("{}", language="json")
                        .classes("w-full")
                        .style("max-height:350px;overflow:auto")
                    )
            diff_code = (
                ui.code("No plan prepared.", language="diff")
                .classes("w-full")
                .style("max-height:240px;overflow:auto")
            )
            ui.button(
                "Configure recovery plan", icon="arrow_back", on_click=lambda: shell.navigate("Dashboard")
            ).props("outline")
    preview.set_visibility(False)

    async def workbook(event):
        global mapping
        try:
            candidate = Mapping.from_xlsx(await event.file.read())
            from engine import normalize

            for row in candidate.inventory:
                hostname = str(row.get("swname") or row.get("switchname") or "").strip()
                if not hostname:
                    raise ValueError("Sum_switch row requires SW Name")
            existing = {normalize(row["hostname"]): row for row in store.rows("inventory")}
            for row in candidate.inventory:
                hostname = str(row.get("swname") or row.get("switchname")).strip()
                old = existing.get(normalize(hostname), {})
                store.save_device(
                    dict(
                        id=old.get("id", ""),
                        hostname=hostname,
                        management_ip=str(row.get("ip") or row.get("managementip") or ""),
                        vendor=str(row.get("vendor") or "cisco"),
                        site=str(row.get("site") or ""),
                    )
                )
            mapping = candidate
            inventory.rows = store.rows("inventory")
            inventory.update()
            ui.notify(
                f"Imported {len(mapping.reference)} reference mappings and {len(mapping.special)} special ports"
            )
        except Exception as exc:
            ui.notify("Workbook rejected: " + str(exc), type="negative")

    with upload_area:
        ui.upload(label="Import local Vlan_User.xlsx", auto_upload=True, on_upload=workbook).props(
            "accept=.xlsx flat bordered"
        ).classes("w-full")

    async def prepare():
        try:
            if not inventory.selected:
                raise ValueError("Select switches")
            exceptions = {}
            from engine import normalize, port_name, vlan_id

            for line in (manual.value or "").splitlines():
                if line.strip():
                    name, port, value = [part.strip() for part in line.split(",")]
                    exceptions[(normalize(name), port_name(port))] = vlan_id(value)
            plans = []
            session = uuid.uuid4().hex
            for device in inventory.selected:
                for port in ports.value.split(","):
                    port = port.strip()
                    vlan, source = mapping.resolve(
                        device["hostname"],
                        port,
                        exceptions.get((normalize(device["hostname"]), port_name(port))),
                    )
                    recovery.seed(device["hostname"], port, device.get("vendor") or "cisco")
                    plans.append(recovery.plan(device["hostname"], port, vlan, source, session))
            preview.rows = [
                dict(device=p["device"], port=p["port"], vlan=p["recovery"]["data_vlan"], source=p["source"])
                for p in plans
            ]
            plan_summary.text = f"{len(plans)} interface(s) · " + ", ".join(
                p["device"] + " " + p["port"] for p in plans
            )
            before_code.content = json.dumps([p["original"] for p in plans], indent=2)
            after_code.content = json.dumps([p["recovery"] for p in plans], indent=2)
            diff_code.content = "\n\n".join(p["diff"] for p in plans)
            preview.set_visibility(True)
            preview.update()
            text = "\n\n".join(
                p["device"] + " " + p["port"] + " source=" + p["source"] + "\n" + p["diff"] for p in plans
            )
            if await confirm("Review SIMULATED recovery plan and preserved settings:\n" + text):
                tasks.submit(
                    "SIMULATED recovery",
                    [{"id": p["id"], "device": p["device"]} for p in plans],
                    lambda item, _: recovery.apply(item["id"]),
                )
                ui.notify("Recovery submitted")
        except Exception as exc:
            ui.notify(type(exc).__name__ + ": " + str(exc), type="negative")

    async def restore():
        if snapshots.value and await confirm(
            "Restore original configuration from snapshot "
            + snapshots.value
            + "? Conflicting changes block restore."
        ):
            tasks.submit(
                "SIMULATED restore", [{"id": snapshots.value}], lambda item, _: recovery.restore(item["id"])
            )

    with preview_actions:
        ui.button("Preview recovery diff", icon="difference", on_click=prepare).props("unelevated")
    with restore_actions:
        ui.button("Restore selected interface", icon="restore", on_click=restore)
        ui.button(
            "Export snapshots",
            icon="download",
            on_click=lambda: ui.download(
                json.dumps(store.rows("snapshots"), indent=2).encode(), "snapshots.json"
            ),
        ).props("outline")

    def refresh_data():
        rows = store.rows("snapshots")
        options = {r["id"]: r["device"] + " " + r["port"] + " " + r["state"] for r in rows}
        if snapshots.options != options:
            snapshots.options = options
            snapshots.update()
            snapshot_table.rows = rows
            snapshot_table.update()
        refs.rows = [
            dict(switch=k, vlan=v, source="Exact reference") for k, v in mapping.reference.items()
        ] + [dict(switch=p[0], vlan=p[3], source="Pattern") for p in mapping.patterns]
        refs.update()
        special.rows = [dict(switch=s, interface=p, vlan=27) for s, p in sorted(mapping.special)]
        special.update()

    ui.timer(1, refresh_data)
    shell.navigate("Dashboard")


if __name__ in {"__main__", "__mp_main__"}:
    run("802.1X Recovery Manager", 8081)
