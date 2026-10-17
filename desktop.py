"""Local Windows launcher; also runnable as a regular Python script."""
import argparse
import socket
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from app import app


def open_when_ready(url, stopped):
    for _ in range(100):
        if stopped.is_set():
            return
        try:
            with urllib.request.urlopen(url + "/health", timeout=0.5) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    print("Browser did not open automatically. Open the address shown above.")


def main():
    parser = argparse.ArgumentParser(description="Thread Studio local application")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    stopped = threading.Event()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        # Keep the socket bound to avoid a race when selecting a free port.
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        print(f"Thread Studio: {url}", flush=True)
        print("Keep this window open. Press Ctrl+C to quit.", flush=True)
        if not args.no_browser:
            threading.Thread(target=open_when_ready, args=(url, stopped), daemon=True).start()
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", loop="asyncio", http="h11", ws="none", lifespan="on"
        ))
        try:
            server.run(sockets=[listener])
        finally:
            stopped.set()


if __name__ == "__main__":
    main()
