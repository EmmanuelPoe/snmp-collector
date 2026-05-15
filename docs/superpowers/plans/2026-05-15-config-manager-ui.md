# Configuration Manager UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken ConfigurationManager UI (which calls 6 non-existent endpoints) with a working OID collection config manager backed by real backend endpoints.

**Architecture:** The `CollectionConfig` table (Postgres) is the actual config mechanism — it stores the OID rows the agent collects. We add `PUT /config/configs/{id}` and `DELETE /config/configs/{id}` to the backend, rewrite `ConfigurationManager.js` to manage these rows (list, add, enable/disable, delete), and remove all the dead schedule/YAML-editor API stubs from `api.js`. The "Schedules" and "Module YAML Editor" sections in the existing frontend don't match the current architecture and will be replaced.

**Tech Stack:** FastAPI + SQLAlchemy + SQLite (tests) for backend; React + axios for frontend; pytest for backend tests; `docker-compose exec backend pytest` to run.

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Modify | `backend/schemas.py` | Add `CollectionConfigUpdate` schema |
| Modify | `backend/routers/config.py` | Add `PUT /config/configs/{id}` and `DELETE /config/configs/{id}` |
| Create | `backend/tests/test_config_router.py` | Full test coverage for config endpoints |
| Modify | `frontend/src/services/api.js` | Remove 7 dead stubs; add `updateConfig`, `deleteConfig` |
| Modify | `frontend/src/components/ConfigurationManager.js` | Rewrite: OID config table + add modal + modules list |

---

## Task 1: Add `CollectionConfigUpdate` schema to `backend/schemas.py`

**Files:**
- Modify: `backend/schemas.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_config_router.py` with a test that calls `PUT /config/configs/1` and expects it to work (this will fail because the endpoint doesn't exist yet).

```python
# backend/tests/test_config_router.py
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
import config
config.settings.database_url = "sqlite:///:memory:"
config.settings.jwt_secret = "test-secret"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from database import Base, get_db
from auth import hash_password
from models import User, UserRole, CollectionConfig


@pytest.fixture(scope="function")
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "jwt_secret", "test-secret")
    monkeypatch.setattr(config.settings, "manager_api_key", "mgr-key")
    monkeypatch.setattr(config.settings, "frontend_url", "http://localhost")
    engine = create_engine(f"sqlite:///{tmp_path}/cfg.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    admin = User(email="admin@test.com", hashed_password=hash_password("pw"), role=UserRole.admin, is_active=True)
    session.add(admin)
    session.commit()

    from main import app
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()


@pytest.fixture
def admin_token(client):
    resp = client.post("/auth/login", data={"username": "admin@test.com", "password": "pw"})
    return resp.json()["access_token"]


@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def test_list_configs_empty(client, auth):
    resp = client.get("/config/configs", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_config(client, auth):
    resp = client.post("/config/configs", json={
        "oid": "1.3.6.1.2.1.2.2.1.10",
        "oid_name": "ifInOctets",
        "description": "Inbound octets",
        "enabled": True,
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["oid"] == "1.3.6.1.2.1.2.2.1.10"
    assert data["oid_name"] == "ifInOctets"
    assert data["enabled"] is True
    assert "id" in data


def test_create_config_duplicate_oid_rejected(client, auth):
    client.post("/config/configs", json={"oid": "1.3.6.1.2.1.1.1.0", "oid_name": "sysDescr", "enabled": True}, headers=auth)
    resp = client.post("/config/configs", json={"oid": "1.3.6.1.2.1.1.1.0", "oid_name": "sysDescr", "enabled": True}, headers=auth)
    assert resp.status_code == 409


def test_update_config_enabled(client, auth):
    create = client.post("/config/configs", json={"oid": "1.3.6.1.2.1.2.2.1.10", "oid_name": "ifInOctets", "enabled": True}, headers=auth)
    config_id = create.json()["id"]
    resp = client.put(f"/config/configs/{config_id}", json={"enabled": False}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_update_config_not_found(client, auth):
    resp = client.put("/config/configs/999", json={"enabled": False}, headers=auth)
    assert resp.status_code == 404


def test_delete_config(client, auth):
    create = client.post("/config/configs", json={"oid": "1.3.6.1.2.1.2.2.1.10", "oid_name": "ifInOctets", "enabled": True}, headers=auth)
    config_id = create.json()["id"]
    resp = client.delete(f"/config/configs/{config_id}", headers=auth)
    assert resp.status_code == 204
    # Confirm gone
    list_resp = client.get("/config/configs", headers=auth)
    assert all(c["id"] != config_id for c in list_resp.json())


def test_delete_config_not_found(client, auth):
    resp = client.delete("/config/configs/999", headers=auth)
    assert resp.status_code == 404


def test_list_modules(client, auth):
    resp = client.get("/config/modules", headers=auth)
    assert resp.status_code == 200
    assert "if_mib" in resp.json()


def test_config_requires_auth(client):
    resp = client.get("/config/configs")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker-compose exec backend pytest tests/test_config_router.py -v
```

Expected: `test_update_config_enabled` and `test_delete_config` FAIL with 405 (method not allowed) or 404 — the PUT and DELETE endpoints don't exist yet.

- [ ] **Step 3: Add `CollectionConfigUpdate` to `backend/schemas.py`**

Add after the `CollectionConfigCreate` class (around line 92):

```python
class CollectionConfigUpdate(BaseModel):
    oid_name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
```

- [ ] **Step 4: Commit the test file and schema change**

```bash
git add backend/tests/test_config_router.py backend/schemas.py
git commit -m "test: add config router tests; add CollectionConfigUpdate schema"
```

---

## Task 2: Add `PUT` and `DELETE` endpoints to `backend/routers/config.py`

**Files:**
- Modify: `backend/routers/config.py`

- [ ] **Step 1: Add the two endpoints**

Replace the full content of `backend/routers/config.py` with:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from auth import get_current_user, require_role
from database import get_db
from models import CollectionConfig, User
from schemas import CollectionConfigCreate, CollectionConfigResponse, CollectionConfigUpdate
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["configuration"])

