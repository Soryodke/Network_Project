from desktop_ui import confirm, history_ui, inventory_ui, run, tasks
from engine import ConsoleSession, Manager
from nicegui import ui

manager = Manager()


@ui.page("/")
def page():
    ui.label("Interface & Tunnel Manager").classes("text-3xl")
    ui.label("SIMULATED by default. Closing this tab keeps tasks running; stopping Python closes sessions.")
    inventory = inventory_ui()
    mode = ui.select(
        ["Direct SSH", "Direct Console", "Console → SSH Jump"], value="Direct SSH", label="Connection mode"
    )
    ui.select(ConsoleSession.ports(), label="Detected console ports (live console unavailable)")
    interface = ui.input("Common interface", value="Tunnel90")
    per_device = ui.textarea("Per-device overrides: hostname=Interface;Interface (one line per device)")
    live = ui.checkbox("LIVE LAB / APPROVED — Cisco SSH only", value=False)
    username = ui.input("Runtime username")
    password = ui.input("Runtime password", password=True)
    enable = ui.input("Runtime enable password", password=True)
    known_hosts = ui.input("Approved known_hosts file path")

    async def execute(action):
        try:
            targets = [dict(row) for row in inventory.selected]
            if not targets:
                raise ValueError("Select one or more devices")
            overrides = {}
            for line in (per_device.value or "").splitlines():
                if line.strip():
                    name, value = line.split("=", 1)
                    overrides[name.strip().casefold()] = value.strip().split(";")
            items = []
            from engine import interface_name

            for device in targets:
                for name in overrides.get(device["hostname"].casefold(), [interface.value]):
                    items.append(
                        dict(device=device, interface=interface_name(name), hostname=device["hostname"])
                    )
            is_live = live.value
            chosen_mode = mode.value
            credentials = dict(
                username=username.value,
                password=password.value,
                enable=enable.value,
                known_hosts=known_hosts.value,
            )
            if is_live and chosen_mode != "Direct SSH":
                raise ValueError("Live console/jump is unavailable pending lab validation")
            summary = "\n".join(item["hostname"] + ": " + item["interface"] for item in items)
            if (action != "Check Status" or is_live) and not await confirm(
                ("LIVE LAB" if is_live else "SIMULATED") + " " + action + "\n" + summary
            ):
                return
            key = tasks.submit(
                action,
                items,
                lambda item, task_id: manager.perform(
                    item["device"], item["interface"], action, chosen_mode, is_live, credentials
                ),
            )
            password.value = ""
            enable.value = ""
            ui.notify("Task started: " + key)
        except (ValueError, TypeError) as exc:
            ui.notify(str(exc), type="negative")

    with ui.row():
        for action in ["Check Status", "No Shutdown", "Shutdown"]:
            ui.button(action, on_click=lambda _, value=action: execute(value))
    history_ui()


if __name__ in {"__main__", "__mp_main__"}:
    run("Interface & Tunnel Manager", 8080)
