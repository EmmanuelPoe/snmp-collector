# shared/

Source of truth for code shared across the Python services (backend, manager,
agent). Because each service has a flat module layout and its own Docker build
context, these modules are **vendored** as byte-identical copies into each
service rather than widening every build context.

- `logging_json.py` — structured JSON logging, the correlation-ID contextvar, the
  ASGI `CorrelationMiddleware`, and outbound-header helpers (Step 5.1).

## Workflow

Edit the file here, then regenerate the copies:

```bash
python scripts/sync_shared.py
```

CI (the `lint` job) runs `python scripts/check_shared.py`, which fails if any
service's copy has drifted. Never edit `backend/logging_json.py`,
`manager/logging_json.py`, or `agent/logging_json.py` directly.
