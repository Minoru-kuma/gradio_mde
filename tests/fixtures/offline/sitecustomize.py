"""Opt-in test-only Python socket egress guard (also inherited by workers).

Enable with MDE_TEST_DENY_EGRESS=1 and this directory on PYTHONPATH. Chrome
requests are independently blocked by BrowserHarness routes. This is an offline
acceptance aid, not an operating-system network sandbox.
"""
import ipaddress
import os
import sys


if os.environ.get("MDE_TEST_DENY_EGRESS") == "1":
    def record(message):
        path = os.environ.get("MDE_TEST_OFFLINE_LOG")
        if path:
            with open(path, "a") as stream:
                stream.write(f"{os.getpid()} {message}\n")

    def loopback(host):
        if host in (None, "localhost", b"localhost"):
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def audit(event, args):
        if event == "socket.connect" and isinstance(args[1], tuple):
            host = args[1][0]
        elif event == "socket.getaddrinfo":
            host = args[0]
        else:
            return
        if not loopback(host):
            record("blocked " + event)
            raise OSError("Offline acceptance: non-loopback socket disabled")

    sys.addaudithook(audit)
    record("offline-guard-active")
