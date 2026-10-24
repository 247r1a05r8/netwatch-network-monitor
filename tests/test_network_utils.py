"""Unit tests for network_utils. Run from the project folder:
    python -m unittest discover -s tests -v
Tests that need a network use only the loopback address (127.0.0.1) or a local
socket created by the test itself, so they work offline.
"""
import os
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
import network_utils as nu  # noqa: E402

WIN_PING = """Pinging 8.8.8.8 with 32 bytes of data:
Reply from 8.8.8.8: bytes=32 time=21ms TTL=117
Reply from 8.8.8.8: bytes=32 time<1ms TTL=117
Request timed out.
Reply from 192.168.1.5: Destination host unreachable.
"""
LINUX_PING = """64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=8.52 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=57 time=9.10 ms
"""
ROUTE_PRINT = """IPv4 Route Table
Network Destination        Netmask          Gateway       Interface  Metric
          0.0.0.0          0.0.0.0      192.168.1.1    192.168.1.23     35
          0.0.0.0          0.0.0.0      10.0.0.1       10.0.0.7         50
        127.0.0.0        255.0.0.0         On-link         127.0.0.1    331
"""


class LocalIpAndInterfaces(unittest.TestCase):
    def test_1_local_ip_detection_returns_ipv4_or_none(self):
        ip = nu.get_local_ip()
        if ip is not None:
            socket.inet_aton(ip)  # raises if not a valid IPv4

    def test_1b_local_ip_none_when_socket_fails(self):
        with mock.patch("socket.socket", side_effect=OSError("no route")):
            self.assertIsNone(nu.get_local_ip())

    def test_2_interface_detection(self):
        interfaces, err = nu.get_interfaces()
        self.assertIsNone(err)
        self.assertTrue(len(interfaces) >= 1)
        self.assertIn("name", interfaces[0])
        self.assertIn(interfaces[0]["status"], ("UP", "DOWN"))

    def test_2b_pick_interface_prefers_user_choice_then_local_ip(self):
        ifs = [{"name": "A", "ipv4": "10.0.0.2", "status": "UP", "loopback": False},
               {"name": "B", "ipv4": "192.168.1.9", "status": "UP", "loopback": False}]
        self.assertEqual(nu.pick_interface(ifs, "192.168.1.9"), "B")
        self.assertEqual(nu.pick_interface(ifs, "192.168.1.9", "A"), "A")
        self.assertEqual(nu.pick_interface(ifs, None, "missing"), "A")
        self.assertIsNone(nu.pick_interface([], None))

    def test_2c_missing_psutil_handled(self):
        with mock.patch.object(nu, "psutil", None):
            interfaces, err = nu.get_interfaces()
            self.assertEqual(interfaces, [])
            self.assertIn("psutil", err)


class GatewayParsing(unittest.TestCase):
    def test_3_windows_route_print_lowest_metric_wins(self):
        self.assertEqual(nu.parse_route_print(ROUTE_PRINT), "192.168.1.1")

    def test_3b_linux_ip_route(self):
        self.assertEqual(nu.parse_ip_route("default via 192.168.0.1 dev wlan0 proto dhcp\n10.0.0.0/8 dev x"), "192.168.0.1")

    def test_3c_ipconfig_fallback(self):
        self.assertEqual(nu.parse_ipconfig("   Default Gateway . . . . . . . . . : 172.16.0.1"), "172.16.0.1")

    def test_3d_no_gateway_found(self):
        self.assertIsNone(nu.parse_route_print("nothing here"))
        self.assertIsNone(nu.parse_ip_route(""))


class PingTests(unittest.TestCase):
    def test_4_parse_windows_output_counts_only_ttl_replies(self):
        r = nu.parse_ping_output(WIN_PING, 4)
        self.assertEqual(r["received"], 2)          # timeout and 'unreachable' not counted
        self.assertEqual(r["rtts"], [21.0, 0.5])    # time<1ms treated as 0.5

    def test_4b_parse_linux_output(self):
        r = nu.parse_ping_output(LINUX_PING, 2)
        self.assertEqual(r["received"], 2)
        self.assertEqual(r["rtts"], [8.52, 9.10])

    def test_4c_ping_loopback(self):
        r = nu.ping("127.0.0.1", count=2, timeout=2)
        self.assertTrue(r["ok"])
        self.assertEqual(r["loss_pct"], 0.0)

    def test_4d_ping_invalid_host_rejected(self):
        r = nu.ping("8.8.8.8; rm -rf /", count=1)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "Invalid host")

    def test_4e_ping_command_missing_falls_back_to_tcp(self):
        with mock.patch.object(nu, "_run", return_value=None), \
             mock.patch.object(nu, "tcp_check", return_value={"up": False, "response_ms": None}):
            r = nu.ping("127.0.0.1", count=2)
            self.assertFalse(r["ok"])
            self.assertEqual(r["method"], "tcp-443")


class DnsTests(unittest.TestCase):
    def test_5_localhost_resolves(self):
        r = nu.check_dns("localhost")
        self.assertTrue(r["ok"])
        self.assertEqual(r["ip"], "127.0.0.1")

    def test_5b_dns_failure_reported(self):
        with mock.patch("socket.getaddrinfo", side_effect=socket.gaierror("fail")):
            r = nu.check_dns("example.invalid")
        self.assertFalse(r["ok"])
        self.assertIn("could not be resolved", r["error"])

    def test_5c_dns_timeout(self):
        import time
        with mock.patch("socket.getaddrinfo", side_effect=lambda *a, **k: time.sleep(2)):
            r = nu.check_dns("slow.example", timeout=0.2)
        self.assertEqual(r["error"], "DNS timeout")

    def test_5d_invalid_domain(self):
        self.assertEqual(nu.check_dns("bad domain!")["error"], "Invalid domain")


