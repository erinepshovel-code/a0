from __future__ import annotations

import json
import sys
from uuid import uuid4

from .contract import A0Request
from .router import handle

def main() -> None:
    raw = open(sys.argv[1], "r", encoding="utf-8").read() if len(sys.argv) > 1 else sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}

    req = A0Request(
        task_id=data.get("task_id") or f"task_{uuid4().hex[:12]}",
        input=data.get("input") or {"text": "", "files": [], "metadata": {}},
        tools_allowed=data.get("tools_allowed") or ["none"],
        mode=data.get("mode") or "analyze",
        hmm=data.get("hmm") or ["hmm"],
    )

    resp = handle(req)
    print(json.dumps(resp.__dict__, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
