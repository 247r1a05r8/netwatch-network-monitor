# NetWatch Test Cases

Status values: **EXECUTED (sandbox)** means it was run in the Linux build environment, not on a Windows laptop. **NOT EXECUTED - USER MUST VERIFY LOCALLY** means you must run it on your own computer and record the result.

## A. Automated unit tests (`python -m unittest discover -s tests -v`)

| ID | Area | Test (file::name) | Sandbox status | Windows status |
|---|---|---|---|---|
| U1 | Local IP detection | test_network_utils::test_1*, 1b | EXECUTED (sandbox) - passed | NOT EXECUTED - USER MUST VERIFY LOCALLY |
| U2 | Interface detection | test_2, 2b, 2c | EXECUTED (sandbox) - passed | NOT EXECUTED - USER MUST VERIFY LOCALLY |
| U3 | Gateway detection | test_3 to 3d (parsing of Windows and Linux output) | EXECUTED (sandbox) - passed | NOT EXECUTED - USER MUST VERIFY LOCALLY |
| U4 | Ping handling | test_4 to 4e | EXECUTED (sandbox) - passed | NOT EXECUTED - USER MUST VERIFY LOCALLY |
| U5 | DNS resolution | test_5 to 5d | EXECUTED (sandbox) - passed | NOT EXECUTED - USER MUST VERIFY LOCALLY |
| U6 | Port checking | test_6, 6b | EXECUTED (sandbox) - passed | NOT EXECUTED - USER MUST VERIFY LOCALLY |
| U7 | HTTP checking | test_7 to 7d | EXECUTED (sandbox) - passed | NOT EXECUTED - USER MUST VERIFY LOCALLY |
| U8 | Bandwidth calculation | test_8 | EXECUTED (sandbox) - passed | NOT EXECUTED - USER MUST VERIFY LOCALLY |
| U9 | Packet loss calculation | test_9, 9b | EXECUTED (sandbox) - passed | NOT EXECUTED - USER MUST VERIFY LOCALLY |
| U10 | Invalid input | test_10 to 10c | EXECUTED (sandbox) - passed | NOT EXECUTED - USER MUST VERIFY LOCALLY |
| U11 | Timeout handling | test_11, 11b, test_5c | EXECUTED (sandbox) - passed | NOT EXECUTED - USER MUST VERIFY LOCALLY |
| U12 | Monitoring failure handling | test_monitor::EngineBehaviour | EXECUTED (sandbox) - passed | NOT EXECUTED - USER MUST VERIFY LOCALLY |

## B. Manual functional test cases

Fill the last column on your own computer.

| ID | Steps | Expected result | Your result |
|---|---|---|---|
| M1 | Run `install.bat` | Python found, venv created, Flask and psutil installed, "Installation finished" | To be captured during project execution. |
| M2 | Run `run_app.bat` | Console shows "NetWatch running at http://127.0.0.1:5000"; browser opens | To be captured during project execution. |
| M3 | Open the dashboard | Page loads with dark theme; CSS and JavaScript load | To be captured during project execution. |
| M4 | Check cards after 10 s | Internet, Gateway, DNS, Packet Loss, Interface, Local IP show real values | To be captured during project execution. |
| M5 | Compare Local IP with `ipconfig` | Same IPv4 address | To be captured during project execution. |
| M6 | Compare Gateway with `ipconfig` / `route print` | Same default gateway (or "Unavailable" with manual option) | To be captured during project execution. |
| M7 | Compare latency with `ping 1.1.1.1` in Command Prompt | Similar values | To be captured during project execution. |
| M8 | Watch the latency graph for 1 minute | New points appear every few seconds | To be captured during project execution. |
| M9 | Download a file or play a video | Download rate increases, then falls | To be captured during project execution. |
| M10 | Open Network Information tab | Hostname, OS, IP, gateway, interfaces, MAC shown | To be captured during project execution. |
| M11 | Troubleshooter > Run Network Diagnostics | Six steps with PASS/FAIL and overall result | To be captured during project execution. |
| M12 | Configuration: set DNS domain `bad domain!` | Save is rejected with a validation message | To be captured during project execution. |
| M13 | Configuration: add service 127.0.0.1:5001, no demo service running | Service shows DOWN, alert and event "SERVICE DOWN" | To be captured during project execution. |
| M14 | Run `python test_service.py` | Service becomes UP, event "SERVICE RESTORED" | To be captured during project execution. |
| M15 | Press Ctrl+C in the demo service window | Service shows DOWN again within about 12 s | To be captured during project execution. |
| M16 | Disconnect Wi-Fi/unplug Ethernet for 20 s | Status becomes OFFLINE (or DEGRADED), alerts and events appear | To be captured during project execution. |
| M17 | Reconnect | Status returns to ONLINE; events "restored" appear | To be captured during project execution. |
| M18 | Set DNS domain to `this-domain-does-not-exist.invalid` | DNS card shows FAILED; status DEGRADED | To be captured during project execution. |
| M19 | Set latency threshold to 1 ms | "High latency detected" alert appears | To be captured during project execution. |
| M20 | Click Clear Logs | Log shows only "Event log cleared" | To be captured during project execution. |
| M21 | Select another interface in the dropdown | Interface card and statistics change | To be captured during project execution. |
| M22 | Stop the app (Ctrl+C) with the page open | Banner "Cannot reach the NetWatch server" appears | To be captured during project execution. |
| M23 | Open the dashboard on a phone-width window | Layout stacks into one column | To be captured during project execution. |
