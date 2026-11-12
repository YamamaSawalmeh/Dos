"""
Run all three services locally (without Docker), run the client demo, then stop them.

    python run_local.py

Data is written to a fresh temporary folder, so every run starts from the seed catalog.
Each service's log is printed at the end.
"""

import os
import subprocess
import sys
import tempfile
import time

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))


def wait_until_up(url, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        try:
            requests.get(url, timeout=1)
            return True
        except requests.RequestException:
            time.sleep(0.3)
    return False


def main():
    tmp = tempfile.mkdtemp(prefix="bazar-")
    services = {
        "catalog": ({"DATA_DIR": os.path.join(tmp, "catalog")}, "http://127.0.0.1:5001/catalog"),
        "order": ({"DATA_DIR": os.path.join(tmp, "order")}, "http://127.0.0.1:5002/orders"),
        "frontend": ({}, "http://127.0.0.1:5000/info/1"),
    }
    procs, logs = {}, {}
    try:
        for name, (extra_env, health_url) in services.items():
            env = {**os.environ, **extra_env, "PYTHONUNBUFFERED": "1"}
            logs[name] = open(os.path.join(tmp, f"{name}.log"), "w+", encoding="utf-8")
            procs[name] = subprocess.Popen(
                [sys.executable, os.path.join(ROOT, name, "app.py")],
                env=env, stdout=logs[name], stderr=subprocess.STDOUT)
            if not wait_until_up(health_url):
                print(f"{name} did not start; see {logs[name].name}")
                return 1

        subprocess.run([sys.executable, os.path.join(ROOT, "client", "client.py"), "demo"])
    finally:
        for p in procs.values():
            p.terminate()
            p.wait()

    for name, f in logs.items():
        f.seek(0)
        lines = [l for l in f.read().splitlines() if f"[{name.upper()}]" in l]
        print(f"\n===== {name} log =====")
        print("\n".join(lines))
        f.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
