#!/usr/bin/env python3
"""Local, read-only smart HTTP transport for Flux's GitRepository source."""
import http.server
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
BACKEND = Path(subprocess.check_output(["git", "--exec-path"], text=True).strip()) / "git-http-backend"


class Handler(http.server.BaseHTTPRequestHandler):
    def serve_git(self):
        url = urllib.parse.urlsplit(self.path)
        prefix = "/cobaltcore-deployment.git/"
        if not url.path.startswith(prefix):
            self.send_error(404)
            return
        suffix = url.path[len(prefix):]
        allowed = (self.command == "GET" and suffix == "info/refs" and url.query == "service=git-upload-pack") or (self.command == "POST" and suffix == "git-upload-pack")
        if not allowed:
            self.send_error(403, "Only Git fetch is enabled")
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > 8 * 1024 * 1024:
            self.send_error(413)
            return
        env = dict(os.environ, GIT_PROJECT_ROOT=str(ROOT), GIT_HTTP_EXPORT_ALL="1",
                   PATH_INFO="/.git/" + suffix, QUERY_STRING=url.query,
                   REQUEST_METHOD=self.command, CONTENT_TYPE=self.headers.get("Content-Type", ""),
                   CONTENT_LENGTH=str(length), REMOTE_ADDR=self.client_address[0])
        if self.headers.get("Git-Protocol"):
            env["HTTP_GIT_PROTOCOL"] = self.headers["Git-Protocol"]
        result = subprocess.run([str(BACKEND)], input=self.rfile.read(length), env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if result.returncode:
            self.send_error(502, "Git backend failed")
            return
        headers, body = result.stdout.split(b"\r\n\r\n", 1)
        fields = [line.decode().split(":", 1) for line in headers.split(b"\r\n")]
        status = next((int(value.strip().split()[0]) for key, value in fields if key.lower() == "status"), 200)
        self.send_response(status)
        for key, value in fields:
            if key.lower() != "status":
                self.send_header(key, value.strip())
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = serve_git
    do_POST = serve_git


if __name__ == "__main__":
    if "--serve" in sys.argv:
        http.server.ThreadingHTTPServer(("127.0.0.1", 19418), Handler).serve_forever()
    else:
        state = ROOT / ".local"
        state.mkdir(exist_ok=True)
        with (state / "git-source.log").open("ab") as log:
            process = subprocess.Popen([sys.executable, __file__, "--serve"],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       start_new_session=True)
        (state / "git-source.pid").write_text(str(process.pid))
        print(f"Local read-only Git HTTP source started (PID {process.pid}).")
