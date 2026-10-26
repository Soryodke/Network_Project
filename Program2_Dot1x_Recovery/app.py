import uuid

from desktop_ui import confirm, history_ui, inventory_ui, run, store, tasks
from engine import Mapping, Recovery
from nicegui import ui

recovery = Recovery(store)
mapping = Mapping()


@ui.page("/")
def page():
    ui.label("802.1X Recovery Manager — Internal IT").classes("text-3xl")
    ui.label(
        "SIMULATED ONLY. Live recovery is unavailable until firmware-specific adapters pass lab validation."
    )
    ui.label(
        "Tab refresh retains tasks and snapshots. Process restart discards simulated device state; restore then refuses unknown state."
    )
    inventory = inventory_ui()

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

    ui.upload(
        label="Import local Vlan_User.xlsx (not committed)", auto_upload=True, on_upload=workbook
    ).props("accept=.xlsx")
    ports = ui.input("Explicit access ports (comma separated)", value="Gi1/0/1")
    manual = ui.textarea("Manual per-device/per-port VLAN exceptions: hostname,interface,vlan (one per line)")
    ui.label(
        "Recovery mapping: manual per-interface > special-user VLAN 27 > exact reference. No switch-wide override."
    )

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

    ui.button("Preview recovery diff", on_click=prepare)
    snapshots = ui.select({}, label="Recovery snapshot / interface").classes("w-full")

    def refresh_snapshots():
        snapshots.options = {
            s["id"]: s["device"] + " " + s["port"] + " " + s["state"] for s in store.rows("snapshots")
        }
        snapshots.update()

    ui.timer(1, refresh_snapshots)

    async def restore():
        if snapshots.value and await confirm(
            "Restore original configuration from snapshot "
            + snapshots.value
            + "? Conflicting changes block restore."
        ):
            tasks.submit(
                "SIMULATED restore", [{"id": snapshots.value}], lambda item, _: recovery.restore(item["id"])
            )

    ui.button("Restore selected interface", on_click=restore)
    ui.button(
        "Export snapshots",
        on_click=lambda: ui.download(
            __import__("json").dumps(store.rows("snapshots"), indent=2).encode(), "snapshots.json"
        ),
    )
    history_ui()


if __name__ in {"__main__", "__mp_main__"}:
    run("802.1X Recovery Manager", 8081)
