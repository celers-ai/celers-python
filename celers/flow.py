"""A Celers automation written in Python: the same board the canvas shows.

    from celers import Flow

    flow = Flow("Invoices")
    rows = flow.excel_read("Invoices.xlsx", sheet="Invoices", variable="invoices")
    with flow.for_each(rows) as row:
        flow.step("navigate", url="https://portal.example/invoices")
        flow.step("type", selector="#number", text=row["Invoice"])
    flow.ask_person("Approve the totals?", kind="approve")
    flow.save("invoices.celers.json")

Each step is a step of the canvas (``celers.steps()`` lists them, with their settings); a step the canvas does not
have, or a setting it does not take, is refused here, not when the board opens. ``Flow.load`` reads a saved board
(or one exported from the app) and ``to_python`` writes it back as code, so a board a person built and a flow a
developer wrote are the same thing both ways.
"""
from __future__ import annotations

import json
import keyword
import re
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

FORMAT = "celers.flow"
VERSION = 1
#: Settings a control step carries that its own panel edits (not in the registry's form fields).
CONTROL_SETTINGS = {"for": {"loop"}, "if": {"condition", "conditions"}, "elif": {"condition", "conditions"},
                    "while": {"condition", "conditions"}, "do_while": {"condition", "conditions"}}
#: Settings every step may carry (the canvas adds them to any step).
COMMON_SETTINGS = {"continueOnError", "comment", "disabled", "retries", "timeout"}


class FlowError(ValueError):
    pass


def _catalogue() -> Dict[str, Dict[str, Any]]:
    text = resources.files("celers").joinpath("catalogue.json").read_text(encoding="utf-8")
    return json.loads(text)["steps"]


_STEPS: Optional[Dict[str, Dict[str, Any]]] = None


def steps() -> Dict[str, Dict[str, Any]]:
    """Every step type Celers offers: {type: {"label", "settings", "ports", "engine"}}."""
    global _STEPS
    if _STEPS is None:
        _STEPS = _catalogue()
    return _STEPS


class Var(str):
    """A value an earlier step saved (``{{name}}`` on the board); ``row["Column"]`` inside a loop."""

    def __getitem__(self, column):  # type: ignore[override]
        if isinstance(column, str):
            return Var("{{" + f'{self.strip("{}")}["{column}"]' + "}}")
        return str.__getitem__(self, column)


class Flow:
    def __init__(self, name: str, description: str = "", strict: bool = True):
        if not str(name or "").strip():
            raise FlowError("A flow needs a name.")
        self.name, self.description, self.strict = str(name).strip(), description, strict
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        self._ids: Dict[str, int] = {}
        # The line the next step goes on (a block's node and its port; (None, None) is the main line), and on each
        # line the last node with the port the step after it leaves from ("next" after a loop or an If).
        self._line: Tuple[Optional[str], Optional[str]] = (None, None)
        self._last: Dict[Tuple[Optional[str], Optional[str]], Tuple[str, Optional[str]]] = {}

    # ── adding steps ────────────────────────────────────────────────────────────────────────────────
    def _id(self, kind: str) -> str:
        n = self._ids.get(kind, 0) + 1
        self._ids[kind] = n
        return f"py-{kind}-{n}"

    def _check(self, kind: str, config: Dict[str, Any]) -> None:
        known = steps()
        if kind not in known:
            near = [k for k in known if k.startswith(kind[:4])][:5]
            raise FlowError(f"Celers has no step {kind!r}" + (f" (did you mean {', '.join(near)}?)" if near else ""))
        allowed = set(known[kind]["settings"]) | CONTROL_SETTINGS.get(kind, set()) | COMMON_SETTINGS
        unknown = sorted(set(config) - allowed)
        if unknown and self.strict:
            raise FlowError(f"{kind} does not take {', '.join(unknown)} (it takes: "
                            f"{', '.join(sorted(allowed)) or 'nothing'})")

    def step(self, kind: str, label: str = "", /, **config: Any) -> str:
        """Add a step of type ``kind`` with its settings; returns its id. Values are kept as the canvas keeps
        them (text); ``{{name}}`` uses what an earlier step saved."""
        self._check(kind, config)
        nid = self._id(kind)
        cfg = {k: (v if isinstance(v, (dict, list)) else ("" if v is None else str(v))) for k, v in config.items()}
        self.nodes.append({"id": nid, "type": kind, "position": {"x": 0, "y": 0},
                           "data": {"type": kind, "label": label or steps()[kind]["label"], "config": cfg}})
        prev = self._last.get(self._line)
        source, handle = prev if prev else self._line
        if source:
            self.edges.append({"id": f"e-{source}-{nid}-{handle or ''}", "source": source, "target": nid,
                               "sourceHandle": handle})
        self._last[self._line] = (nid, None)
        return nid

    @contextmanager
    def _block(self, nid: str, port: str) -> Iterator[None]:
        outer = self._line
        self._line = (nid, port)
        try:
            yield
        finally:
            self._line = outer
            self._last[outer] = (nid, "next")  # the step after the block comes out of its "next" port

    # ── control ─────────────────────────────────────────────────────────────────────────────────────
    @contextmanager
    def for_each(self, rows: Union[str, Var], label: str = "", variable: str = "row") -> Iterator[Var]:
        """The steps inside run once for each row of ``rows`` (what an earlier step saved)."""
        name = str(rows).strip("{} ")
        nid = self.step("for", label or f"For each row of {name}", loop={"iterable": name, "variable": variable})
        with self._block(nid, "body"):
            yield Var("{{" + variable + "}}")

    @contextmanager
    def when(self, condition: Dict[str, Any], label: str = "") -> Iterator[None]:
        """The steps inside run only when ``condition`` holds (the canvas's If; its condition as the If's panel
        writes it, e.g. {"left": "{{total}}", "operator": ">", "right": "5000"})."""
        nid = self.step("if", label or "If", condition=condition)
        with self._block(nid, "true"):
            yield

    # ── common steps ────────────────────────────────────────────────────────────────────────────────
    def navigate(self, url: str, label: str = "") -> str:
        return self.step("navigate", label, url=url)

    def excel_read(self, path: str, sheet: str = "", variable: str = "rows", label: str = "") -> Var:
        self.step("excel_read", label, path=path, sheet=sheet, variable=variable)
        return Var("{{" + variable + "}}")

    def excel_write(self, path: str, rows: Union[str, Var], sheet: str = "", if_exists: str = "replace",
                    label: str = "") -> str:
        return self.step("excel_write", label, path=path, sheet=sheet, variable=str(rows).strip("{} "),
                         ifExists=if_exists)

    def ask_person(self, question: str, kind: str = "approve", label: str = "", **more: Any) -> str:
        return self.step("ask_person", label, question=question, kind=kind, **more)

    def log(self, message: str, label: str = "") -> str:
        return self.step("log", label, message=message)

    # ── the board ───────────────────────────────────────────────────────────────────────────────────
    def graph(self) -> Dict[str, Any]:
        """The board: {"nodes", "edges"}, laid out top to bottom (the canvas keeps any layout it is given)."""
        y = {}
        for i, n in enumerate(self.nodes):
            y[n["id"]] = i
        nodes = [dict(n, position={"x": 0, "y": 120 * y[n["id"]]}) for n in self.nodes]
        return {"nodes": nodes, "edges": [dict(e) for e in self.edges]}

    def to_dict(self) -> Dict[str, Any]:
        return {"format": FORMAT, "version": VERSION, "name": self.name, "description": self.description,
                "graph": self.graph()}

    def save(self, path: Union[str, Path]) -> Path:
        p = Path(path)
        p.write_text(json.dumps(self.to_dict(), indent=1, ensure_ascii=False), encoding="utf-8")
        return p

    @classmethod
    def from_graph(cls, graph: Dict[str, Any], name: str = "Board", strict: bool = False) -> "Flow":
        """A board (the canvas's graph, as the app saves or exports it) as a Flow."""
        f = cls(name, strict=strict)
        f.nodes = [dict(n) for n in graph.get("nodes") or []]
        f.edges = [dict(e) for e in graph.get("edges") or []]
        return f

    @classmethod
    def load(cls, path: Union[str, Path]) -> "Flow":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("format") == FORMAT:
            f = cls.from_graph(data.get("graph") or {}, data.get("name") or "Board")
            f.description = data.get("description") or ""
            return f
        return cls.from_graph(data.get("graph") or data, Path(path).stem)

    def to_python(self) -> str:
        """The board as Python that makes it again (canvas to code)."""
        return to_python(self)


