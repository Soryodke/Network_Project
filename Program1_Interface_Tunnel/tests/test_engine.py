import threading

import pytest
from engine import Manager, SimulatedDevice, interface_name, parse_status
from local_runtime import Store, Tasks


@pytest.mark.parametrize(
    "admin,oper,expected",
    [
        ("up", "up", "UP"),
        ("down", "down", "DOWN"),
        ("administratively down", "down", "ADMIN DOWN"),
        ("up", "down", "UP/DOWN"),
    ],
)
def test_readback(admin, oper, expected):
    assert parse_status(f"Tunnel90 is {admin}, line protocol is {oper}", "Tunnel90") == expected


@pytest.mark.parametrize(
    "value", ["Tunnel90\nreload", "Tunnel90;reload", "foo", "GigabitEthernet0/0/0\rshutdown"]
)
def test_command_injection(value):
    with pytest.raises(ValueError):
        interface_name(value)


def test_unknown_not_found():
    assert parse_status("% Invalid input", "Tunnel90") == "NOT FOUND"
    assert parse_status("unexpected response", "Tunnel90") == "UNKNOWN"


def test_simulated_write_readback():
    manager = Manager()
    device = dict(id="a", hostname="BRANCH1", management_ip="192.0.2.1", wan_ip="198.51.100.1")
    assert manager.perform(device, "Tunnel90", "Shutdown")["status"] == "ADMIN DOWN"
    assert manager.perform(device, "Tunnel90", "Check Status")["status"] == "ADMIN DOWN"
    assert manager.perform(device, "Tunnel90", "No Shutdown")["status"] == "UP"
    assert manager.perform(device, "Tunnel500", "Shutdown")["status"] == "NOT FOUND"
    assert (
        manager.perform(device, "Tunnel90", "Check Status", "Console → SSH Jump")["target"] == "198.51.100.1"
    )


def test_identity_and_transport_failures():
    device = SimulatedDevice("A")
    with pytest.raises(ValueError):
        device.execute("B", "Tunnel90", "Shutdown")
    device.fail = "timeout"
    with pytest.raises(ConnectionError):
        device.execute("A", "Tunnel90", "Shutdown")


def test_live_console_refuses():
    with pytest.raises(NotImplementedError):
        Manager().perform(dict(id="a", hostname="A"), "Tunnel90", "Shutdown", "Direct Console", True)


def test_inventory_roundtrip(tmp_path):
    store = Store(tmp_path / "state.db")
    store.save_device(dict(hostname="A", management_ip="192.0.2.1"))
    other = Store(tmp_path / "other.db")
    other.import_inventory(store.export_inventory(True), True)
    assert other.rows("inventory")[0]["hostname"] == "A"
    with pytest.raises(ValueError):
        store.save_device(dict(hostname="A", password="do-not-store"))


def test_tasks_fail_skip_and_redaction(tmp_path):
    store = Store(tmp_path / "state.db")
    tasks = Tasks(store)

    def operation(item, key):
        if item["hostname"] == "bad":
            raise RuntimeError("secret-password")
        return dict(status="UP")

    key = tasks.submit("check", [dict(hostname="bad"), dict(hostname="good")], operation)
    tasks.pool.shutdown(wait=True)
    row = next(r for r in store.rows("tasks") if r["id"] == key)
    assert row["state"] == "failed"
    assert len(row["results"]) == 2
    assert "secret-password" not in str(row)


def test_cancel_queued_and_restart(tmp_path):
    store = Store(tmp_path / "state.db")
    tasks = Tasks(store)
    entered, release = threading.Event(), threading.Event()

    def operation(item, key):
        entered.set()
        assert release.wait(3)
        return dict(status="UP")

    key = tasks.submit("batch", [{}, {}], operation)
    assert entered.wait(3)
    tasks.cancel(key)
    release.set()
    tasks.close()
    assert store.rows("tasks")[0]["state"] == "cancelled"
    assert len(store.rows("tasks")[0]["results"]) == 1
    store.put("tasks", "interrupted", dict(id="interrupted", state="running"))
    restarted = Tasks(store)
    assert store.rows("tasks")[-1]["state"] == "interrupted"
    restarted.close()


