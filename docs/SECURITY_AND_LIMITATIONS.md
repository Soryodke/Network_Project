# Scope and hardware validation

Implemented and exercised: two standalone NiceGUI distributions, inventory CRUD/import/export, loopback servers, same-origin/Host guard, task IDs and durable history, cancellation of queued targets, process-restart interruption markers, simulated interface checks/writes/readback, recovery mapping precedence, durable checksummed snapshots, diff confirmation, conflict-aware exact restore, and conservative offline Cisco/Huawei config parsing.

Cisco Direct SSH uses strict enrolled host keys, expected prompt identity, bounded timeouts, context-managed cleanup, per-device locks, existing-interface checks before writes and explicit UNKNOWN after interrupted writes. It is implemented but not hardware validated. No corporate devices were contacted. Credentials exist only in process memory; transport exception messages are omitted from durable results.

Incomplete relative to the master specification:

- Real serial login/enable/paging and console-to-SSH jump prompt recovery, gateway selection and target host-key enrollment are NOT implemented. Serial port enumeration/exclusive ownership exists; simulated modes do not validate these protocols. Live console/jump is blocked.
- Live Cisco Catalyst and Huawei S5735/S5700 recovery/restore commands and version-certified templates are NOT implemented. Offline parsers and structured simulations do not prove actual CLI semantics. Live recovery is blocked.
- No bulk access-port discovery, reset-and-reapply workflow, or hardware-certified adapter matrix.
- Direct SSH target batches are sequential within each task; independent tasks use a bounded four-worker pool and serialize by inventory ID. Duplicate inventory entries pointing at the same physical device are not automatically coalesced.
- Workbook support uses a documented explicit schema and token patterns; undocumented proprietary spreadsheet layouts are refused. Mapping tables are in process memory and must be reimported after restarting. Inventory and snapshots persist.
- GUI is functional but has not met every requested UX detail: results are structured JSON rather than the full specified result grid; table columns are sortable, not freely resizable; simulated gateway trust/context state is modeled but does not validate real serial/SSH prompts.
- Windows launchers and Linux/Windows CI are supplied, but no Windows machine or physical console was available. Browser tests ran on Linux Chromium only.
- Authentication/command timeouts currently share one SSH timeout setting, with no UI controls for separate idle/keepalive tuning.
- Host/origin checks reduce browser-origin abuse. This is not an authentication boundary against other local users/processes. No remote multi-user deployment is supported.
- Persistent local data and exported snapshots are not encrypted. Protect them with OS account/file controls and organization backup policy. No raw runtime credentials should be entered in inventory notes.

Required lab work: Windows BAT behavior and shutdown, COM driver/baud and resource cleanup; Cisco IOS/IOS-XE model/firmware identity, enable rights, host-key mismatch and post-write disconnection; Cisco Catalyst dynamic RADIUS/MAB/dot1x plus voice VLAN; Huawei hybrid tagged/untagged/PVID and interface auth-profile behavior; concurrent operators, recovery conflict and lost-session cases. Use authorized lab targets only and explicitly record model/firmware.

No production-readiness or full-spec completion claim is made.
