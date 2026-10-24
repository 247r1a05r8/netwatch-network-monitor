"""Low-level network helper functions used by NetWatch.

Every function here performs a real check against the operating system or the
network and returns plain dictionaries. Nothing is simulated. If a value cannot
be obtained, the function returns None (shown as "Unavailable" in the dashboard)
or an "error" message. Functions never raise for ordinary network failures.
"""
import platform
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request

import config

try:
    import psutil
except ImportError:  # handled gracefully, see README
    psutil = None

IS_WINDOWS = platform.system() == "Windows"


# ---------------------------------------------------------------- calculations
def calculate_packet_loss(sent, received):
    """Packet loss percentage = (sent - received) / sent * 100. None if sent is 0."""
    try:
        sent, received = int(sent), int(received)
    except (TypeError, ValueError):
        return None
    if sent <= 0 or received < 0:
        return None
    received = min(received, sent)
    return round((sent - received) * 100.0 / sent, 1)


def calculate_bandwidth(prev_bytes, curr_bytes, seconds):
    """Rate in Mbps = (change in bytes * 8) / seconds / 1,000,000.

    Returns None when the counters went backwards (counter reset) or the time
    difference is not positive.
    """
    try:
        delta = curr_bytes - prev_bytes
        if seconds <= 0 or delta < 0:
            return None
        return round(delta * 8.0 / seconds / 1_000_000, 3)
    except TypeError:
        return None


def format_bytes(n):
    if n is None:
        return "Unavailable"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%d B" % n if unit == "B" else "%.2f %s" % (n, unit)
        n /= 1024


# ------------------------------------------------------------------ small tools
def run_with_timeout(func, timeout, *args):
    """Run func(*args) in a daemon thread; return (finished, result_or_exception)."""
    box = {}

    def target():
        try:
            box["value"] = func(*args)
        except Exception as exc:  # noqa: BLE001 - reported to caller
            box["error"] = exc

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return False, None
    return True, box.get("error", box.get("value"))


def _popen_kwargs():
    kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
    if IS_WINDOWS:
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW: no console flash
    return kwargs


def _run(cmd, timeout):
    """Run a command, return output text or None if it cannot run."""
    try:
        proc = subprocess.run(cmd, timeout=timeout, **_popen_kwargs())
        return proc.stdout.decode("utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None


# ------------------------------------------------------------------ local info
def get_local_ip():
    """Local IPv4 address used for outgoing traffic.

    A UDP socket is "connected" to a public address only so the OS chooses a
    route; no packet is sent. Returns None if there is no usable route.
    """
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("192.0.2.1", 9))  # TEST-NET address, never contacted
        ip = s.getsockname()[0]
        return None if ip.startswith("0.") else ip
    except OSError:
        return None
    finally:
        if s:
            s.close()


def get_ipv6_addresses():
    if psutil is None:
        return []
    out = []
    try:
        for name, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family == socket.AF_INET6 and not a.address.lower().startswith("fe80"):
                    out.append(a.address.split("%")[0])
    except Exception:  # noqa: BLE001
        pass
    return out[:4]


def get_interfaces():
    """List real network interfaces using psutil. Returns (list, error_or_None)."""
    if psutil is None:
        return [], "psutil is not installed. Run: pip install psutil"
    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        io = psutil.net_io_counters(pernic=True)
    except Exception as exc:  # noqa: BLE001
        return [], "Could not read interfaces: %s" % type(exc).__name__
    result = []
    for name, st in stats.items():
        ipv4, mac = None, None
        for a in addrs.get(name, []):
            if a.family == socket.AF_INET and ipv4 is None:
                ipv4 = a.address
            elif getattr(psutil, "AF_LINK", None) is not None and a.family == psutil.AF_LINK:
                mac = a.address
        c = io.get(name)
        result.append({
            "name": name,
            "status": "UP" if st.isup else "DOWN",
            "ipv4": ipv4,
            "mac": mac,
            "speed_mbps": st.speed or None,
            "bytes_sent": c.bytes_sent if c else None,
            "bytes_recv": c.bytes_recv if c else None,
            "packets_sent": c.packets_sent if c else None,
            "packets_recv": c.packets_recv if c else None,
            "errors_in": c.errin if c else None,
            "errors_out": c.errout if c else None,
            "loopback": bool(ipv4 and ipv4.startswith("127.")),
        })
    result.sort(key=lambda i: (i["loopback"], i["status"] != "UP", i["name"].lower()))
    return result, None


def pick_interface(interfaces, local_ip, preferred="auto"):
    """Choose the interface used for traffic monitoring.

    A user-selected name wins. Otherwise pick the interface that owns the local
    IP, never blindly the first one in the list.
    """
    names = {i["name"] for i in interfaces}
    if preferred and preferred != "auto" and preferred in names:
        return preferred
    if local_ip:
        for i in interfaces:
            if i["ipv4"] == local_ip:
                return i["name"]
    for i in interfaces:
        if i["status"] == "UP" and not i["loopback"] and i["ipv4"]:
            return i["name"]
    return None


