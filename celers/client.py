"""The Celers app on this computer (or a Celers workspace), reached with the person's own sign-in.

    from celers import Client
    app = Client()                       # the desktop app on this computer, its address and key from CELERS_URL /
                                         # CELERS_TOKEN, or Client("http://127.0.0.1:8000", token="...")
    project = app.upload(flow)           # a project with the flow as its board: open it in the app, run, schedule

Nothing here runs automations itself: the app does, under the person's plan (its computers, its schedules, its
assistant allowance). The token is the app's own sign-in token; it is sent only to the address given.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .flow import Flow

DEFAULT_URL = "http://127.0.0.1:8000"


class CelersError(RuntimeError):
    pass


class Client:
    def __init__(self, url: str = "", token: str = "", timeout: float = 30.0):
        self.url = (url or os.environ.get("CELERS_URL") or DEFAULT_URL).rstrip("/")
        self.token = token or os.environ.get("CELERS_TOKEN") or ""
        self.timeout = timeout

    def _call(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                text = r.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code == 401:
                raise CelersError("The Celers app refused the sign-in: set CELERS_TOKEN to your sign-in token.") from None
            if exc.code == 402:
                raise CelersError(f"Your Celers plan does not allow this: {detail}") from None
            raise CelersError(f"{method} {path}: {exc.code} {detail}") from None
        except urllib.error.URLError as exc:
            raise CelersError(f"The Celers app does not answer at {self.url} ({exc.reason}). Is it open?") from None
        return json.loads(text) if text else None

    def projects(self) -> List[Dict[str, Any]]:
        got = self._call("GET", "/api/projects/")
        return got if isinstance(got, list) else (got or {}).get("projects", [])

    def upload(self, flow: Flow, project_id: str = "") -> str:
        """The flow as a project's board: a new project named after it, or ``project_id``'s board replaced.
        Returns the project's id."""
        if not project_id:
            made = self._call("POST", "/api/projects/", {"name": flow.name, "description": flow.description})
            project_id = str((made or {}).get("id") or (made or {}).get("project", {}).get("id") or "")
            if not project_id:
                raise CelersError("The app did not make the project.")
        self._call("POST", "/api/workflow/canvas-graph", {"p_id": project_id, "graph": flow.graph()})
        return project_id

    def download(self, project_id: str) -> Flow:
        """A project's board as a Flow (``to_python()`` writes it as code)."""
        got = self._call("GET", f"/api/workflow/canvas-graph/{project_id}") or {}
        name = next((p.get("name") for p in self.projects() if p.get("id") == project_id), "") or "Board"
        return Flow.from_graph(got.get("graph") or {}, name)
