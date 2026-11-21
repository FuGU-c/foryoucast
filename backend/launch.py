"""Run the prebuilt demo in one terminal so the browser can reconnect to it."""
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "/api/bootstrap", timeout=0.5) as response:
            payload = json.load(response)
        return isinstance(payload, dict) and bool(payload.get("catalog_version")) and "profiles" in payload
    except (OSError, ValueError, urllib.error.URLError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    if not all((ROOT / path).exists() for path in ("dist/index.html", "data/catalog.json")):
        print("The frontend build or catalog is missing. Run the setup in README.md.")
        return 1
    if ready(url):
        print(f"Seranews is already running at {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    worker = None
    with (ROOT / "data" / "launcher-api.log").open("a", encoding="utf-8") as api_log:
        api = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.server:app", "--host", "127.0.0.1", "--port", str(args.port)],
            cwd=ROOT, stdout=api_log, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(40):
                if api.poll() is not None:
                    break
                if ready(url):
                    break
                time.sleep(0.25)
            else:
                print("Seranews did not start. See data/launcher-api.log.")
                return 1
            if api.poll() is not None:
                print("Seranews could not bind its port or start. See data/launcher-api.log.")
                return 1
            with (ROOT / "data" / "launcher-worker.log").open("a", encoding="utf-8") as worker_log:
                worker = subprocess.Popen(
                    [sys.executable, "-m", "backend.worker"], cwd=ROOT,
                    stdout=worker_log, stderr=subprocess.STDOUT,
                )
                print(f"Seranews is ready at {url}. Keep this window open while using the demo.", flush=True)
                if not args.no_browser:
                    webbrowser.open(url)
                return api.wait()
        except KeyboardInterrupt:
            return 0
        finally:
            for process in (worker, api):
                if process is not None and process.poll() is None:
                    process.terminate()


if __name__ == "__main__":
    sys.exit(main())