def get_interface_counters(name):
    if psutil is None or not name:
        return None
    try:
        c = psutil.net_io_counters(pernic=True).get(name)
        if c is None:
            return None
        return {"bytes_sent": c.bytes_sent, "bytes_recv": c.bytes_recv, "time": time.time()}
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------- gateway
def parse_route_print(text):
    """Parse Windows `route print -4` output. Returns gateway IP or None."""
    best = None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
            gw = parts[2]
            if config.is_valid_ip(gw) and gw != "0.0.0.0":
                try:
                    metric = int(parts[4])
                except ValueError:
                    metric = 9999
                if best is None or metric < best[0]:
                    best = (metric, gw)
    return best[1] if best else None


def parse_ip_route(text):
    """Parse Linux `ip route` output. Returns gateway IP or None."""
    for line in text.splitlines():
        m = re.match(r"^default\s+via\s+(\S+)", line.strip())
        if m and config.is_valid_ip(m.group(1)):
            return m.group(1)
    return None


def parse_ipconfig(text):
    """Fallback: parse `ipconfig` for 'Default Gateway ... : x.x.x.x'."""
    for m in re.finditer(r"Default Gateway[ .]*:\s*([0-9.]+)", text):
        if config.is_valid_ip(m.group(1)):
            return m.group(1)
    return None


def get_default_gateway():
    """Detect the default gateway. Returns IP string or None (never hard coded)."""
    system = platform.system()
    if system == "Windows":
        out = _run(["route", "print", "-4"], 8)
        gw = parse_route_print(out) if out else None
        if gw:
            return gw
        out = _run(["ipconfig"], 8)
        return parse_ipconfig(out) if out else None
    if system == "Linux":
        try:
            with open("/proc/net/route") as f:
                for line in f.readlines()[1:]:
                    p = line.split()
                    if len(p) >= 3 and p[1] == "00000000" and int(p[3], 16) & 2:
                        b = bytes.fromhex(p[2])[::-1]
                        return socket.inet_ntoa(b)
        except (OSError, ValueError):
            pass
    out = _run(["ip", "route"], 5)
    if out:
        gw = parse_ip_route(out)
        if gw:
            return gw
    out = _run(["route", "-n", "get", "default"], 5)  # macOS
    if out:
        m = re.search(r"gateway:\s*(\S+)", out)
        if m and config.is_valid_ip(m.group(1)):
            return m.group(1)
    return None


# ------------------------------------------------------------------------ ping
def parse_ping_output(text, count):
    """Parse ping output (Windows, Linux, macOS). Returns dict with rtts and counts.

    A reply is counted only when it has a TTL field, so 'Destination host
    unreachable' lines on Windows are not counted as success.
    """
    replies = re.findall(r"ttl[=:]\s*\d+", text, flags=re.I)
    rtts = []
    for line in text.splitlines():
        if re.search(r"ttl[=:]\s*\d+", line, flags=re.I):
            m = re.search(r"time\s*([=<])\s*([0-9.]+)\s*ms", line, flags=re.I)
            if m:
                value = float(m.group(2))
                rtts.append(0.5 if m.group(1) == "<" and value <= 1 else value)
    received = len(replies)
    return {"sent": count, "received": min(received, count), "rtts": rtts[:count]}


def ping(host, count=None, timeout=None):
    """Send a few ICMP echo requests using the OS ping command.

    Returns {"ok", "sent", "received", "loss_pct", "avg_ms", "min_ms", "max_ms",
    "method", "error"}. Falls back to TCP connect timing (port 443) if the ping
    command is missing or blocked from running.
    """
    count = count or config.PING_COUNT
    timeout = timeout or config.PING_TIMEOUT
    result = {"ok": False, "sent": count, "received": 0, "loss_pct": None,
              "avg_ms": None, "min_ms": None, "max_ms": None, "rtts": [],
              "method": "icmp", "error": None}
    if not config.is_valid_host(host):
        result["error"] = "Invalid host"
        return result
    system = platform.system()
    if system == "Windows":
        cmd = ["ping", "-n", str(count), "-w", str(int(timeout * 1000)), host]
    elif system == "Darwin":
        cmd = ["ping", "-c", str(count), "-W", str(int(timeout * 1000)), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(int(timeout)), "-i", "0.3", host]
    out = _run(cmd, timeout * count + 6)
    if out is None:
        return _tcp_ping_fallback(host, count, result, "ping command unavailable")
    parsed = parse_ping_output(out, count)
    if parsed["received"] == 0 and re.search(
            r"could not find host|unknown host|name or service not known|"
            r"temporary failure in name resolution|cannot resolve", out, flags=re.I):
        result["error"] = "Host name could not be resolved"
        result["loss_pct"] = 100.0
        return result
    result.update(parsed)
    result["loss_pct"] = calculate_packet_loss(count, parsed["received"])
    if parsed["rtts"]:
        r = parsed["rtts"]
        result.update(avg_ms=round(sum(r) / len(r), 2), min_ms=round(min(r), 2),
                      max_ms=round(max(r), 2))
    result["ok"] = parsed["received"] > 0
    if not result["ok"]:
        result["error"] = "No reply"
    return result


