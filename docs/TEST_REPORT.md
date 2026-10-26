# Verification evidence

Executed on 2026-10-26 in Linux cloud with Python 3.12.14. No production or corporate device connections were made.

| Check | Outcome |
|---|---|
| Program 1: `python -m pytest -q` from its folder | 21 passed |
| Program 2: `python -m pytest -q` from its folder | 20 passed |
| Ruff check of both distributions and browser script | Passed |
| `pip check` | No broken requirements |
| Both NiceGUI servers: local HTTP GET | HTTP 200, expected application content |
| Chromium end-to-end inventory + simulated shutdown/readback + page reload | Passed |
| Chromium end-to-end simulated recovery + snapshot selection + restore | Passed |
| External browser origin HTTP request | Rejected with HTTP 403 by each application |
| Browser requests to external HTTP destinations | Blocked in smoke test; both workflows still passed |
| Repeat install script using pinned direct requirements | Passed, both unit suites executed |
| Repeat startup with temporary data | Passed after fixing POSIX TIME_WAIT handling in port probe |
| Git diff whitespace validation | Passed before commit |
| Windows BAT execution / Windows CI | Not run locally; workflow supplied |
| Physical SSH, serial, Cisco/Huawei lab tests | Not run; mocks/fixtures only |

Unit coverage includes status classification, command injection refusal, synthetic write/readback, identity and transport failure, strict known-host configuration, ambiguous write without retry, exclusive serial ownership/cleanup, simulated jump target trust and lost gateway context, queued cancellation, durable task reattachment/restart, exception-message redaction, inventory XLSX roundtrip, VLAN precedence and pattern floor/side ambiguity, checksum integrity, snapshot storage failure, port exclusions, preserved voice/QoS/STP, conflict-aware restore, unknown post-restart device state, and conservative offline Cisco/Huawei CLI parsing.

Resolved failures during development: test invocation needed each distribution's working directory; task-history display did not switch to a newly submitted restore task; smoke-test cleanup removed temporary data before stopping servers; POSIX startup probe rejected recently closed ports in TIME_WAIT. Relevant unit/browser checks were rerun successfully.

Supply-chain limitation: direct dependencies are version-pinned; full transitive lockfiles/hashes are not supplied. Package TLS verification remained enabled. Browser download was denied by environment policy, so the preinstalled `/usr/bin/chromium` was used without changing network policy for browser downloads.
