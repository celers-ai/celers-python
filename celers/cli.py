"""celers steps [TYPE]              the steps Celers offers, or one step's settings
celers python BOARD.json [OUT.py]  a board saved from the app (or a .celers.json) as Python
celers upload FLOW.celers.json     the flow as a project in the Celers app on this computer"""
from __future__ import annotations

import json
import sys

from . import Client, Flow, steps


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = args[0]
    if cmd == "steps":
        cat = steps()
        if len(args) > 1:
            s = cat.get(args[1])
            if not s:
                print(f"No step {args[1]!r}.")
                return 1
            print(json.dumps(s, indent=1))
        else:
            for k in sorted(cat):
                print(f"{k:28} {cat[k]['label']}")
        return 0
    if cmd == "python" and len(args) > 1:
        code = Flow.load(args[1]).to_python()
        if len(args) > 2:
            open(args[2], "w", encoding="utf-8").write(code)
        else:
            print(code)
        return 0
    if cmd == "upload" and len(args) > 1:
        print(Client().upload(Flow.load(args[1])))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
