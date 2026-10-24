"""NetWatch configuration.

Default settings live here. Values can be changed from the Configuration page
while the app runs (changes are kept in memory only) or edited here for a
permanent change. No private network information is hard coded: the gateway is
auto-detected and the monitored services start as an empty list.
"""
import os
import re
import ipaddress
from urllib.parse import urlparse

# ---- Server -----------------------------------------------------------------
HOST = os.environ.get("NETWATCH_HOST", "127.0.0.1")   # local only by default
PORT = int(os.environ.get("NETWATCH_PORT", "5000"))

# ---- Timing (seconds) -------------------------------------------------------
MONITOR_INTERVAL = 2          # engine tick; also the interface statistics interval
GATEWAY_INTERVAL = 4          # gateway ping
INTERNET_INTERVAL = 6         # internet ping + connectivity check
DNS_INTERVAL = 10             # DNS resolution test
SERVICE_INTERVAL = 6          # TCP service + HTTP URL checks

# ---- Ping -------------------------------------------------------------------
PING_COUNT = 3                # pings per cycle (kept small on purpose)
PING_TIMEOUT = 2              # seconds to wait for each reply
TCP_TIMEOUT = 2               # seconds for one TCP connect attempt
HTTP_TIMEOUT = 5              # seconds for one HTTP request
DNS_TIMEOUT = 4               # seconds to wait for a DNS answer

# ---- Memory limits ----------------------------------------------------------
MAX_EVENTS = 100              # last 100 events only
PING_HISTORY_SIZE = 200       # about 15 minutes at one sample per 6 s
BANDWIDTH_HISTORY_SIZE = 450  # about 15 minutes at one sample per 2 s
MAX_SERVICES = 10
MAX_URLS = 10

# ---- Defaults for the Configuration page -----------------------------------
DEFAULT_SETTINGS = {
    "gateway_mode": "auto",             # "auto" or "manual"
    "gateway_ip": "",                   # used when gateway_mode == "manual"
    "interface": "auto",                # "auto" or an interface name
    "dns_domain": "example.com",
    "internet_ping_host": "1.1.1.1",    # safe public endpoint for ICMP checks
    "internet_http_url": "https://example.com",
    "latency_threshold_ms": 200,
    "packet_loss_threshold_pct": 10,
    "services": [],                     # [{"name","host","port"}]
    "urls": [{"name": "Example", "url": "https://example.com"}],
}

_HOST_RE = re.compile(
    r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)"
    r"(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")


def is_valid_ip(value):
    try:
        ipaddress.ip_address(str(value).strip())
        return True
    except ValueError:
        return False


def is_valid_host(value):
    """True for a valid IP address or hostname. Rejects spaces and shell characters."""
    if not isinstance(value, str):
        return False
    value = value.strip()
    if not value or value.startswith("-"):
        return False
    return is_valid_ip(value) or bool(_HOST_RE.match(value))


def is_valid_url(value):
    if not isinstance(value, str) or len(value) > 300:
        return False
    try:
        p = urlparse(value.strip())
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.hostname) and is_valid_host(p.hostname)


def _clean_name(value, default):
    value = str(value or "").strip()[:40]
    return re.sub(r"[<>\"'`]", "", value) or default


def validate_settings(data, current=None):
    """Validate a settings dict. Returns (clean_settings, errors).

    Unknown keys are ignored. Missing keys keep their current value.
    """
    base = dict(DEFAULT_SETTINGS)
    if current:
        base.update(current)
    errors = []
    if not isinstance(data, dict):
        return base, ["Settings must be a JSON object."]
    out = dict(base)

    mode = data.get("gateway_mode", out["gateway_mode"])
    if mode not in ("auto", "manual"):
        errors.append("gateway_mode must be 'auto' or 'manual'.")
    else:
        out["gateway_mode"] = mode
    gip = str(data.get("gateway_ip", out["gateway_ip"])).strip()
    if out["gateway_mode"] == "manual":
        if not is_valid_ip(gip):
            errors.append("Manual gateway must be a valid IP address.")
        else:
            out["gateway_ip"] = gip
    elif gip == "" or is_valid_ip(gip):
        out["gateway_ip"] = gip
    else:
        errors.append("Gateway IP is not a valid IP address.")

    if "interface" in data:
        iface = str(data["interface"]).strip()
        if not iface or len(iface) > 100:
            errors.append("Interface name is invalid.")
        else:
            out["interface"] = iface

    if "dns_domain" in data:
        d = str(data["dns_domain"]).strip()
        if is_valid_host(d) and not is_valid_ip(d):
            out["dns_domain"] = d
        else:
            errors.append("DNS test domain must be a valid hostname such as example.com.")

    if "internet_ping_host" in data:
        h = str(data["internet_ping_host"]).strip()
        if is_valid_host(h):
            out["internet_ping_host"] = h
        else:
            errors.append("Internet ping host must be a valid IP or hostname.")

    if "internet_http_url" in data:
        u = str(data["internet_http_url"]).strip()
        if is_valid_url(u):
            out["internet_http_url"] = u
        else:
            errors.append("Internet check URL must start with http:// or https://.")

    for key, label, lo, hi in (
            ("latency_threshold_ms", "High latency threshold", 1, 10000),
            ("packet_loss_threshold_pct", "Packet loss threshold", 0, 100)):
        if key in data:
            try:
                num = float(data[key])
                if not (lo <= num <= hi):
                    raise ValueError
                out[key] = int(num) if num == int(num) else num
            except (TypeError, ValueError):
                errors.append("%s must be a number between %s and %s." % (label, lo, hi))

    if "services" in data:
        svc_in = data["services"]
        svc_out = []
        if not isinstance(svc_in, list) or len(svc_in) > MAX_SERVICES:
            errors.append("Services must be a list of at most %d entries." % MAX_SERVICES)
        else:
            for i, s in enumerate(svc_in, 1):
                if not isinstance(s, dict):
                    errors.append("Service %d is invalid." % i)
                    continue
                host = str(s.get("host", "")).strip()
                try:
                    port = int(s.get("port"))
                    if not (1 <= port <= 65535):
                        raise ValueError
                except (TypeError, ValueError):
                    errors.append("Service %d: port must be 1-65535." % i)
                    continue
                if not is_valid_host(host):
                    errors.append("Service %d: host is not a valid IP or hostname." % i)
                    continue
                svc_out.append({"name": _clean_name(s.get("name"), "Service %d" % i),
                                "host": host, "port": port})
            out["services"] = svc_out

    if "urls" in data:
        url_in = data["urls"]
        url_out = []
        if not isinstance(url_in, list) or len(url_in) > MAX_URLS:
            errors.append("URLs must be a list of at most %d entries." % MAX_URLS)
        else:
            for i, u in enumerate(url_in, 1):
                if not isinstance(u, dict) or not is_valid_url(str(u.get("url", "")).strip()):
                    errors.append("URL %d must start with http:// or https:// and have a valid host." % i)
                    continue
                url_out.append({"name": _clean_name(u.get("name"), "URL %d" % i),
                                "url": str(u["url"]).strip()})
            out["urls"] = url_out

    return (base if errors else out), errors
