"""NetWatch - Flask web server. Routes only read data from the monitoring engine."""
import logging

from flask import Flask, jsonify, render_template, request

import config
from monitor import MonitoringEngine
import network_utils as nu

app = Flask(__name__)
engine = MonitoringEngine()
log = logging.getLogger("netwatch")

WINDOWS = {"1": 60, "5": 300, "15": 900}


def ok(data, code=200):
    resp = jsonify(data)
    resp.status_code = code
    resp.headers["Cache-Control"] = "no-store"
    return resp


def fail(message, code=400, **extra):
    return ok({"error": message, **extra}, code)


@app.errorhandler(404)
def not_found(_e):
    return fail("Not found", 404)


@app.errorhandler(405)
def bad_method(_e):
    return fail("Method not allowed", 405)


@app.errorhandler(Exception)
def handle_any(exc):
    log.exception("Unhandled error")  # details stay in the server console only
    return fail("Internal server error. See the server console.", 500)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return ok(engine.snapshot())


@app.route("/api/network-info")
def api_network_info():
    snap = engine.snapshot()
    info = nu.get_system_info()
    ifaces, _ = nu.get_interfaces()
    info.update({
        "local_ipv4": snap["local_ip"],
        "ipv6": nu.get_ipv6_addresses(),
        "gateway": snap["gateway"]["ip"],
        "gateway_source": snap["gateway"]["source"],
        "selected_interface": snap["interface"],
        "mac": (snap["selected_interface"] or {}).get("mac"),
        "dns_test_domain": snap["dns"]["domain"],
        "interfaces": [{"name": i["name"], "status": i["status"], "ipv4": i["ipv4"], "mac": i["mac"]}
                       for i in ifaces],
        "note": "System DNS server addresses are not read by NetWatch; DNS is tested by resolving the configured domain.",
    })
    return ok(info)


@app.route("/api/interfaces")
def api_interfaces():
    snap = engine.snapshot()
    return ok({"interfaces": engine.interfaces, "selected": snap["interface"],
               "error": engine.interfaces_error})


@app.route("/api/latency")
def api_latency():
    window = WINDOWS.get(request.args.get("window", "5"), 300)
    return ok(engine.history(window))


@app.route("/api/dns")
def api_dns():
    return ok(engine.snapshot()["dns"])


@app.route("/api/services")
def api_services():
    snap = engine.snapshot()
    return ok({"services": snap["services"], "urls": snap["urls"]})


@app.route("/api/http-check")
def api_http_check():
    return ok({"urls": engine.snapshot()["urls"]})


@app.route("/api/diagnostics")
def api_diagnostics():
    return ok(engine.run_diagnostics())


@app.route("/api/events", methods=["GET", "DELETE"])
def api_events():
    if request.method == "DELETE":
        engine.clear_events()
    return ok({"events": engine.get_events()})


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        return ok({"settings": engine.get_settings(), "defaults": config.DEFAULT_SETTINGS,
                   "interfaces": [i["name"] for i in engine.interfaces]})
    data = request.get_json(silent=True)
    if data is None:
        return fail("Request body must be JSON.")
    clean, errors = config.validate_settings(data, engine.get_settings())
    if errors:
        return fail("Invalid settings", 400, details=errors)
    engine.update_settings(clean)
    return ok({"settings": clean, "saved": True})


def main():
    engine.start()
    print("NetWatch running at http://%s:%d  (press Ctrl+C to stop)" % (config.HOST, config.PORT))
    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