class PortTests(unittest.TestCase):
    def test_6_open_port_is_up_then_closed_port_is_down(self):
        srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
        port = srv.getsockname()[1]
        try:
            self.assertTrue(nu.check_tcp("127.0.0.1", port)["up"])
        finally:
            srv.close()
        r = nu.check_tcp("127.0.0.1", port)
        self.assertFalse(r["up"])
        self.assertEqual(r["error"], "Connection refused")

    def test_6b_invalid_port_and_host(self):
        self.assertEqual(nu.check_tcp("127.0.0.1", 70000)["error"], "Invalid host or port")
        self.assertEqual(nu.check_tcp("bad host", 80)["error"], "Invalid host or port")
        self.assertEqual(nu.check_tcp("127.0.0.1", "abc")["error"], "Invalid host or port")


class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        code = 500 if self.path == "/fail" else 200
        self.send_response(code); self.end_headers(); self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = HTTPServer(("127.0.0.1", 0), _H)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def test_7_http_200_up(self):
        r = nu.check_http("http://127.0.0.1:%d/" % self.port)
        self.assertTrue(r["up"]); self.assertEqual(r["status_code"], 200)

    def test_7b_http_500_down(self):
        r = nu.check_http("http://127.0.0.1:%d/fail" % self.port)
        self.assertFalse(r["up"]); self.assertEqual(r["status_code"], 500)

    def test_7c_connection_refused(self):
        s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
        r = nu.check_http("http://127.0.0.1:%d/" % p)
        self.assertFalse(r["up"]); self.assertEqual(r["error"], "Connection refused")

    def test_7d_invalid_url(self):
        self.assertEqual(nu.check_http("ftp://x.com")["error"], "Invalid URL")
        self.assertEqual(nu.check_http("not a url")["error"], "Invalid URL")


class CalculationTests(unittest.TestCase):
    def test_8_bandwidth(self):
        self.assertEqual(nu.calculate_bandwidth(0, 250_000, 1), 2.0)      # 250 KB/s = 2 Mbps
        self.assertEqual(nu.calculate_bandwidth(1000, 1000, 2), 0.0)
        self.assertIsNone(nu.calculate_bandwidth(5000, 100, 2))           # counter reset
        self.assertIsNone(nu.calculate_bandwidth(0, 100, 0))              # zero time

    def test_9_packet_loss(self):
        self.assertEqual(nu.calculate_packet_loss(4, 3), 25.0)
        self.assertEqual(nu.calculate_packet_loss(4, 4), 0.0)
        self.assertEqual(nu.calculate_packet_loss(4, 0), 100.0)
        self.assertIsNone(nu.calculate_packet_loss(0, 0))

    def test_9b_format_bytes(self):
        self.assertEqual(nu.format_bytes(None), "Unavailable")
        self.assertEqual(nu.format_bytes(1536), "1.50 KB")


class InvalidInput(unittest.TestCase):
    def test_10_host_validation(self):
        for good in ("192.168.1.1", "example.com", "localhost", "my-host.local", "::1"):
            self.assertTrue(config.is_valid_host(good), good)
        for bad in ("", "a b", "-flag", "host;ls", "x" * 300, None, 5):
            self.assertFalse(config.is_valid_host(bad), repr(bad))

    def test_10b_settings_validation(self):
        _, errs = config.validate_settings({"latency_threshold_ms": "abc"})
        self.assertTrue(errs)
        _, errs = config.validate_settings({"packet_loss_threshold_pct": 150})
        self.assertTrue(errs)
        _, errs = config.validate_settings({"gateway_mode": "manual", "gateway_ip": "nope"})
        self.assertTrue(errs)
        _, errs = config.validate_settings({"services": [{"name": "x", "host": "1.2.3.4", "port": 0}]})
        self.assertTrue(errs)
        _, errs = config.validate_settings({"urls": [{"name": "x", "url": "javascript:alert(1)"}]})
        self.assertTrue(errs)
        clean, errs = config.validate_settings({"services": [{"name": "Web", "host": "127.0.0.1", "port": "80"}]})
        self.assertFalse(errs); self.assertEqual(clean["services"][0]["port"], 80)

    def test_10c_too_many_services_rejected(self):
        many = [{"name": "s", "host": "127.0.0.1", "port": 80}] * (config.MAX_SERVICES + 1)
        _, errs = config.validate_settings({"services": many})
        self.assertTrue(errs)


class TimeoutTests(unittest.TestCase):
    def test_11_run_with_timeout(self):
        import time
        done, _ = nu.run_with_timeout(lambda: time.sleep(1), 0.1)
        self.assertFalse(done)
        done, val = nu.run_with_timeout(lambda: 42, 1)
        self.assertTrue(done); self.assertEqual(val, 42)

    def test_11b_tcp_timeout_reported(self):
        with mock.patch("socket.create_connection", side_effect=socket.timeout()):
            self.assertEqual(nu.check_tcp("10.255.255.1", 80)["error"], "Timeout")


if __name__ == "__main__":
    unittest.main()
