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

    admin = User(email="admin@test.com", hashed_password=hash_password("pw"), role=UserRole.admin, is_active=True, force_password_change=False)
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
