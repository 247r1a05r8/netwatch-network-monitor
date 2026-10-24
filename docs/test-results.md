# NetWatch Test Results

This file records what was actually executed. Nothing here is estimated.

## 1. Executed in the build environment (not on the student's laptop)

| Item | Value |
|---|---|
| Environment | Linux container (build/execution sandbox), Python 3.10.12, Flask 3.1.3, psutil 7.2.2 |
| Date | 2 October 2026 |
| Network | The sandbox's own network. Every measured value (gateway, latency, DNS, bandwidth) belongs to that environment and **not** to any student's laptop or college network. |

### Automated tests

`python -m unittest discover -s tests -v` -> **Ran 56 tests, OK** (0 failures, 0 errors).

### Application checks executed in the sandbox

| Check | Result |
|---|---|
| Flask starts (`python app.py`) | Started and served requests |
| Dashboard `/`, `/static/style.css`, `/static/app.js` | HTTP 200 each |
| API: status, network-info, interfaces, latency, dns, services, http-check, events, config, diagnostics | HTTP 200 each, JSON |
| Unknown API path | JSON `{"error": "Not found"}`, HTTP 404, no stack trace |
| Invalid configuration (port 99999, host with spaces) | Rejected with HTTP 400 and a validation message |
| Local IP, interface, gateway detection | Returned real values from the sandbox (Linux `/proc/net/route` path) |
| Ping, DNS, HTTP, TCP checks | Real results: internet ping and DNS and HTTPS request succeeded |
| Gateway ping | The sandbox gateway did not answer ping, so NetWatch showed Gateway UNREACHABLE, raised the alert and showed overall DEGRADED while the internet was ONLINE. This is correct behaviour for that environment (a gateway that blocks ICMP). |
| Bandwidth calculation | Non-zero real values from sandbox interface counters |
| Service monitoring demo (127.0.0.1:5001) | DOWN (not running) -> UP (started) -> DOWN (stopped) -> UP (restarted), twice. Event log recorded "SERVICE DOWN" and "SERVICE RESTORED" for each change |
| Dashboard rendering | Rendered in headless Chrome and inspected visually (cards, graphs, health, alerts, events) |

## 2. NOT EXECUTED - USER MUST VERIFY LOCALLY

These were **not** run on Windows and must be verified on the student's computer:

- `install.bat` and `run_app.bat`
- Windows `ping` output parsing against a real Windows machine (parsing is unit-tested using sample Windows output only)
- Windows gateway detection with `route print`
- Wi-Fi / Ethernet interface names and selection on Windows
- Bandwidth values while using the real Wi-Fi connection
- Behaviour on the college network (ICMP may be blocked)
- Disconnect/reconnect demonstration (M16, M17)

Record your own results using `tests/test_cases.md` and `docs/screenshot-checklist.md`.

**To be captured during project execution.**
