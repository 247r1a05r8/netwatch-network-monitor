"""Tiny local service for the NetWatch demo: http://127.0.0.1:5001

Start it, add 127.0.0.1 port 5001 in NetWatch > Configuration, then stop it
with Ctrl+C to see SERVICE DOWN, and start it again to see SERVICE RESTORED.
"""
from flask import Flask

svc = Flask(__name__)


@svc.route("/")
def home():
    return "NetWatch demo test service is running."


if __name__ == "__main__":
    print("Demo service on http://127.0.0.1:5001 (Ctrl+C to stop)")
    svc.run(host="127.0.0.1", port=5001, debug=False)
