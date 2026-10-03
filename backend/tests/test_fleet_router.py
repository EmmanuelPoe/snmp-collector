import httpx
import pytest
from models import Alert, AlertSeverity, AlertStatus, AlertType, Device

MANAGER = "http://manager:8000"


@pytest.fixture
def fleet(db_session):
    devices = [Device(name=f"sw{i}", ip_address=f"10.0.0.{i}") for i in range(1, 6)]
    devices[4].enabled = False
    db_session.add_all(devices)
    db_session.commit()
    sw1, sw2, sw3, _sw4, sw5 = devices
    db_session.add_all(
        [
            Alert(
                device_id=sw1.id, alert_type=AlertType.device_unreachable, severity=AlertSeverity.critical, message="x"
            ),
            # sw1 also has an interface alert: it must count once, as down.
            Alert(device_id=sw1.id, alert_type=AlertType.interface_down, severity=AlertSeverity.warning, message="x"),
            Alert(
                device_id=sw2.id, alert_type=AlertType.bandwidth_threshold, severity=AlertSeverity.warning, message="x"
            ),
            # Resolved alerts and disabled devices never degrade the roll-up.
            Alert(
                device_id=sw3.id,
                alert_type=AlertType.device_unreachable,
                severity=AlertSeverity.critical,
                message="x",
                status=AlertStatus.resolved,
            ),
            Alert(
                device_id=sw5.id, alert_type=AlertType.device_unreachable, severity=AlertSeverity.critical, message="x"
            ),
        ]
    )
    db_session.commit()
    return devices


def test_summary_rolls_up_devices_alerts_agents(client, admin_headers, fleet, respx_mock):
    respx_mock.get(f"{MANAGER}/internal/agents").mock(
        return_value=httpx.Response(200, json=[{"status": "online"}, {"status": "offline"}, {"status": "online"}])
    )
    resp = client.get("/fleet/summary", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["devices"] == {"total": 5, "enabled": 4, "disabled": 1, "up": 2, "degraded": 1, "down": 1}
    assert body["alerts"] == {"open": 4, "critical": 2, "warning": 2, "info": 0, "unacknowledged": 4}
    assert body["agents"] == {"total": 3, "online": 2, "offline": 1}


def test_summary_survives_manager_outage(client, admin_headers, fleet, respx_mock):
    respx_mock.get(f"{MANAGER}/internal/agents").mock(side_effect=httpx.ConnectError("down"))
    resp = client.get("/fleet/summary", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["agents"] is None
    assert resp.json()["devices"]["down"] == 1


def test_summary_requires_auth(client):
    assert client.get("/fleet/summary").status_code == 401


def test_traffic_resolves_device_names(client, admin_headers, fleet, respx_mock):
    row = {"device_ip": "10.0.0.2", "interface_name": "Gi0/1", "in_bps": 5.0, "out_bps": 1.0, "utilization_pct": 1.5}
    unknown = {**row, "device_ip": "192.0.2.9"}
    respx_mock.get(f"{MANAGER}/internal/metrics/fleet-traffic").mock(
        return_value=httpx.Response(
            200, json={"series": [], "totals": {}, "top_by_traffic": [row, unknown], "top_by_utilization": [row]}
        )
    )
    resp = client.get("/fleet/traffic?top=2", headers=admin_headers)
    assert resp.status_code == 200
    top = resp.json()["top_by_traffic"]
    assert top[0]["device_name"] == "sw2" and top[0]["device_id"] == fleet[1].id
    assert top[1]["device_name"] == "192.0.2.9" and top[1]["device_id"] is None


def test_traffic_503_when_manager_down(client, admin_headers, respx_mock):
    respx_mock.get(f"{MANAGER}/internal/metrics/fleet-traffic").mock(side_effect=httpx.ConnectError("down"))
    assert client.get("/fleet/traffic", headers=admin_headers).status_code == 503


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>proxy error</html>"),
        httpx.Response(200, json={"series": []}),  # older payload shape
    ],
)
def test_traffic_503_on_malformed_manager_payload(client, admin_headers, respx_mock, response):
    respx_mock.get(f"{MANAGER}/internal/metrics/fleet-traffic").mock(return_value=response)
    assert client.get("/fleet/traffic", headers=admin_headers).status_code == 503
