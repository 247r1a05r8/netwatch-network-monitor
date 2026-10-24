# NetWatch - Real-Time Network Monitoring & Troubleshooting System

A lightweight, local web dashboard that continuously checks the health of your network and helps answer the question *"Why is the internet slow?"*. Built with Python, Flask, psutil and plain HTML/CSS/JavaScript for a B.Tech Computer Networks mini project.

## Problem

College labs, hostels, small offices and homes often have no simple tool to tell *where* a network problem is. When a user says "internet is slow", the cause could be the local connection, the router (gateway), DNS, the internet link, high latency, packet loss, or one specific server. NetWatch shows these basic checks together in one dashboard, with a history of what happened and when.

## Features

All values come from the real operating system and network. If a value cannot be measured, the dashboard shows **Unavailable**. Nothing is random or simulated.

- Overall status: ONLINE / DEGRADED / OFFLINE (documented rules)
- Default gateway auto-detection (Windows `route print`/`ipconfig`, Linux `/proc` and `ip route`) with manual override
- Gateway ping with latency
- Internet check: ICMP ping plus a tiny HTTPS request
- DNS check: real name resolution with response time and resolved IP
- Live latency graph (current, average, min, max, packet loss) with 1, 5 and 15 minute windows
- Packet loss calculation from controlled pings (3 pings per cycle)
- Bandwidth: download/upload rate from interface byte counters
- Interface statistics via psutil, with interface selection
- TCP service monitoring and HTTP URL monitoring (only hosts you configure)
- Alerts generated from real results
- Event log (last 100 events) with Clear Logs
- Network Troubleshooter (6 safe tests with "possible cause" and suggestions)
- Network Information page and Configuration page with input validation
- Dark glassmorphism UI, responsive for mobile

## Architecture

```
Browser (HTML/CSS/JavaScript dashboard, polls every 2-5 s)
        |
Flask backend (app.py, JSON API)
        |
Monitoring engine (monitor.py, background thread)
        |
Network helpers (network_utils.py: ping, sockets, DNS, HTTP, psutil)
        |
Operating system network stack  ->  Gateway / Internet / Monitored services
```

Flask routes only read stored results, so a slow network test never blocks a web page.

## Installation (Windows)

1. Install Python 3.9 or newer from python.org (tick **Add Python to PATH**).
2. Open the project folder in File Explorer, or in Command Prompt:

```cmd
cd netwatch-network-monitor
install.bat
```

Manual alternative:

```cmd
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Execution

```cmd
run_app.bat
```

or manually:

```cmd
venv\Scripts\activate
python app.py
```

Open **http://127.0.0.1:5000**. Stop with `Ctrl+C`. The server listens on 127.0.0.1 only (this computer). To change the port: `set NETWATCH_PORT=5050` before running.

## Dashboard Usage

| Section | What it shows |
|---|---|
| Network Status (top right) | ONLINE, DEGRADED or OFFLINE from the health rules |
| Cards | Internet, Gateway, DNS, Packet Loss, Interface, Local IP, Download, Upload |
| Live Latency | Ping latency graph with current/average/min/max/loss; red dashed line = threshold |
| Network Health | Tick/cross for Latency, Packet Loss, Gateway, Internet, DNS, Services |
| Bandwidth / Packet Loss History | Recent download/upload and loss per ping cycle |
| Alerts | Problems active right now |
| Service / HTTP Monitoring | Your configured TCP ports and URLs |
| Interface Statistics | Bytes, packets, errors; dropdown selects the interface to monitor |
| Event Log | Changes such as "SERVICE DOWN", "Gateway reachable" (newest first) |
| Network Troubleshooter tab | Click **Run Network Diagnostics** |
| Network Information tab | Hostname, IPs, gateway, interfaces, MAC |
| Configuration tab | Gateway, DNS domain, thresholds, services, URLs |

### Health rules

- **HEALTHY**: gateway reachable (or not detectable), internet reachable, DNS working, packet loss and latency within thresholds, all configured services up.
- **DEGRADED**: any one test failing, latency or packet loss above threshold, or a service/URL down.
- **OFFLINE**: internet unreachable and gateway unreachable or unavailable, or no local IP address.

### Live demonstration

1. Run `run_app.bat`. Show **Internet ONLINE, Gateway REACHABLE, DNS AVAILABLE**.
2. Watch the latency graph update every few seconds.
3. Open a video or download a file and watch Download change.
4. In a second Command Prompt: `venv\Scripts\activate` then `python test_service.py` (starts a demo service on 127.0.0.1:5001).
5. Configuration > Services > **+ Add**: Name `Demo Service`, Host `127.0.0.1`, Port `5001` > **Save Settings**.
6. Press `Ctrl+C` in the demo window. Within about 6-12 seconds NetWatch shows **SERVICE DOWN** (alert + event log).
7. Run `python test_service.py` again: **SERVICE RESTORED**.

Note: some routers block ping. If the gateway shows UNREACHABLE while the internet works, that router may simply ignore ICMP.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Python was not found` | Reinstall Python and tick "Add Python to PATH", or use `py` |
| `No module named flask/psutil` | Run `install.bat` again, or `venv\Scripts\activate` then `pip install -r requirements.txt` |
| Port 5000 already in use | `set NETWATCH_PORT=5050` then run again |
| Gateway shows Unavailable | Set the gateway manually in Configuration |
| Gateway UNREACHABLE but internet works | Router may block ping; this is a known limitation |
| Everything OFFLINE on a campus network | The network may block ICMP/HTTPS to the test host. Change "Internet ping host" and "Internet check URL" in Configuration |
| Bandwidth shows Unavailable first | It needs two samples (about 2 seconds) |
| Wrong interface selected | Choose another in the Interface Statistics dropdown |

## Testing

```cmd
venv\Scripts\activate
python -m unittest discover -s tests -v
```

The tests cover local IP, interfaces, gateway parsing, ping parsing, DNS, TCP port checks, HTTP checks, bandwidth, packet loss, invalid input, timeouts and failure handling. They use only 127.0.0.1 and sockets created by the test itself. Manual test cases: `tests/test_cases.md`. Recorded results: `docs/test-results.md`.

## Limitations

- Checks basic connectivity only; it cannot find every fault or the exact root cause.
- ICMP may be blocked by some routers/firewalls; the gateway test can then show UNREACHABLE.
- Bandwidth is the traffic on this computer's interface, not the maximum line speed.
- Monitors this computer and configured hosts only; it does not discover other devices.
- Data is stored in memory and is lost when the app stops.
- Ping output parsing expects the standard English `ping` output format (loss is counted from reply lines with TTL).
- Single-user local tool: no login. Do not expose the port to untrusted networks.

## Future Scope

SNMP monitoring, multi-device monitoring, persistent history database, email/SMS alerts, role-based access, central monitoring server, Docker deployment, Prometheus/Grafana integration. These are **not** implemented.

## Safety

NetWatch is defensive. It does **not** sniff packets, scan ports, discover devices, capture credentials, spoof, or exploit anything. It only checks the local system, safe public endpoints and the hosts/ports you configure, one attempt per check.

## License

MIT (see LICENSE).
