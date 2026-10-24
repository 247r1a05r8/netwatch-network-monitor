# NetWatch Architecture

## Layers

1. **Frontend** (`templates/index.html`, `static/style.css`, `static/app.js`): dashboard in plain HTML/CSS/JavaScript. Charts are drawn on a canvas, so no CDN or internet library is needed. The page polls the API: status every 2 s, history and events every 4 s.
2. **Backend** (`app.py`): Flask routes that return JSON. They only read data stored by the engine, so slow checks cannot block them. Errors are returned as short JSON messages; stack traces stay in the server console.
3. **Monitoring engine** (`monitor.py`): `MonitoringEngine` runs in one background thread. It decides what to check and when, keeps bounded in-memory history (deque), generates events and computes alerts and the health status.
4. **Helpers** (`network_utils.py`): ping, TCP connect, DNS lookup, HTTP request, interface information (psutil), gateway detection and the calculations.
5. **Configuration** (`config.py`): timing, limits, defaults and input validation.

## Data flow

Engine thread -> helper functions -> OS network stack -> results stored in `engine.state` (protected by a lock) -> Flask reads a copy -> JSON -> browser draws cards and charts.

## Update intervals

| Check | Interval |
|---|---|
| Interface statistics and bandwidth | 2 s |
| Gateway ping (3 pings) | 4 s |
| Internet ping (3 pings) + HTTP request | 6 s |
| DNS resolution | 10 s |
| TCP services and URLs | 6 s |

## API

`GET /api/status`, `/api/network-info`, `/api/interfaces`, `/api/latency?window=1|5|15`, `/api/dns`, `/api/services`, `/api/http-check`, `/api/diagnostics`, `/api/events` (`DELETE` clears), `/api/config` (`GET`, `POST`).

## Health rules

- OFFLINE: no local IP, or internet unreachable and gateway unreachable/unavailable.
- DEGRADED: any failing test, latency above threshold, loss above threshold, service/URL down, or internet down while the gateway works.
- HEALTHY: none of the above.

## Memory limits

Events 100, ping history 200 samples, bandwidth history 450 samples, 10 services, 10 URLs.

## Security design

Binds to 127.0.0.1. No port scanning, no device discovery, no packet capture. Inputs validated: hostnames/IPs by pattern (no spaces or shell characters), ports 1-65535, URLs http/https only. The ping command is called with an argument list (no shell), so input cannot inject commands. The frontend inserts all text with `textContent`.