# ── canvas to code ──────────────────────────────────────────────────────────────────────────────────

def _kw(config: Dict[str, Any]) -> str:
    parts = []
    for k, v in config.items():
        if k.isidentifier() and not keyword.iskeyword(k):
            parts.append(f"{k}={v!r}")
    extra = {k: v for k, v in config.items() if not (k.isidentifier() and not keyword.iskeyword(k))}
    if extra:
        parts.append(f"**{extra!r}")
    return ", ".join(parts)


def to_python(flow: Flow) -> str:
    by_id = {n["id"]: n for n in flow.nodes}
    out_edges: Dict[Tuple[str, Optional[str]], str] = {}
    targets = set()
    for e in flow.edges:
        out_edges[(e["source"], e.get("sourceHandle") or None)] = e["target"]
        targets.add(e["target"])
    lines = ["from celers import Flow", "", f"flow = Flow({flow.name!r}, strict=False)"]

    def chain(start: Optional[str], indent: int, seen: set) -> None:
        nid = start
        pad = "    " * indent
        while nid and nid not in seen and nid in by_id:
            seen.add(nid)
            n = by_id[nid]
            data = n.get("data") or {}
            kind = data.get("type") or n.get("type")
            label = data.get("label") or ""
            cfg = dict(data.get("config") or {})
            if kind == "for":
                loop = cfg.get("loop") or {}
                lines.append(f"{pad}with flow.for_each({str(loop.get('iterable') or '')!r}, label={label!r}, "
                             f"variable={str(loop.get('variable') or 'row')!r}) as row:")
                body = out_edges.get((nid, "body"))
                if body:
                    chain(body, indent + 1, seen)
                else:
                    lines.append(f"{pad}    pass")
                nid = out_edges.get((nid, "next"))
                continue
            if kind == "if":
                lines.append(f"{pad}with flow.when({cfg.get('condition') or {}!r}, label={label!r}):")
                side = out_edges.get((nid, "true"))
                if side:
                    chain(side, indent + 1, seen)
                else:
                    lines.append(f"{pad}    pass")
                nid = out_edges.get((nid, "next"))
                continue
            args = f"{kind!r}, {label!r}" + (", " + _kw(cfg) if cfg else "")
            lines.append(f"{pad}flow.step({args})")
            nid = out_edges.get((nid, None))

    roots = [n["id"] for n in flow.nodes if n["id"] not in targets]
    seen: set = set()
    for r in roots:
        chain(r, 0, seen)
    lines += ["", f"flow.save({re.sub(r'[^a-z0-9]+', '_', flow.name.lower()).strip('_') + '.celers.json'!r})", ""]
    return "\n".join(lines)
