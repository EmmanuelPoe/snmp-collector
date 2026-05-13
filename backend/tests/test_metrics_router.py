import pytest
import httpx
from models import Device


@pytest.fixture
def device(db_session):
    d = Device(name="test-switch", ip_address="10.0.0.1")
    db_session.add(d)
    db_session.commit()
    db_session.refresh(d)
    return d


def test_rates_proxy_returns_manager_response(client, admin_headers, device, respx_mock):
    manager_payload = {
        "interfaces": {
            "Gi0/1": {
                "status": "up",
                "speed_bps": 1000000000,
                "current_in_bps": 800000.0,
                "current_out_bps": 200000.0,
                "utilization_pct": 0.08,
                "error_count": 0,
                "sparkline": [],
            }
        }
    }
    respx_mock.get("http://manager:8000/internal/metrics/rates").mock(
        return_value=httpx.Response(200, json=manager_payload)
    )

    resp = client.get(f"/metrics/rates/{device.id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "Gi0/1" in data["interfaces"]
    assert data["interfaces"]["Gi0/1"]["current_in_bps"] == 800000.0


def test_rates_proxy_404_for_unknown_device(client, admin_headers):
    resp = client.get("/metrics/rates/9999", headers=admin_headers)
    assert resp.status_code == 404


def test_rates_proxy_requires_auth(client, device):
    resp = client.get(f"/metrics/rates/{device.id}")
    assert resp.status_code == 401
