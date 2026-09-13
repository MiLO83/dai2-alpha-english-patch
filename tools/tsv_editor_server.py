#!/usr/bin/env python3
"""Local-only web bridge for the Dai-2 Alpha TSV editor and ISO builder."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
WORK = ROOT / "work" / "web-editor"
TABLE = WORK / "current-translation.tsv"
ISO = ROOT / "build" / "SLPS-25228-English-web-edited.iso"
PATCH = ROOT / "build" / "SLPS-25228-English-web-edited.xdelta"
ORIGINAL = ROOT / "original" / "SLPS-25228.iso"
MAX_TABLE_BYTES = 32 * 1024 * 1024

state_lock = threading.Lock()
state: dict[str, str] = {"state": "idle", "log": "", "output": ""}


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(8 * 1024 * 1024):
            result.update(block)
    return result.hexdigest()


def start_job(command: list[str], output: Path) -> bool:
    with state_lock:
        if state["state"] == "running":
            return False
        state.update(state="running", log="", output=str(output))

    def worker() -> None:
        try:
            process = subprocess.Popen(
                command, cwd=ROOT, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                with state_lock:
                    state["log"] = (state["log"] + line)[-200_000:]
            code = process.wait()
            with state_lock:
                if code == 0 and output.exists():
                    state["state"] = "complete"
                    state["log"] += f"\nOutput: {output}\nSHA-256: {digest(output)}\n"
                else:
                    state["state"] = "failed"
                    state["log"] += f"\nCommand exited with status {code}.\n"
        except Exception as error:  # surfaced to the local UI
            with state_lock:
                state["state"] = "failed"
                state["log"] += f"\n{type(error).__name__}: {error}\n"

    threading.Thread(target=worker, daemon=True).start()
    return True


class Handler(BaseHTTPRequestHandler):
    server_version = "Dai2TSVEditor/1.0"

    def send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/tsv-editor.html"):
            self.send_bytes((TOOLS / "tsv-editor.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/tsv-editor-extra.js":
            self.send_bytes((TOOLS / "tsv-editor-extra.js").read_bytes(), "text/javascript; charset=utf-8")
        elif path == "/api/status":
            with state_lock:
                body = json.dumps(state).encode()
            self.send_bytes(body, "application/json")
        else:
            self.send_bytes(b"Not found\n", "text/plain", 404)

    def do_POST(self) -> None:  # noqa: N802
        origin = self.headers.get("Origin", "")
        if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}",
                                    f"http://localhost:{self.server.server_port}"}:
            self.send_bytes(b"Rejected non-local origin\n", "text/plain", 403)
            return
        path = urlparse(self.path).path
        if path == "/api/build":
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= MAX_TABLE_BYTES:
                self.send_bytes(b"Invalid TSV size\n", "text/plain", 400)
                return
            body = self.rfile.read(length)
            first = body.decode("utf-8-sig", errors="strict").splitlines()[0].split("\t")
            valid = ["Original Japanese", "Automatic Translation", "English"]
            paged = valid + ["English Page 2", "English Page 3"]
            if first not in (["Scope"] + valid, valid, ["Scope"] + paged, paged):
                self.send_bytes(b"Invalid TSV headers\n", "text/plain", 400)
                return
            if not ORIGINAL.exists():
                self.send_bytes(f"Missing original ISO: {ORIGINAL}\n".encode(), "text/plain", 400)
                return
            WORK.mkdir(parents=True, exist_ok=True)
            TABLE.write_bytes(body)
            ISO.parent.mkdir(parents=True, exist_ok=True)
            command = [str(TOOLS / "build-web-edited-iso.sh"), str(TABLE), str(ORIGINAL), str(ISO)]
            if not start_job(command, ISO):
                self.send_bytes(b"Another build is already running\n", "text/plain", 409)
                return
            self.send_bytes(b'{"started":true}', "application/json", 202)
        elif path == "/api/generate-patch":
            if not ISO.exists():
                self.send_bytes(b"Build an ISO with Apply Patch first\n", "text/plain", 400)
                return
            xdelta = TOOLS / "xdelta3"
            command = [str(xdelta), "-f", "-e", "-s", str(ORIGINAL), str(ISO), str(PATCH)]
            if not start_job(command, PATCH):
                self.send_bytes(b"Another build is already running\n", "text/plain", 409)
                return
            self.send_bytes(b'{"started":true}', "application/json", 202)
        else:
            self.send_bytes(b"Not found\n", "text/plain", 404)

    def log_message(self, pattern: str, *args: object) -> None:
        print(pattern % args)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Dai-2 Alpha TSV editor: {url}")
    print("Press Ctrl+C to stop the local server.")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEditor stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