SUPPORTED_MODULES = ["if_mib", "host_resources", "ucd_snmp", "cisco_memory", "cisco_cpu"]


@router.get("/modules")
def list_modules(_: User = Depends(get_current_user)):
    return SUPPORTED_MODULES


@router.get("/configs", response_model=List[CollectionConfigResponse])
def list_configs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(CollectionConfig).all()


@router.post("/configs", response_model=CollectionConfigResponse, status_code=status.HTTP_201_CREATED)
def create_config(
    config: CollectionConfigCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    existing = db.query(CollectionConfig).filter(CollectionConfig.oid == config.oid).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Config for OID {config.oid} already exists")
    db_config = CollectionConfig(**config.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


@router.put("/configs/{config_id}", response_model=CollectionConfigResponse)
def update_config(
    config_id: int,
    updates: CollectionConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    db_config = db.query(CollectionConfig).filter(CollectionConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(db_config, field, value)
    db.commit()
    db.refresh(db_config)
    return db_config


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_config(
    config_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    db_config = db.query(CollectionConfig).filter(CollectionConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    db.delete(db_config)
    db.commit()
```

- [ ] **Step 2: Run tests to verify all pass**

```bash
docker-compose exec backend pytest tests/test_config_router.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 3: Run full backend test suite to check for regressions**

```bash
docker-compose exec backend pytest tests/ -v
```

Expected: All tests pass (previously passing tests remain green).

- [ ] **Step 4: Commit**

```bash
git add backend/routers/config.py
git commit -m "feat(backend): add PUT and DELETE /config/configs/{id} endpoints"
```

---

## Task 3: Update `frontend/src/services/api.js` — remove dead stubs, add real config calls

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 1: Replace the Configuration section (lines 80–112)**

Find the `// ===== Configuration =====` block and replace it entirely:

```js
// ===== Configuration =====
export const getModules = async () => {
    const response = await api.get('/config/modules');
    return response.data;
};
export const getConfigs = async () => {
    const response = await api.get('/config/configs');
    return response.data;
};
export const createConfig = async (configData) => {
    const response = await api.post('/config/configs', configData);
    return response.data;
};
export const updateConfig = async (configId, updates) => {
    const response = await api.put(`/config/configs/${configId}`, updates);
    return response.data;
};
export const deleteConfig = async (configId) => {
    await api.delete(`/config/configs/${configId}`);
};
```

Remove these 7 functions entirely (they call endpoints that don't exist and never will):
- `getModuleConfig`
- `updateModuleConfig`
- `getSchedules`
- `getSchedule`
- `updateSchedule`
- `createSchedule`
- `reloadConfig`

- [ ] **Step 2: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "refactor(frontend): replace dead config API stubs with real OID config calls"
```

---

## Task 4: Rewrite `frontend/src/components/ConfigurationManager.js`

**Files:**
- Modify: `frontend/src/components/ConfigurationManager.js`

The existing component references the 7 removed API functions and renders a schedule table + YAML editor that have no working backend. Replace it entirely with an OID config manager: a table of `CollectionConfig` rows with enable/disable toggles and delete, plus an "Add OID" modal.

- [ ] **Step 1: Replace the full file**

```jsx
import React, { useState, useEffect, useCallback } from 'react';
import { getModules, getConfigs, createConfig, updateConfig, deleteConfig } from '../services/api';
import { useToast } from '../hooks/useToast';

const EMPTY_FORM = { oid: '', oid_name: '', description: '', enabled: true };

export default function ConfigurationManager() {
  const { showToast } = useToast();
  const [modules, setModules] = useState([]);
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [m, c] = await Promise.all([getModules(), getConfigs()]);
      setModules(m);
      setConfigs(c);
    } catch {
      showToast('Failed to load configuration', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { load(); }, [load]);

  const handleToggle = async (cfg) => {
    try {
      const updated = await updateConfig(cfg.id, { enabled: !cfg.enabled });
      setConfigs(prev => prev.map(c => c.id === cfg.id ? updated : c));
    } catch {
      showToast('Failed to update config', 'error');
    }
  };

  const handleDelete = async (cfg) => {
    if (!window.confirm(`Delete OID config "${cfg.oid_name}" (${cfg.oid})?`)) return;
    try {
      await deleteConfig(cfg.id);
      setConfigs(prev => prev.filter(c => c.id !== cfg.id));
      showToast('Config deleted', 'success');
    } catch {
      showToast('Failed to delete config', 'error');
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const created = await createConfig(form);
      setConfigs(prev => [...prev, created]);
      setShowModal(false);
      setForm(EMPTY_FORM);
      showToast(`OID "${form.oid_name}" added`, 'success');
    } catch (err) {
      showToast('Error: ' + (err.response?.data?.detail || 'Failed to create config'), 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="loading-center"><div className="spinner" /></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Configuration</div>
          <div className="page-subtitle">Manage OID collection configs and supported modules</div>
        </div>
      </div>

      {/* OID Collection Configs */}
      <div className="card" style={{ marginBottom: 16, padding: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: '1px solid var(--color-border)' }}>
          <div>
            <div className="page-title" style={{ fontSize: 13 }}>OID Collection Configs</div>
            <div className="page-subtitle">Which OIDs the agent collects from each device.</div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>+ Add OID</button>
        </div>
        {configs.length === 0 ? (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--color-text-faint)' }}>
            No OID configs defined. Add one to start collecting metrics.
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>OID Name</th>
                <th>OID</th>
                <th>Description</th>
                <th>Enabled</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {configs.map(cfg => (
                <tr key={cfg.id}>
                  <td style={{ fontWeight: 500 }}>{cfg.oid_name}</td>
                  <td className="font-mono text-sm text-muted">{cfg.oid}</td>
                  <td className="text-sm text-muted">{cfg.description || '—'}</td>
                  <td>
                    <button
                      className={`btn btn-sm ${cfg.enabled ? 'btn-secondary' : 'btn-primary'}`}
                      onClick={() => handleToggle(cfg)}
                    >
                      {cfg.enabled ? 'Disable' : 'Enable'}
                    </button>
                  </td>
                  <td>
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete(cfg)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Supported Modules */}
      <div className="card">
        <div className="page-title" style={{ fontSize: 13, marginBottom: 4 }}>Supported Modules</div>
        <div className="page-subtitle" style={{ marginBottom: 12 }}>
          SNMP module groups available for collection. Assign modules to devices via Device Management.
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {modules.map(mod => (
            <span key={mod} className="badge" style={{ fontSize: 12, padding: '4px 10px' }}>{mod}</span>
          ))}
        </div>
      </div>

      {/* Add OID Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Add OID Collection Config</h3>
              <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label className="form-label">OID</label>
                <input className="input" required placeholder="e.g. 1.3.6.1.2.1.2.2.1.10"
                  value={form.oid}
                  onChange={e => setForm({ ...form, oid: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">OID Name</label>
                <input className="input" required placeholder="e.g. ifInOctets"
                  value={form.oid_name}
                  onChange={e => setForm({ ...form, oid_name: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">Description (optional)</label>
                <input className="input" placeholder="e.g. Inbound octets per interface"
                  value={form.description}
                  onChange={e => setForm({ ...form, description: e.target.value })} />
              </div>
              <div className="form-group">
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={form.enabled}
                    onChange={e => setForm({ ...form, enabled: e.target.checked })} />
                  <span className="form-label" style={{ margin: 0 }}>Enable immediately</span>
                </label>
              </div>
              <div className="action-buttons">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Adding...' : 'Add OID'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ConfigurationManager.js
git commit -m "feat(frontend): rewrite ConfigurationManager with working OID config management"
```

---

## Task 5: Build, deploy, and verify

- [ ] **Step 1: Rebuild backend and frontend containers**

```bash
make build
```

Expected: Both `backend` and `frontend` images rebuild without errors.

- [ ] **Step 2: Start services**

```bash
make up
```

Expected: All services start. Check with `docker-compose ps` — all should be `Up`.

- [ ] **Step 3: Verify backend endpoints directly**

```bash
# Login to get a token
TOKEN=$(curl -s -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@localhost&password=admin" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# List configs (should be empty initially)
curl -s http://localhost/api/config/configs -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Create a config
curl -s -X POST http://localhost/api/config/configs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"oid":"1.3.6.1.2.1.2.2.1.10","oid_name":"ifInOctets","description":"Inbound octets","enabled":true}' | python3 -m json.tool

# List again — should show the new entry
curl -s http://localhost/api/config/configs -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: Empty list, then the created entry, then one-item list.

- [ ] **Step 4: Verify frontend in browser**

Open `http://localhost` → login as `admin@localhost` / `admin` → click **Configuration** in sidebar.

Check:
- Page loads without errors (no broken spinner or crash)
- "No OID configs defined" empty state shown if no configs exist
- "Add OID" button opens modal
- Fill in OID, OID Name, Description → submit → row appears in table
- "Disable" button on row → button changes to "Enable", (visually toggled)
- "Delete" button → confirm dialog → row disappears
- **Supported Modules** section shows the 5 module badge pills

- [ ] **Step 5: Final commit (if any last touch-ups needed)**

```bash
git add -A
git commit -m "chore: post-deploy verification clean-up (if any)"
```

---

## Self-Review Notes

- All 9 test cases in `test_config_router.py` cover: list empty, create, duplicate OID rejection, update enabled, update not found, delete, delete not found, list modules, unauthenticated access.
- `CollectionConfigUpdate` uses `exclude_unset=True` so partial updates (just `enabled`) don't wipe other fields.
- Dead API stubs removed: `getModuleConfig`, `updateModuleConfig`, `getSchedules`, `getSchedule`, `updateSchedule`, `createSchedule`, `reloadConfig` — none of these have backend implementations and the schedule/YAML-editor concepts don't match the architecture.
- Frontend `window.confirm` used for delete — consistent with existing pattern in `DeviceManagement.js`.
- No new DB migrations needed — `CollectionConfig` table already exists.
