from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .demo import build_demo_plan_summary
from .jellyfish_base import inspect_jellyfish_base
from .studio import build_stage_index, build_studio_status


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json({"status": "ok", "engine": "LuminAI", "workflow": [stage.id for stage in build_stage_index(build_demo_plan_summary())]})
            return
        if self.path == "/demo/closed-loop-plan":
            self._json(build_demo_plan_summary())
            return
        if self.path == "/api/studio/status":
            self._json(build_studio_status(build_demo_plan_summary(), inspect_jellyfish_base()))
            return
        if self.path == "/api/jellyfish/base-status":
            self._json(inspect_jellyfish_base().as_dict())
            return
        if self.path == "/":
            self._html(_dashboard_html())
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, payload: dict[str, object]) -> None:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _html(self, html: str) -> None:
        raw = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def create_server(host: str = "127.0.0.1", port: int = 8799) -> HTTPServer:
    return HTTPServer((host, port), _Handler)


def _dashboard_html() -> str:
    return """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>LuminAI Studio Dashboard</title></head>
<body>
  <main>
    <h1>LuminAI Studio Dashboard</h1>
    <section><h2>Stage Index</h2><div id="stages"></div></section>
    <section><h2>Shot Workbench</h2><div id="shots"></div></section>
  </main>
</body>
</html>"""