def _tcp_ping_fallback(host, count, result, reason):
    rtts = []
    for _ in range(count):
        t = tcp_check(host, 443, timeout=config.TCP_TIMEOUT)
        if t["up"]:
            rtts.append(t["response_ms"])
    result.update(method="tcp-443", sent=count, received=len(rtts), rtts=rtts,
                  loss_pct=calculate_packet_loss(count, len(rtts)))
    if rtts:
        result.update(avg_ms=round(sum(rtts) / len(rtts), 1), min_ms=round(min(rtts), 1),
                      max_ms=round(max(rtts), 1), ok=True)
    else:
        result["error"] = reason + "; TCP fallback failed"
    return result


# ------------------------------------------------------------------------- DNS
def check_dns(domain, timeout=None):
    """Resolve a domain with the system resolver and time the answer."""
    timeout = timeout or config.DNS_TIMEOUT
    res = {"ok": False, "domain": domain, "ip": None, "response_ms": None, "error": None}
    if not config.is_valid_host(domain):
        res["error"] = "Invalid domain"
        return res
    start = time.perf_counter()
    finished, value = run_with_timeout(socket.getaddrinfo, timeout, domain, None, socket.AF_INET)
    elapsed = (time.perf_counter() - start) * 1000
    if not finished:
        res["error"] = "DNS timeout"
    elif isinstance(value, socket.gaierror):
        res["error"] = "Name could not be resolved"
    elif isinstance(value, Exception):
        res["error"] = "DNS error (%s)" % type(value).__name__
    elif not value:
        res["error"] = "No address returned"
    else:
        res.update(ok=True, ip=value[0][4][0], response_ms=round(elapsed, 1))
    return res


# ------------------------------------------------------------------- TCP / HTTP
def check_tcp(host, port, timeout=None):
    """One TCP connection attempt to one configured host:port (no scanning)."""
    return tcp_check(host, port, timeout)


def tcp_check(host, port, timeout=None):
    timeout = timeout or config.TCP_TIMEOUT
    res = {"up": False, "host": host, "port": port, "response_ms": None, "error": None}
    try:
        port = int(port)
        if not (1 <= port <= 65535) or not config.is_valid_host(host):
            raise ValueError
    except (TypeError, ValueError):
        res["error"] = "Invalid host or port"
        return res
    start = time.perf_counter()
    s = None
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        res.update(up=True, response_ms=round((time.perf_counter() - start) * 1000, 1))
    except socket.timeout:
        res["error"] = "Timeout"
    except ConnectionRefusedError:
        res["error"] = "Connection refused"
    except socket.gaierror:
        res["error"] = "Host name could not be resolved"
    except OSError as exc:
        res["error"] = "Connection error (%s)" % (exc.__class__.__name__)
    finally:
        if s:
            s.close()
    return res


def check_http(url, timeout=None):
    """Lightweight HTTP(S) GET. Reads at most 1 KB, never downloads the page."""
    timeout = timeout or config.HTTP_TIMEOUT
    res = {"up": False, "url": url, "status_code": None, "response_ms": None, "error": None}
    if not config.is_valid_url(url):
        res["error"] = "Invalid URL"
        return res
    req = urllib.request.Request(url, headers={"User-Agent": "NetWatch/1.0", "Range": "bytes=0-1023"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(1024)
            code = resp.getcode()
        res.update(status_code=code, up=code < 400,
                   response_ms=round((time.perf_counter() - start) * 1000, 1))
    except urllib.error.HTTPError as exc:
        res.update(status_code=exc.code, up=exc.code < 400,
                   response_ms=round((time.perf_counter() - start) * 1000, 1))
        if exc.code >= 400:
            res["error"] = "HTTP error %d" % exc.code
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, socket.gaierror):
            res["error"] = "DNS failure"
        elif isinstance(reason, (socket.timeout, TimeoutError)):
            res["error"] = "Timeout"
        elif isinstance(reason, ConnectionRefusedError):
            res["error"] = "Connection refused"
        else:
            res["error"] = "Connection error"
    except (socket.timeout, TimeoutError):
        res["error"] = "Timeout"
    except Exception as exc:  # noqa: BLE001
        res["error"] = "Request failed (%s)" % type(exc).__name__
    return res


def get_system_info():
    return {
        "hostname": socket.gethostname(),
        "os": "%s %s" % (platform.system(), platform.release()),
        "python": platform.python_version(),
    }
