"""Unit tests for the monitoring engine rules and failure handling."""
import copy
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
import monitor  # noqa: E402


def make_state(**over):
    st = monitor._initial_state()
    st["local_ip"] = "192.168.1.10"
    st["gateway"].update(ip="192.168.1.1", status="REACHABLE", latency_ms=3)
    st["internet"].update(status="ONLINE", latency_ms=30, loss_pct=0.0)
    st["dns"].update(status="AVAILABLE", domain="example.com")
    for k, v in over.items():
        if isinstance(v, dict):
            st[k].update(v)
        else:
            st[k] = v
    return st


S = config.DEFAULT_SETTINGS


class OverallRules(unittest.TestCase):
    def test_healthy(self):
        self.assertEqual(monitor.compute_overall(make_state(), S)[0], "HEALTHY")

    def test_checking_before_first_results(self):
        self.assertEqual(monitor.compute_overall(monitor._initial_state(), S)[0], "CHECKING")

    def test_offline_when_internet_and_gateway_down(self):
        st = make_state(gateway={"status": "UNREACHABLE"}, internet={"status": "OFFLINE"})
        self.assertEqual(monitor.compute_overall(st, S)[0], "OFFLINE")

    def test_degraded_when_gateway_ok_but_internet_down(self):
        st = make_state(internet={"status": "OFFLINE"})
        status, reasons = monitor.compute_overall(st, S)
        self.assertEqual(status, "DEGRADED")
        self.assertTrue(any("upstream" in r for r in reasons))

    def test_degraded_dns_failure(self):
        self.assertEqual(monitor.compute_overall(make_state(dns={"status": "FAILED"}), S)[0], "DEGRADED")

    def test_degraded_high_latency_and_loss(self):
        self.assertEqual(monitor.compute_overall(make_state(internet={"latency_ms": 500}), S)[0], "DEGRADED")
        self.assertEqual(monitor.compute_overall(make_state(internet={"loss_pct": 25.0}), S)[0], "DEGRADED")

    def test_degraded_service_down(self):
        st = make_state(services=[{"name": "W", "host": "h", "port": 80, "status": "DOWN"}])
        self.assertEqual(monitor.compute_overall(st, S)[0], "DEGRADED")

    def test_offline_without_local_ip(self):
        self.assertEqual(monitor.compute_overall(make_state(local_ip=None), S)[0], "OFFLINE")

    def test_gateway_unavailable_does_not_degrade_when_internet_ok(self):
        st = make_state(gateway={"status": "UNAVAILABLE", "ip": None})
        self.assertEqual(monitor.compute_overall(st, S)[0], "HEALTHY")


class AlertTests(unittest.TestCase):
    def test_alerts_from_real_results(self):
        st = make_state(gateway={"status": "UNREACHABLE"}, internet={"status": "OFFLINE", "latency_ms": 900, "loss_pct": 50.0},
                        services=[{"name": "App", "host": "h", "port": 5000, "status": "DOWN"}])
        msgs = " | ".join(a["message"] for a in monitor.compute_alerts(st, S))
        for expected in ("Gateway unreachable", "Internet connectivity lost", "High latency", "Packet loss", "App"):
            self.assertIn(expected, msgs)

    def test_no_alerts_when_healthy(self):
        self.assertEqual(monitor.compute_alerts(make_state(), S), [])


