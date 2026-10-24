"""NetWatch monitoring engine.

A background thread runs the checks on their own schedules and stores the
latest results in memory. Flask routes only read that stored state, so a slow
network check can never block a web request.
"""
import copy
import threading
import time
from collections import deque
from datetime import datetime

import config
import network_utils as nu


# ------------------------------------------------------------ pure rule functions
def compute_alerts(state, settings):
    """Build the list of active alerts from real monitoring results."""
    alerts = []
    gw, net, dns = state["gateway"], state["internet"], state["dns"]
    if gw["status"] == "UNREACHABLE":
        alerts.append({"level": "error", "key": "gateway", "message": "Gateway unreachable"})
    if net["status"] == "OFFLINE":
        alerts.append({"level": "error", "key": "internet", "message": "Internet connectivity lost"})
    if dns["status"] == "FAILED":
        alerts.append({"level": "error", "key": "dns", "message": "DNS resolution failing"})
    lat = net.get("latency_ms")
    if lat is not None and lat > settings["latency_threshold_ms"]:
        alerts.append({"level": "warning", "key": "latency",
                       "message": "High latency detected (%s ms)" % lat})
    loss = net.get("loss_pct")
    if loss is not None and loss > settings["packet_loss_threshold_pct"]:
        alerts.append({"level": "warning", "key": "loss",
                       "message": "Packet loss detected (%s%%)" % loss})
    for s in state["services"]:
        if s["status"] == "DOWN":
            alerts.append({"level": "warning", "key": "svc:%s:%s" % (s["host"], s["port"]),
                           "message": "Monitored service unavailable: %s" % s["name"]})
    for u in state["urls"]:
        if u["status"] == "DOWN":
            alerts.append({"level": "warning", "key": "url:" + u["url"],
                           "message": "Monitored URL unavailable: %s" % u["name"]})
    return alerts


def compute_overall(state, settings):
    """Documented health rules. Returns (status, reasons).

    OFFLINE   : internet check failing AND gateway not reachable (or no active
                interface with an IP address).
    DEGRADED  : any one test failing, latency above threshold, packet loss above
                threshold, or a monitored service/URL down.
    HEALTHY   : gateway reachable (or unavailable to detect), internet reachable,
                DNS working, loss and latency within thresholds, services up.
    CHECKING  : first measurements not finished yet.
    """
    gw, net, dns = state["gateway"], state["internet"], state["dns"]
    reasons = []
    if net["status"] == "UNKNOWN" and gw["status"] == "UNKNOWN":
        return "CHECKING", ["First measurements are still running."]
    if not state["local_ip"]:
        return "OFFLINE", ["No local IP address / no active network route."]
    if net["status"] == "OFFLINE" and gw["status"] in ("UNREACHABLE", "UNAVAILABLE"):
        return "OFFLINE", ["Internet and gateway are not reachable."]
    if net["status"] == "OFFLINE":
        reasons.append("Internet unreachable while gateway is reachable (possible upstream/WAN problem).")
    if gw["status"] == "UNREACHABLE":
        reasons.append("Gateway unreachable.")
    if dns["status"] == "FAILED":
        reasons.append("DNS resolution failing.")
    if net.get("latency_ms") is not None and net["latency_ms"] > settings["latency_threshold_ms"]:
        reasons.append("Latency above threshold.")
    if net.get("loss_pct") is not None and net["loss_pct"] > settings["packet_loss_threshold_pct"]:
        reasons.append("Packet loss above threshold.")
    if any(s["status"] == "DOWN" for s in state["services"]):
        reasons.append("A monitored service is down.")
    if any(u["status"] == "DOWN" for u in state["urls"]):
        reasons.append("A monitored URL is down.")
    return ("DEGRADED" if reasons else "HEALTHY"), reasons


def build_health_checks(state, settings):
    """Per-item tick marks for the Network Health card: ok / warn / fail / unknown."""
    def lvl(ok, unknown=False):
        return "unknown" if unknown else ("ok" if ok else "fail")
    gw, net, dns = state["gateway"], state["internet"], state["dns"]
    lat, loss = net.get("latency_ms"), net.get("loss_pct")
    svc_all = state["services"] + state["urls"]
    return [
        {"name": "Latency", "level": lvl(lat is not None and lat <= settings["latency_threshold_ms"],
                                         unknown=lat is None and net["status"] != "OFFLINE")},
        {"name": "Packet Loss", "level": lvl(loss is not None and loss <= settings["packet_loss_threshold_pct"],
                                             unknown=loss is None)},
        {"name": "Gateway", "level": lvl(gw["status"] == "REACHABLE",
                                         unknown=gw["status"] in ("UNKNOWN", "UNAVAILABLE"))},
        {"name": "Internet", "level": lvl(net["status"] == "ONLINE", unknown=net["status"] == "UNKNOWN")},
        {"name": "DNS", "level": lvl(dns["status"] == "AVAILABLE", unknown=dns["status"] == "UNKNOWN")},
        {"name": "Services", "level": "unknown" if not svc_all else
            lvl(all(s["status"] == "UP" for s in svc_all),
                unknown=any(s["status"] == "UNKNOWN" for s in svc_all))},
    ]


