---
phase: 1
plan: 1.1
title: "Database migrations: add v3 fields, drop metrics tables"
wave: 1
depends_on: []
autonomous: true
files_modified:
  - backend/alembic/versions/006_add_v3_fields_drop_metrics.py
  - backend/models.py
requirements:
  - BE-01
  - BE-06
must_haves:
  goal: "Alembic migrations apply cleanly from scratch with v3 device fields present and metrics tables gone"
  truths:
    - "devices table has columns: username, auth_protocol, auth_password, priv_protocol, priv_password, assigned_agent_id — all nullable"
    - "snmp_metrics table does not exist in the database after upgrade"
    - "if_mib_metrics table does not exist in the database after upgrade"
    - "Alembic reports migration 006 as current head with no pending upgrades"
    - "models.py Device class reflects the six new nullable columns"
    - "models.py has no SNMPMetric or IfMibMetric classes"
---

<objective>
Create Alembic migration 006 that adds six nullable v3 SNMP credential columns and the agent assignment column to `devices`, and drops the `snmp_metrics` and `if_mib_metrics` tables. Update `models.py` to match.

Purpose: The new agent-based architecture stores no metrics in Postgres. Devices need v3 credential fields so agents can receive complete SNMP config. These are structural prerequisites for all other Phase 1 work.

Output:
- `backend/alembic/versions/006_add_v3_fields_drop_metrics.py` — forward-only migration
- `backend/models.py` — updated with new Device columns, SNMPMetric and IfMibMetric classes removed
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
</context>

<interfaces>
<!-- Current Alembic chain: 001_initial → 002_add_snmp_module → 003_multi_module_support → 004_add_metric_module → 005_add_if_mib_table -->
<!-- New migration must set: down_revision = '005_add_if_mib_table' -->

<!-- Current Device columns (from models.py): id, name, ip_address, snmp_version, snmp_community, snmp_port, snmp_modules, device_type, description, enabled, created_at, updated_at -->
<!-- Relationships to REMOVE from Device: metrics, if_mib_metrics -->
<!-- Relationship to KEEP: schedules -->

<!-- Tables to DROP in migration upgrade(): snmp_metrics (has hypertable + indexes), if_mib_metrics (has indexes) -->
<!-- Indexes on snmp_metrics: ix_snmp_metrics_device_id, ix_snmp_metrics_interface_name, ix_snmp_metrics_oid, ix_snmp_metrics_timestamp -->
<!-- Indexes on if_mib_metrics: ix_if_mib_metrics_device_id, ix_if_mib_metrics_timestamp, ix_if_mib_metrics_interface_name -->
<!-- snmp_metrics has a TimescaleDB hypertable — op.drop_table() works on hypertables with CASCADE -->
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Write Alembic migration 006</name>
  <files>backend/alembic/versions/006_add_v3_fields_drop_metrics.py</files>
  <read_first>
    - backend/alembic/versions/005_add_if_mib_table.py — to confirm down_revision value and understand index naming conventions
    - backend/alembic/versions/001_initial.py — to understand how snmp_metrics and its indexes were created
  </read_first>
  <action>
Create `backend/alembic/versions/006_add_v3_fields_drop_metrics.py` with the following exact content:

```python
"""Add v3 SNMP fields to devices, drop metrics tables

Revision ID: 006_add_v3_fields_drop_metrics
Revises: 005_add_if_mib_table
Create Date: 2026-05-02

"""
from alembic import op
import sqlalchemy as sa

revision = '006_add_v3_fields_drop_metrics'
down_revision = '005_add_if_mib_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add v3 credential columns to devices (all nullable — existing devices remain valid)
    op.add_column('devices', sa.Column('username', sa.String(length=255), nullable=True))
    op.add_column('devices', sa.Column('auth_protocol', sa.String(length=10), nullable=True))
    op.add_column('devices', sa.Column('auth_password', sa.String(length=255), nullable=True))
    op.add_column('devices', sa.Column('priv_protocol', sa.String(length=10), nullable=True))
    op.add_column('devices', sa.Column('priv_password', sa.String(length=255), nullable=True))
    op.add_column('devices', sa.Column('assigned_agent_id', sa.String(length=255), nullable=True))

    # Drop if_mib_metrics indexes then table
    op.drop_index('ix_if_mib_metrics_interface_name', table_name='if_mib_metrics')
    op.drop_index('ix_if_mib_metrics_timestamp', table_name='if_mib_metrics')
    op.drop_index('ix_if_mib_metrics_device_id', table_name='if_mib_metrics')
    op.drop_table('if_mib_metrics')

    # Drop snmp_metrics indexes then table (TimescaleDB hypertable — DROP TABLE handles it)
    op.drop_index('ix_snmp_metrics_timestamp', table_name='snmp_metrics')
    op.drop_index('ix_snmp_metrics_oid', table_name='snmp_metrics')
    op.drop_index('ix_snmp_metrics_interface_name', table_name='snmp_metrics')
    op.drop_index('ix_snmp_metrics_device_id', table_name='snmp_metrics')
    op.drop_table('snmp_metrics')


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported: metrics data was intentionally discarded")
```

