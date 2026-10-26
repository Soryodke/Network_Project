"""Cisco interface operations with explicit target identity and readback."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field

import paramiko
from sessions import LostGatewayContext, SimulatedJump

INTERFACE = re.compile(
    r"^(?:Tunnel|GigabitEthernet|TenGigabitEthernet|FastEthernet|Ethernet|Loopback|Port-channel)\d+(?:[/.:-]\d+)*$",
    re.I,
)


def interface_name(value):
    if not INTERFACE.fullmatch(value.strip()):
        raise ValueError("Unsupported or unsafe interface name")
    return value.strip()


def parse_status(output, interface):
    interface_name(interface)
    match = re.search(
        r"^" + re.escape(interface) + r" is (administratively down|up|down), line protocol is (up|down)",
        output,
        re.M | re.I,
    )
    if not match:
        return (
            "NOT FOUND" if re.search(r"Invalid input|does not exist|not found", output, re.I) else "UNKNOWN"
        )
    admin, oper = (v.lower() for v in match.groups())
    return (
        "ADMIN DOWN"
        if admin == "administratively down"
        else {"up/up": "UP", "down/down": "DOWN", "up/down": "UP/DOWN"}.get(admin + "/" + oper, "UNKNOWN")
    )


@dataclass
class SimulatedDevice:
    hostname: str
    interfaces: dict = field(default_factory=lambda: {"Tunnel90": "up", "GigabitEthernet0/0/0": "down"})
    fail: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock)

    def execute(self, expected, interface, action):
        with self.lock:
            if self.hostname.casefold() != expected.casefold():
                raise ValueError("Identity mismatch")
            if self.fail:
                raise ConnectionError("Simulated transport failure")
            if interface not in self.interfaces:
                return "NOT FOUND", "No change: interface does not exist"
            if action != "Check Status":
                self.interfaces[interface] = "administratively down" if action == "Shutdown" else "up"
            admin = self.interfaces[interface]
            output = f"{interface} is {admin}, line protocol is {'up' if admin == 'up' else 'down'}"
            return parse_status(output, interface), "SIMULATED readback verified"


class AmbiguousWriteError(RuntimeError):
    """A command may have reached the device; never automatically retry."""


class SSHSession:
    """Strict known-host enrollment. Credentials remain only in process memory.

    IOS interactive configuration via Netmiko; host-key checking is mandatory.
    Live use requires authorized lab validation of platform/firmware semantics.
    """

    def __init__(self, device, username, password, known_hosts, enable="", timeout=15):
        self.device = device
        self.username = username
        self.password = password
        self.known_hosts = known_hosts
        self.enable = enable
        self.timeout = timeout

    def execute(self, expected, interface, action):
        from netmiko import ConnectHandler

        if self.device.get("vendor", "").lower() not in {"cisco", "cisco_ios", "ios", "ios-xe"}:
            raise ValueError("Only Cisco IOS/IOS-XE is supported")
        # Verify the host has already been explicitly enrolled before Netmiko.
        keys = paramiko.HostKeys(self.known_hosts)
        host = self.device["management_ip"]
        if host not in keys:
            raise ValueError("SSH host key must be enrolled by an approved process")
        with ConnectHandler(
            device_type="cisco_ios",
            host=host,
            username=self.username,
            password=self.password,
            secret=self.enable,
            conn_timeout=self.timeout,
            auth_timeout=self.timeout,
            banner_timeout=self.timeout,
            ssh_strict=True,
            system_host_keys=False,
            alt_host_keys=True,
            alt_key_file=self.known_hosts,
            fast_cli=False,
        ) as conn:
            prompt = conn.find_prompt().strip()
            actual = re.sub(r"\([^)]*\)", "", prompt).rstrip("#>")
            if actual.casefold() != expected.casefold():
                raise ValueError("Device identity mismatch")
            conn.enable()
            initial = conn.send_command("show interfaces " + interface, read_timeout=self.timeout)
            initial_status = parse_status(initial, interface)
            if initial_status in {"NOT FOUND", "UNKNOWN"}:
                return initial_status, "No write sent: interface identity/status could not be verified"
            if action != "Check Status":
                try:
                    output = conn.send_config_set(
                        ["interface " + interface, "shutdown" if action == "Shutdown" else "no shutdown"],
                        read_timeout=self.timeout,
                    )
                    if re.search(r"%\s*(Invalid|Error|Incomplete|Ambiguous)", output, re.I):
                        return "FAILED", "Device rejected configuration command; inspect current state"
                    output = conn.send_command("show interfaces " + interface, read_timeout=self.timeout)
                except Exception as exc:
                    raise AmbiguousWriteError(
                        "Write/readback interrupted; inspect device before retry"
                    ) from exc
            else:
                output = initial
            return parse_status(
                output, interface
            ), "Readback completed; operational UP is distinct from command acceptance"


class ConsoleSession:
    """Exclusive serial ownership. Live console writes are withheld pending lab validation."""

    _locks = {}
    _guard = threading.Lock()

    @classmethod
    def ports(cls):
        from serial.tools.list_ports import comports

        return [port.device for port in comports()]

    def __init__(self, port, baud=9600):
        self.port, self.baud = port, baud
        with self._guard:
            self.lock = self._locks.setdefault(port, threading.Lock())

    def __enter__(self):
        import serial

        if not self.lock.acquire(blocking=False):
            raise RuntimeError("Console is already owned by another task")
        try:
            self.connection = serial.Serial(self.port, self.baud, timeout=1, write_timeout=3)
        except Exception:
            self.lock.release()
            raise
        return self

    def __exit__(self, *args):
        try:
            self.connection.close()
        finally:
            self.lock.release()


class Manager:
    def __init__(self):
        self.devices = {}
        self.lock = threading.Lock()
        self.console_lock = threading.Lock()
        self.device_locks = {}
        self.jump = SimulatedJump()

    def perform(self, device, interface, action, mode="Direct SSH", live=False, credentials=None):
        interface = interface_name(interface)
        if action not in {"Check Status", "Shutdown", "No Shutdown"}:
            raise ValueError("Unknown action")
        if mode not in {"Direct SSH", "Direct Console", "Console → SSH Jump"}:
            raise ValueError("Unknown connection mode")
        if live and mode != "Direct SSH":
            raise NotImplementedError(
                "Live console/jump is blocked pending firmware-specific prompt and trust validation"
            )
        result = dict(
            device=device["hostname"],
            target=device.get("wan_ip") if mode.endswith("Jump") else device.get("management_ip", ""),
            interface=interface,
            action=action,
            mode=mode,
        )

        def execute():
            if live:
                return SSHSession(device, **(credentials or {})).execute(
                    device["hostname"], interface, action
                )
            with self.lock:
                simulated = self.devices.setdefault(device["id"], SimulatedDevice(device["hostname"]))
            return simulated.execute(device["hostname"], interface, action)

        with self.lock:
            device_lock = self.device_locks.setdefault(device["id"], threading.Lock())
        try:
            with device_lock:
                if mode == "Direct SSH":
                    status, explanation = execute()
                else:
                    with self.console_lock:
                        if mode == "Console → SSH Jump":
                            self.jump.enroll_simulated_target(device["hostname"])
                            with self.jump.target(device["hostname"]):
                                status, explanation = execute()
                        else:
                            status, explanation = execute()
        except LostGatewayContext:
            result.update(
                status="UNKNOWN",
                fatal=True,
                action_result="unverified",
                explanation="SIMULATED gateway context lost; remaining jump targets stopped",
            )
            return result
        except AmbiguousWriteError:
            status, explanation = "UNKNOWN", "Connection lost after write; no automatic retry; inspect device"
        action_result = (
            "read only"
            if action == "Check Status"
            else (
                "verified"
                if (action == "Shutdown" and status == "ADMIN DOWN")
                or (action == "No Shutdown" and status in {"UP", "UP/DOWN", "DOWN"})
                else "unverified"
            )
        )
        result.update(status=status, action_result=action_result, explanation=explanation)
        return result