def test_unknown_write_never_retried(monkeypatch):
    from engine import AmbiguousWriteError, SSHSession

    calls = []

    def interrupted(*args):
        calls.append(1)
        raise AmbiguousWriteError()

    monkeypatch.setattr(SSHSession, "execute", interrupted)
    row = Manager().perform(
        dict(id="a", hostname="A", management_ip="192.0.2.1"),
        "Tunnel90",
        "Shutdown",
        live=True,
        credentials=dict(username="x", password="not-persisted", known_hosts="unused"),
    )
    assert row["status"] == "UNKNOWN"
    assert row["action_result"] == "unverified"
    assert len(calls) == 1
    assert "not-persisted" not in str(row)


def test_ssh_strict_identity_readback_and_cleanup(monkeypatch):
    import netmiko
    import paramiko
    from engine import SSHSession

    options = []

    class Connection:
        def __init__(self):
            self.closed = False
            self.writes = []
            self.admin = "up"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.closed = True

        def find_prompt(self):
            return "BR1#"

        def enable(self):
            pass

        def send_command(self, command, **kwargs):
            assert command == "show interfaces Tunnel90"
            return f"Tunnel90 is {self.admin}, line protocol is down"

        def send_config_set(self, commands, **kwargs):
            self.writes.extend(commands)
            self.admin = "administratively down"
            return "accepted"

    conn = Connection()

    def connect(**kwargs):
        options.append(kwargs)
        return conn

    monkeypatch.setattr(netmiko, "ConnectHandler", connect)
    monkeypatch.setattr(paramiko, "HostKeys", lambda path: {"192.0.2.1": object()})
    session = SSHSession(
        dict(management_ip="192.0.2.1", vendor="cisco"), "runtime-user", "runtime-password", "approved"
    )
    assert session.execute("BR1", "Tunnel90", "Shutdown")[0] == "ADMIN DOWN"
    assert options[0]["ssh_strict"] is True
    assert options[0]["alt_key_file"] == "approved"
    assert conn.closed and conn.writes == ["interface Tunnel90", "shutdown"]
    conn.writes.clear()
    with pytest.raises(ValueError, match="identity"):
        session.execute("OTHER", "Tunnel90", "Shutdown")
    assert not conn.writes


def test_unenrolled_key_and_nonexistent_interface_do_not_write(monkeypatch):
    import netmiko
    import paramiko
    from engine import SSHSession

    session = SSHSession(dict(management_ip="192.0.2.1", vendor="cisco"), "user", "password", "approved")
    monkeypatch.setattr(paramiko, "HostKeys", lambda path: {})
    monkeypatch.setattr(netmiko, "ConnectHandler", lambda **kwargs: pytest.fail("must not connect"))
    with pytest.raises(ValueError, match="enrolled"):
        session.execute("BR1", "Tunnel90", "Shutdown")


def test_serial_ownership_and_cleanup(monkeypatch):
    import serial
    from engine import ConsoleSession

    class FakeSerial:
        closed = False

        def __init__(self, *args, **kwargs):
            pass

        def close(self):
            self.closed = True

    monkeypatch.setattr(serial, "Serial", FakeSerial)
    with ConsoleSession("FAKE") as owner:
        with pytest.raises(RuntimeError, match="owned"):
            with ConsoleSession("FAKE"):
                pytest.fail("duplicate serial owner")
    assert owner.connection.closed
    with ConsoleSession("FAKE"):
        pass


def test_jump_context_and_distinct_target_trust():
    from sessions import LostGatewayContext, SimulatedJump

    jump = SimulatedJump("GW")
    with pytest.raises(ValueError, match="trust"):
        with jump.target("BR1"):
            pass
    jump.enroll_simulated_target("BR1")
    with jump.target("BR1"):
        assert jump.prompt == "BR1#"
    assert jump.prompt == "GW#"
    with pytest.raises(LostGatewayContext):
        with jump.target("BR1"):
            jump.healthy = False
    with pytest.raises(LostGatewayContext):
        with jump.target("BR1"):
            pytest.fail("must stop on lost context")


def test_manager_jump_fatal_stops_batch(tmp_path):
    store = Store(tmp_path / "state.db")
    tasks = Tasks(store)
    manager = Manager()
    manager.jump.healthy = False
    devices = [dict(id="a", hostname="A"), dict(id="b", hostname="B")]
    tasks.submit(
        "jump",
        devices,
        lambda device, _: manager.perform(device, "Tunnel90", "Check Status", "Console → SSH Jump"),
    )
    tasks.pool.shutdown(wait=True)
    row = store.rows("tasks")[0]
    assert len(row["results"]) == 1
    assert row["results"][0]["fatal"] is True
    assert row["state"] == "failed"
