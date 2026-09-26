#!/usr/bin/env python3
"""Vendor shared/ modules into each service (Step 5.1 / plan Step 35).

Each Python service (backend, manager, agent) has a flat module layout and its
own Docker build context, so shared code is vendored as byte-identical copies
rather than widening every build context. This script regenerates those copies;
`scripts/check_shared.py` verifies they match (run in CI). Run after editing any
file under shared/:

    python scripts/sync_shared.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHARED = REPO / "shared"
SERVICES = ("backend", "manager", "agent")

# Files under shared/ that get vendored into each service (module name -> keep).
VENDORED = ["logging_json.py"]


def main() -> int:
    for name in VENDORED:
        source = SHARED / name
        content = source.read_bytes()
        for service in SERVICES:
            dest = REPO / service / name
            dest.write_bytes(content)
            print(f"synced {source.relative_to(REPO)} -> {dest.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