Key points:
- `assigned_agent_id` is `String(255)` not Integer — it stores the string agent_id issued by the manager, not a Postgres FK
- `downgrade()` raises intentionally — this is a destructive migration with no prod data to restore (per architecture decision)
- Drop indexes BEFORE tables (Alembic/Postgres requires this for explicit index objects)
- TimescaleDB hypertable: `op.drop_table('snmp_metrics')` drops the hypertable and its chunks; no extra CASCADE call needed at the SQLAlchemy op level
  </action>
  <verify>
    <automated>python -c "import ast, sys; ast.parse(open('backend/alembic/versions/006_add_v3_fields_drop_metrics.py').read()); print('syntax ok')"</automated>
  </verify>
  <done>
    - File exists at backend/alembic/versions/006_add_v3_fields_drop_metrics.py
    - `revision = '006_add_v3_fields_drop_metrics'` present
    - `down_revision = '005_add_if_mib_table'` present
    - `op.add_column('devices', ...)` called 6 times (username, auth_protocol, auth_password, priv_protocol, priv_password, assigned_agent_id)
    - `op.drop_table('snmp_metrics')` present
    - `op.drop_table('if_mib_metrics')` present
    - `downgrade()` raises NotImplementedError
  </done>
</task>

<task type="auto">
  <name>Task 2: Update models.py to match migration</name>
  <files>backend/models.py</files>
  <read_first>
    - backend/models.py — read full file before editing; must see all imports and relationships
    - backend/routers/metrics.py — to identify all imports of SNMPMetric/IfMibMetric that will break and must be noted
    - backend/services/collector.py — same reason
  </read_first>
  <action>
Rewrite `backend/models.py` to:

1. Remove the `SNMPMetric` class entirely (lines 31–47)
2. Remove the `IfMibMetric` class entirely (lines 50–84)
3. Remove `BigInteger` from the SQLAlchemy import line (no longer needed)
4. On the `Device` class:
   - Remove `metrics` relationship (references deleted SNMPMetric)
   - Remove `if_mib_metrics` relationship (references deleted IfMibMetric)
   - Keep `schedules` relationship unchanged
   - Add six new columns after `updated_at`:
     ```python
     username = Column(String(255), nullable=True)
     auth_protocol = Column(String(10), nullable=True)
     auth_password = Column(String(255), nullable=True)
     priv_protocol = Column(String(10), nullable=True)
     priv_password = Column(String(255), nullable=True)
     assigned_agent_id = Column(String(255), nullable=True)
     ```

5. Keep `CollectionConfig` and `CollectionSchedule` classes unchanged.

After editing, the import line should read:
```python
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
```
(Float is still needed by nothing currently — remove it too if no remaining class uses it; both SNMPMetric used Float. Check CollectionConfig and CollectionSchedule — neither uses Float. Remove Float.)

Final import line:
```python
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
```
  </action>
  <verify>
    <automated>python -c "
import sys; sys.path.insert(0, 'backend')
# Patch settings before import
import os; os.environ.setdefault('POSTGRES_USER','x'); os.environ.setdefault('POSTGRES_PASSWORD','x'); os.environ.setdefault('POSTGRES_DB','x')
from models import Device, CollectionConfig, CollectionSchedule
assert hasattr(Device, 'username'), 'missing username'
assert hasattr(Device, 'auth_protocol'), 'missing auth_protocol'
assert hasattr(Device, 'assigned_agent_id'), 'missing assigned_agent_id'
try:
    from models import SNMPMetric
    print('FAIL: SNMPMetric still exists')
    sys.exit(1)
except ImportError:
    pass
print('models.py ok')
"</automated>
  </verify>
  <done>
    - `Device` has 6 new columns: username, auth_protocol, auth_password, priv_protocol, priv_password, assigned_agent_id
    - `SNMPMetric` class does not exist in models.py
    - `IfMibMetric` class does not exist in models.py
    - `Device.metrics` relationship does not exist in models.py
    - `Device.if_mib_metrics` relationship does not exist in models.py
    - `Device.schedules` relationship still present
    - File parses without syntax errors
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| migration runtime → Postgres | Migration runs with DB superuser credentials during deploy |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-1.1-01 | Tampering | 006 migration downgrade | accept | downgrade() raises NotImplementedError by design; destructive-only migration is documented in code comment |
| T-1.1-02 | Information Disclosure | auth_password / priv_password columns | accept | Postgres-level encryption out of scope for Phase 1; columns store values passed by operator at device creation |
</threat_model>

<verification>
After both tasks complete, verify end-to-end migration integrity:

```bash
# Check migration file exists and is syntactically valid
python -c "import ast; ast.parse(open('backend/alembic/versions/006_add_v3_fields_drop_metrics.py').read()); print('ok')"

# Check Alembic can read the chain (no DB connection needed for this)
cd backend && python -m alembic heads 2>&1

# Verify models import cleanly
cd backend && python -c "
import os; os.environ.setdefault('POSTGRES_USER','x'); os.environ.setdefault('POSTGRES_PASSWORD','x'); os.environ.setdefault('POSTGRES_DB','x')
from models import Device, CollectionConfig, CollectionSchedule
cols = [c.key for c in Device.__table__.columns]
assert 'username' in cols
assert 'assigned_agent_id' in cols
assert 'snmp_metrics' not in [t for t in Device.metadata.tables]
assert 'if_mib_metrics' not in [t for t in Device.metadata.tables]
print('all checks passed')
"
```
</verification>

<success_criteria>
- `backend/alembic/versions/006_add_v3_fields_drop_metrics.py` exists with correct revision chain
- `backend/models.py` has Device with 6 new nullable columns and no SNMPMetric/IfMibMetric classes
- `python -m alembic heads` shows `006_add_v3_fields_drop_metrics (head)` when run from backend/
- No syntax errors in either file
</success_criteria>

<output>
After completion, create `.planning/phases/01-backend-foundation/01-1.1-SUMMARY.md`
</output>