def _initial_state():
    return {
        "local_ip": None,
        "interface": None,
        "gateway": {"ip": None, "source": None, "status": "UNKNOWN", "latency_ms": None, "loss_pct": None, "error": None},
        "internet": {"status": "UNKNOWN", "target": None, "method": None, "latency_ms": None,
                     "min_ms": None, "max_ms": None, "loss_pct": None, "http_ms": None, "error": None},
        "dns": {"status": "UNKNOWN", "domain": None, "ip": None, "response_ms": None, "error": None},
        "bandwidth": {"interface": None, "down_mbps": None, "up_mbps": None},
        "services": [],
        "urls": [],
    }


class MonitoringEngine:
    def __init__(self, settings=None):
        self.settings = copy.deepcopy(settings or config.DEFAULT_SETTINGS)
        self.lock = threading.RLock()
        self.state = _initial_state()
        self.events = deque(maxlen=config.MAX_EVENTS)
        self.ping_history = deque(maxlen=config.PING_HISTORY_SIZE)
        self.bw_history = deque(maxlen=config.BANDWIDTH_HISTORY_SIZE)
        self.last_run = {}
        self.cycles = 0
        self._prev_counters = None
        self._prev_iface = None
        self._prev_conditions = {}
        self._prev_overall = None
        self._thread = None
        self._stop = threading.Event()
        self.started_at = None
        self.interfaces = []
        self.interfaces_error = None
        self.check_errors = 0

    # ------------------------------------------------------------- lifecycle
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.started_at = time.time()
        self._add_event("info", "NetWatch monitoring started")
        self._thread = threading.Thread(target=self._loop, name="netwatch-monitor", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            self.run_cycle()
            self._stop.wait(config.MONITOR_INTERVAL)

    # ----------------------------------------------------------------- events
    def _add_event(self, level, message):
        with self.lock:
            self.events.appendleft({"time": datetime.now().strftime("%H:%M:%S"),
                                    "ts": time.time(), "level": level, "message": message})

    def clear_events(self):
        with self.lock:
            self.events.clear()
        self._add_event("info", "Event log cleared")

    def _due(self, name, interval, now):
        if now - self.last_run.get(name, 0) >= interval:
            self.last_run[name] = now
            return True
        return False

    def _safe(self, name, func):
        """One failing check must never stop the others."""
        try:
            func()
        except Exception as exc:  # noqa: BLE001
            self.check_errors += 1
            self._add_event("warning", "Internal error in %s check (%s)" % (name, type(exc).__name__))

    # ------------------------------------------------------------------ cycle
    def run_cycle(self):
        now = time.time()
        self.cycles += 1
        self._safe("interface", self.check_interface_and_bandwidth)
        if self._due("gateway", config.GATEWAY_INTERVAL, now):
            self._safe("gateway", self.check_gateway)
        if self._due("internet", config.INTERNET_INTERVAL, now):
            self._safe("internet", self.check_internet)
        if self._due("dns", config.DNS_INTERVAL, now):
            self._safe("dns", self.check_dns)
        if self._due("services", config.SERVICE_INTERVAL, now):
            self._safe("services", self.check_services)
        self._safe("events", self.generate_events)

    # ------------------------------------------------------------------ checks
    def get_network_interfaces(self):
        interfaces, err = nu.get_interfaces()
        with self.lock:
            self.interfaces, self.interfaces_error = interfaces, err
        return interfaces

    def get_local_ip(self):
        ip = nu.get_local_ip()
        with self.lock:
            self.state["local_ip"] = ip
        return ip

    def check_interface_and_bandwidth(self):
        ip = self.get_local_ip()
        interfaces = self.get_network_interfaces()
        with self.lock:
            pref = self.settings["interface"]
        name = nu.pick_interface(interfaces, ip, pref)
        with self.lock:
            self.state["interface"] = name
        self.calculate_bandwidth(name)

    def calculate_bandwidth(self, name):
        counters = nu.get_interface_counters(name)
        down = up = None
        if counters and self._prev_counters and self._prev_iface == name:
            dt = counters["time"] - self._prev_counters["time"]
            down = nu.calculate_bandwidth(self._prev_counters["bytes_recv"], counters["bytes_recv"], dt)
            up = nu.calculate_bandwidth(self._prev_counters["bytes_sent"], counters["bytes_sent"], dt)
        self._prev_counters, self._prev_iface = counters, name
        with self.lock:
            self.state["bandwidth"] = {"interface": name, "down_mbps": down, "up_mbps": up}
            if down is not None and up is not None:
                self.bw_history.append({"t": time.time(), "down": down, "up": up})

    def get_gateway(self):
        with self.lock:
            mode, manual = self.settings["gateway_mode"], self.settings["gateway_ip"]
        if mode == "manual" and manual:
            return manual, "manual"
        ip = nu.get_default_gateway()
        return ip, ("auto" if ip else None)

    def ping_gateway(self):
        gw_ip, source = self.get_gateway()
        gw = {"ip": gw_ip, "source": source, "status": "UNAVAILABLE", "latency_ms": None,
              "loss_pct": None, "error": "Default gateway could not be detected. Set it manually in Configuration."}
        if gw_ip:
            r = nu.ping(gw_ip)
            gw.update(status="REACHABLE" if r["ok"] else "UNREACHABLE", latency_ms=r["avg_ms"],
                      loss_pct=r["loss_pct"], error=None if r["ok"] else r["error"])
        return gw

    def check_gateway(self):
        gw = self.ping_gateway()
        with self.lock:
            self.state["gateway"] = gw

    def check_internet(self):
        with self.lock:
            host = self.settings["internet_ping_host"]
            url = self.settings["internet_http_url"]
        p = nu.ping(host)
        h = nu.check_http(url)
        online = p["ok"] or h["up"]
        net = {"status": "ONLINE" if online else "OFFLINE", "target": host, "method": p["method"],
               "latency_ms": p["avg_ms"], "min_ms": p["min_ms"], "max_ms": p["max_ms"],
               "loss_pct": p["loss_pct"], "http_ms": h["response_ms"] if h["up"] else None,
               "http_status": h["status_code"],
               "error": None if online else (h["error"] or p["error"])}
        with self.lock:
            self.state["internet"] = net
            self.ping_history.append({"t": time.time(), "latency": p["avg_ms"],
                                      "loss": p["loss_pct"], "min": p["min_ms"], "max": p["max_ms"]})

    def check_dns(self):
        with self.lock:
            domain = self.settings["dns_domain"]
        r = nu.check_dns(domain)
        with self.lock:
            self.state["dns"] = {"status": "AVAILABLE" if r["ok"] else "FAILED", "domain": domain,
                                 "ip": r["ip"], "response_ms": r["response_ms"], "error": r["error"]}

    def check_services(self):
        with self.lock:
            services = list(self.settings["services"])
            urls = list(self.settings["urls"])
        svc_out, url_out = [], []
        for s in services:
            r = nu.check_tcp(s["host"], s["port"])
            svc_out.append({"name": s["name"], "host": s["host"], "port": s["port"],
                            "status": "UP" if r["up"] else "DOWN",
                            "response_ms": r["response_ms"], "error": r["error"]})
        for u in urls:
            r = nu.check_http(u["url"])
            url_out.append({"name": u["name"], "url": u["url"],
                            "status": "UP" if r["up"] else "DOWN", "status_code": r["status_code"],
                            "response_ms": r["response_ms"], "error": r["error"]})
        with self.lock:
            self.state["services"], self.state["urls"] = svc_out, url_out

    # ----------------------------------------------------------------- events
    def generate_events(self):
        """Write an event whenever a real condition changes state."""
        with self.lock:
            st = copy.deepcopy(self.state)
            settings = copy.deepcopy(self.settings)
        conds = {}
        gw, net, dns = st["gateway"], st["internet"], st["dns"]
        if gw["status"] in ("REACHABLE", "UNREACHABLE"):
            conds["gateway"] = (gw["status"] == "REACHABLE", "Gateway unreachable", "Gateway reachable")
        if net["status"] in ("ONLINE", "OFFLINE"):
            conds["internet"] = (net["status"] == "ONLINE", "Internet connectivity lost",
                                 "Internet connectivity restored")
        if dns["status"] in ("AVAILABLE", "FAILED"):
            conds["dns"] = (dns["status"] == "AVAILABLE", "DNS check failed", "DNS check successful")
        if net.get("latency_ms") is not None:
            conds["latency"] = (net["latency_ms"] <= settings["latency_threshold_ms"],
                                "Latency increased above threshold (%s ms)" % net["latency_ms"],
                                "Latency back within threshold")
        if net.get("loss_pct") is not None:
            conds["loss"] = (net["loss_pct"] <= settings["packet_loss_threshold_pct"],
                             "Packet loss detected (%s%%)" % net["loss_pct"], "Packet loss back within threshold")
        for s in st["services"]:
            conds["svc:%s:%s" % (s["host"], s["port"])] = (
                s["status"] == "UP", "SERVICE DOWN: %s (%s:%s)" % (s["name"], s["host"], s["port"]),
                "SERVICE RESTORED: %s (%s:%s)" % (s["name"], s["host"], s["port"]))
        for u in st["urls"]:
            conds["url:" + u["url"]] = (u["status"] == "UP", "URL DOWN: %s" % u["name"],
                                        "URL RESTORED: %s" % u["name"])
        for key, (ok, bad, good) in conds.items():
            prev = self._prev_conditions.get(key)
            if prev is None:
                if not ok or key in ("gateway", "internet", "dns"):
                    first_ok = {"internet": "Internet ONLINE"}.get(key, good)
                    self._add_event("success" if ok else "error", first_ok if ok else bad)
            elif prev != ok:
                self._add_event("success" if ok else "error", good if ok else bad)
            self._prev_conditions[key] = ok
        for key in list(self._prev_conditions):
            if key not in conds:
                del self._prev_conditions[key]
        overall, _ = compute_overall(st, settings)
        if overall != self._prev_overall and overall != "CHECKING":
            level = {"HEALTHY": "success", "DEGRADED": "warning", "OFFLINE": "error"}[overall]
            self._add_event(level, "Network %s" % {"HEALTHY": "ONLINE", "DEGRADED": "DEGRADED",
                                                   "OFFLINE": "OFFLINE"}[overall])
            self._prev_overall = overall

    # ---------------------------------------------------------------- queries
    def update_settings(self, new_settings):
        with self.lock:
            self.settings = copy.deepcopy(new_settings)
            # force fresh checks on the next tick so the user sees the change quickly
            self.last_run = {}
            self._prev_counters = None

    def get_settings(self):
        with self.lock:
            return copy.deepcopy(self.settings)

    def snapshot(self):
        with self.lock:
            st = copy.deepcopy(self.state)
            settings = copy.deepcopy(self.settings)
            ifaces = copy.deepcopy(self.interfaces)
        overall, reasons = compute_overall(st, settings)
        selected = next((i for i in ifaces if i["name"] == st["interface"]), None)
        status_label = {"HEALTHY": "ONLINE", "DEGRADED": "DEGRADED", "OFFLINE": "OFFLINE",
                        "CHECKING": "CHECKING"}[overall]
        return {
            "network_status": status_label,
            "health": overall,
            "reasons": reasons,
            "checks": build_health_checks(st, settings),
            "alerts": compute_alerts(st, settings),
            "selected_interface": selected,
            "interfaces_error": self.interfaces_error,
            "thresholds": {"latency_ms": settings["latency_threshold_ms"],
                           "loss_pct": settings["packet_loss_threshold_pct"]},
            "uptime_s": int(time.time() - self.started_at) if self.started_at else 0,
            "server_time": datetime.now().strftime("%H:%M:%S"),
            **st,
        }

    def history(self, window_s):
        cutoff = time.time() - window_s
        with self.lock:
            ping = [p for p in self.ping_history if p["t"] >= cutoff]
            bw = [b for b in self.bw_history if b["t"] >= cutoff]
        lat = [p["latency"] for p in ping if p["latency"] is not None]
        stats = {"current": lat[-1] if lat else None,
                 "avg": round(sum(lat) / len(lat), 2) if lat else None,
                 "min": min(lat) if lat else None, "max": max(lat) if lat else None}
        losses = [p["loss"] for p in ping if p["loss"] is not None]
        stats["loss_avg"] = round(sum(losses) / len(losses), 1) if losses else None
        now = time.time()
        return {"window_s": window_s, "stats": stats,
                "ping": [{"age": round(now - p["t"], 1), "latency": p["latency"], "loss": p["loss"]} for p in ping],
                "bandwidth": [{"age": round(now - b["t"], 1), "down": b["down"], "up": b["up"]} for b in bw]}

    def get_events(self):
        with self.lock:
            return list(self.events)

    # ------------------------------------------------------------ diagnostics
    def run_diagnostics(self):
        """Run the Network Troubleshooter: safe tests in a fixed order."""
        settings = self.get_settings()
        steps = []

        def add(name, status, detail, cause=None, suggestions=None):
            steps.append({"name": name, "status": status, "detail": detail,
                          "possible_cause": cause, "suggestions": suggestions or []})

        ip = nu.get_local_ip()
        ifaces, err = nu.get_interfaces()
        name = nu.pick_interface(ifaces, ip, settings["interface"])
        if err:
            add("Local Interface", "FAIL", err, "Interface information could not be read.",
                ["Install psutil: pip install psutil", "Restart NetWatch"])
        elif ip and name:
            add("Local Interface", "PASS", "%s is up with IP %s" % (name, ip))
        else:
            add("Local Interface", "FAIL", "No active interface with an IP address was found.",
                "The device may not be connected to a network.",
                ["Check Wi-Fi/Ethernet connection", "Verify the network adapter is enabled"])
        gw_ip, source = self.get_gateway()
        gw_ok = None
        if gw_ip:
            add("Default Gateway", "PASS", "Gateway %s (%s)" % (gw_ip, "manual" if source == "manual" else "auto-detected"))
            r = nu.ping(gw_ip)
            gw_ok = r["ok"]
            if r["ok"]:
                add("Gateway Ping", "PASS", "%s ms average, %s%% loss" % (r["avg_ms"], r["loss_pct"]))
            else:
                add("Gateway Ping", "FAIL", "No reply from %s" % gw_ip,
                    "Local network/router connectivity may be unavailable. Some routers also block ping.",
                    ["Check Wi-Fi/Ethernet connection", "Check router status", "Verify network adapter"])
        else:
            add("Default Gateway", "UNAVAILABLE", "Gateway could not be detected.",
                "The device may have no route, or detection is not supported.",
                ["Set the gateway manually in Configuration"])
            add("Gateway Ping", "SKIPPED", "No gateway to test.")
        d = nu.check_dns(settings["dns_domain"])
        if d["ok"]:
            add("DNS Resolution", "PASS", "%s resolved to %s in %s ms" % (d["domain"], d["ip"], d["response_ms"]))
        else:
            add("DNS Resolution", "FAIL", "%s: %s" % (d["domain"], d["error"]),
                "The DNS server may be unreachable or misconfigured (possible cause only).",
                ["Try another DNS server (for example 8.8.8.8 or 1.1.1.1) in adapter settings",
                 "Restart the router", "Run: ipconfig /flushdns"])
        p = nu.ping(settings["internet_ping_host"])
        h = nu.check_http(settings["internet_http_url"])
        if p["ok"] or h["up"]:
            parts = []
            if p["ok"]:
                parts.append("ping %s ms" % p["avg_ms"])
            if h["up"]:
                parts.append("HTTP %s in %s ms" % (h["status_code"], h["response_ms"]))
            add("Internet Connectivity", "PASS", ", ".join(parts))
        else:
            if gw_ok:
                cause = "Gateway works but internet does not: possible upstream/WAN/ISP problem."
            elif gw_ok is False:
                cause = "Local network path problem is more likely (gateway also unreachable)."
            else:
                cause = "Internet endpoints are unreachable (possible cause only)."
            add("Internet Connectivity", "FAIL", "Ping: %s; HTTP: %s" % (p["error"], h["error"]), cause,
                ["Check the router's internet light", "Contact the internet provider if the router is fine"])
        svc_fail = 0
        svc_total = len(settings["services"]) + len(settings["urls"])
        if svc_total == 0:
            add("Configured Services", "SKIPPED", "No services or URLs are configured.")
        else:
            lines = []
            for s in settings["services"]:
                r = nu.check_tcp(s["host"], s["port"])
                svc_fail += 0 if r["up"] else 1
                lines.append("%s %s:%s %s" % (s["name"], s["host"], s["port"], "UP" if r["up"] else "DOWN (%s)" % r["error"]))
            for u in settings["urls"]:
                r = nu.check_http(u["url"])
                svc_fail += 0 if r["up"] else 1
                lines.append("%s %s" % (u["name"], ("UP (HTTP %s)" % r["status_code"]) if r["up"] else "DOWN (%s)" % r["error"]))
            if svc_fail:
                add("Configured Services", "FAIL", "; ".join(lines),
                    "The service may be stopped, blocked by a firewall, or the host may be down.",
                    ["Check that the service is running", "Check the host and port in Configuration"])
            else:
                add("Configured Services", "PASS", "; ".join(lines))
        failed = [s for s in steps if s["status"] == "FAIL"]
        if not failed:
            overall = "No basic connectivity problem detected."
        else:
            overall = "Possible problem areas: %s. These checks cannot identify every possible fault." % ", ".join(s["name"] for s in failed)
        return {"steps": steps, "overall": overall, "passed": not failed,
                "time": datetime.now().strftime("%H:%M:%S")}
