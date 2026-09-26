#!/usr/bin/env python3
"""Assert vendored shared/ copies are byte-identical to the source (Step 5.1).

Run in CI (lint job). Exits non-zero and names the drifted files if any service's
copy differs from shared/ — run `python scripts/sync_shared.py` to fix.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHARED = REPO / "shared"
SERVICES = ("backend", "manager", "agent")
VENDORED = ["logging_json.py"]


def main() -> int:
    drifted: list[str] = []
    for name in VENDORED:
        source = (SHARED / name).read_bytes()
        for service in SERVICES:
            dest = REPO / service / name
            if not dest.exists() or dest.read_bytes() != source:
                drifted.append(str(dest.relative_to(REPO)))
    if drifted:
        print("Vendored shared/ copies are out of sync with shared/:")
        for path in drifted:
            print(f"  - {path}")
        print("\nRun: python scripts/sync_shared.py")
        return 1
    print("shared/ vendored copies are in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
