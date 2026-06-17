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


def test_export_csv_returns_summary(client, admin_headers, device, respx_mock):
    summary = {"interfaces": {
        "Gi0/1": {"max_in_bps": 900.0, "avg_in_bps": 100.0, "max_out_bps": 50.0,
                  "avg_out_bps": 25.0, "speed_bps": 1000, "max_utilization_pct": 90.0,
                  "avg_utilization_pct": 10.0, "samples": 12},
        "Gi0/2": {"max_in_bps": 0.0, "avg_in_bps": 0.0, "max_out_bps": 0.0,
                  "avg_out_bps": 0.0, "speed_bps": None, "max_utilization_pct": None,
                  "avg_utilization_pct": None, "samples": 0},
    }}
    respx_mock.get("http://manager:8000/internal/metrics/summary").mock(
        return_value=httpx.Response(200, json=summary)
    )

    resp = client.get(f"/metrics/export/csv/{device.id}", params={"hours": 720}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "test-switch_bandwidth_720h.csv" in resp.headers["content-disposition"]
    body = resp.text.strip().splitlines()
    assert body[0] == "interface,max_in_bps,avg_in_bps,max_out_bps,avg_out_bps,speed_bps,max_utilization_pct,avg_utilization_pct,samples"
    assert body[1].startswith("Gi0/1,900.0,100.0,50.0,25.0,1000,90.0,10.0,12")
    # null speed/util render as empty fields, not "None"
    assert body[2] == "Gi0/2,0.0,0.0,0.0,0.0,,,,0"


def test_export_csv_404_for_unknown_device(client, admin_headers):
    assert client.get("/metrics/export/csv/9999", headers=admin_headers).status_code == 404


def test_rates_proxy_requires_auth(client, device):
    resp = client.get(f"/metrics/rates/{device.id}")
    assert resp.status_code == 401