class EngineBehaviour(unittest.TestCase):
    def setUp(self):
        self.e = monitor.MonitoringEngine()

    def test_failing_check_does_not_crash_cycle(self):
        with mock.patch.object(self.e, "check_gateway", side_effect=RuntimeError("boom")):
            self.e.run_cycle()   # must not raise
        self.assertEqual(self.e.check_errors, 1)
        self.assertTrue(any("Internal error" in ev["message"] for ev in self.e.get_events()))

    def test_event_on_service_down_and_restored(self):
        self.e.state = make_state(services=[{"name": "T", "host": "127.0.0.1", "port": 5001, "status": "UP"}])
        self.e.generate_events()
        self.e.state["services"][0]["status"] = "DOWN"; self.e.generate_events()
        self.e.state["services"][0]["status"] = "UP"; self.e.generate_events()
        msgs = [ev["message"] for ev in self.e.get_events()]
        self.assertTrue(any(m.startswith("SERVICE DOWN") for m in msgs))
        self.assertTrue(any(m.startswith("SERVICE RESTORED") for m in msgs))

    def test_event_log_limited_to_100(self):
        for i in range(250):
            self.e._add_event("info", "e%d" % i)
        self.assertEqual(len(self.e.get_events()), 100)

    def test_clear_logs(self):
        self.e._add_event("info", "x"); self.e.clear_events()
        self.assertEqual(len(self.e.get_events()), 1)   # only the 'cleared' marker

    def test_history_is_bounded(self):
        for i in range(config.PING_HISTORY_SIZE + 50):
            self.e.ping_history.append({"t": 0, "latency": 1, "loss": 0, "min": 1, "max": 1})
        self.assertEqual(len(self.e.ping_history), config.PING_HISTORY_SIZE)

    def test_bandwidth_uses_counter_difference(self):
        seq = iter([{"bytes_recv": 0, "bytes_sent": 0, "time": 100.0},
                    {"bytes_recv": 250_000, "bytes_sent": 125_000, "time": 101.0}])
        with mock.patch("network_utils.get_interface_counters", side_effect=lambda n: next(seq)):
            self.e.calculate_bandwidth("eth0"); self.e.calculate_bandwidth("eth0")
        bw = self.e.state["bandwidth"]
        self.assertEqual((bw["down_mbps"], bw["up_mbps"]), (2.0, 1.0))

    def test_gateway_manual_mode(self):
        s = self.e.get_settings(); s.update(gateway_mode="manual", gateway_ip="10.0.0.1")
        self.e.update_settings(s)
        self.assertEqual(self.e.get_gateway(), ("10.0.0.1", "manual"))

    def test_gateway_not_detected_gives_unavailable(self):
        with mock.patch("network_utils.get_default_gateway", return_value=None):
            gw = self.e.ping_gateway()
        self.assertEqual(gw["status"], "UNAVAILABLE")

    def test_internet_offline_when_everything_fails(self):
        fake_ping = {"ok": False, "avg_ms": None, "min_ms": None, "max_ms": None, "loss_pct": 100.0, "error": "No reply", "method": "icmp"}
        fake_http = {"up": False, "response_ms": None, "status_code": None, "error": "DNS failure"}
        with mock.patch("network_utils.ping", return_value=fake_ping), mock.patch("network_utils.check_http", return_value=fake_http):
            self.e.check_internet()
        self.assertEqual(self.e.state["internet"]["status"], "OFFLINE")

    def test_snapshot_shape(self):
        snap = self.e.snapshot()
        for key in ("network_status", "checks", "alerts", "gateway", "internet", "dns", "bandwidth"):
            self.assertIn(key, snap)

    def test_diagnostics_structure(self):
        with mock.patch("network_utils.get_default_gateway", return_value=None):
            d = self.e.run_diagnostics()
        self.assertIn("steps", d); self.assertIn("overall", d)
        self.assertEqual(d["steps"][0]["name"], "Local Interface")


class FlaskApi(unittest.TestCase):
    def test_api_routes_return_json_and_no_traceback(self):
        import app as netwatch_app
        client = netwatch_app.app.test_client()
        for path in ("/api/status", "/api/network-info", "/api/interfaces", "/api/latency", "/api/dns",
                     "/api/services", "/api/http-check", "/api/events", "/api/config"):
            r = client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertTrue(r.is_json)
        r = client.get("/api/does-not-exist")
        self.assertEqual(r.status_code, 404); self.assertNotIn("Traceback", r.get_data(as_text=True))

    def test_config_rejects_invalid_and_accepts_valid(self):
        import app as netwatch_app
        c = netwatch_app.app.test_client()
        self.assertEqual(c.post("/api/config", json={"dns_domain": "bad domain!"}).status_code, 400)
        self.assertEqual(c.post("/api/config", data="notjson").status_code, 400)
        self.assertEqual(c.post("/api/config", json={"latency_threshold_ms": 250}).status_code, 200)
        netwatch_app.engine.update_settings(copy.deepcopy(config.DEFAULT_SETTINGS))


if __name__ == "__main__":
    unittest.main()
