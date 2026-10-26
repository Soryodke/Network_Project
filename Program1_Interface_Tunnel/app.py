from desktop_ui import Shell, confirm, field, history_ui, inventory_ui, panel_title, run, settings_ui, tasks
from engine import ConsoleSession, Manager
from nicegui import ui

manager = Manager()


@ui.page("/")
def page():
    shell = Shell(
        "Interface & Tunnel Manager",
        "Interface operations",
        [
            ("Dashboard", "space_dashboard"),
            ("Interface Manager", "settings_ethernet"),
            ("Device Inventory", "dns"),
            ("Connections", "cable"),
            ("Operation Logs", "terminal"),
            ("Settings", "tune"),
        ],
    )
    with shell.view("Connections"):
        with ui.card().classes("panel"):
            panel_title("Connection settings", "cable", "Credentials stay in memory")
            with ui.element("div").classes("grid-fields"):
                username = field("Runtime username")
                password = ui.input("Runtime password", password=True).props("outlined dense")
                enable = ui.input("Runtime enable password", password=True).props("outlined dense")
                known_hosts = field("Approved known_hosts file path")
                ui.select(ConsoleSession.ports(), label="Detected console ports").props("outlined dense")
            live = ui.checkbox("LIVE LAB / APPROVED — Cisco SSH only", value=False)
            live.on_value_change(lambda e: shell.mode.set_text("LIVE LAB" if e.value else "SIMULATED"))
            ui.label(
                "Live console and jump are unavailable pending lab validation. Host keys must be enrolled by IT."
            ).classes("subtitle")
    with shell.view("Device Inventory"):
        with ui.card().classes("panel"):
            inventory_ui(manage=True)
    with shell.view("Settings"):
        settings_ui(shell)
    with shell.view("Operation Logs"):
        with ui.card().classes("panel"):
            history_ui(expanded=True)
    workspace = shell.view("Dashboard")
    shell.views["Interface Manager"] = workspace
    with workspace:
        with ui.element("div").classes("workspace"):
            with ui.card().classes("panel"):
                inventory = inventory_ui()
            with ui.element("div").classes("stack"):
                with ui.card().classes("panel"):
                    panel_title("Interface control", "settings_ethernet", "01 / Configure operation")
                    with ui.row().classes("w-full items-center no-wrap gap-3"):
                        mode = (
                            ui.select(
                                ["Direct SSH", "Direct Console", "Console → SSH Jump"],
                                value="Direct SSH",
                                label="Connection mode",
                            )
                            .props("outlined dense options-dense")
                            .classes("grow")
                        )
                        ui.button(
                            "Connection settings", icon="tune", on_click=lambda: shell.navigate("Connections")
                        ).props("flat dense")
                    with ui.row().classes("w-full items-center gap-3 no-wrap"):
                        selection = ui.toggle(
                            ["Same Interface", "Per-Device Interface"], value="Same Interface"
                        ).props("unelevated dense no-caps")
                        interface = field("Common interface", "Tunnel90")
                    per_device = (
                        ui.textarea(
                            "Per-device overrides: hostname=Interface;Interface (one line per device)"
                        )
                        .props("outlined dense rows=2")
                        .classes("w-full")
                    )
                    per_device.bind_visibility_from(
                        selection, "value", backward=lambda value: value == "Per-Device Interface"
                    )
                    ui.separator()
                    actions = ui.row().classes("w-full items-center gap-3")
                with ui.card().classes("panel"):
                    history_ui()

    shell.mode.text = "SIMULATED · Direct SSH"
    mode.on_value_change(
        lambda e: shell.mode.set_text(("LIVE LAB" if live.value else "SIMULATED") + " · " + e.value)
    )

    async def execute(action):
        try:
            targets = [dict(row) for row in inventory.selected]
            if not targets:
                raise ValueError("Select one or more devices")
            overrides = {}
            for line in (
                (per_device.value or "") if selection.value == "Per-Device Interface" else ""
            ).splitlines():
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

    with actions:
        for action, icon, color in [
            ("Check Status", "radar", "primary"),
            ("No Shutdown", "play_arrow", "positive"),
            ("Shutdown", "power_settings_new", "negative"),
        ]:
            ui.button(action, icon=icon, color=color, on_click=lambda _, value=action: execute(value)).props(
                "unelevated"
            )
        ui.space()
        ui.label("Automatic read-back").classes("subtitle")
    shell.navigate("Dashboard")


if __name__ in {"__main__", "__mp_main__"}:
    run("Interface & Tunnel Manager", 8080)
