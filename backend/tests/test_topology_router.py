"""Tests for the Step 13 topology router: graph read + LLDP discovery."""

from models import Alert, AlertStatus, AlertType, Device, TopologyEdge


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_graph_reports_nodes_edges_and_status(client, db_session, admin_headers):
    d1 = Device(name="sw1", ip_address="10.0.0.1", enabled=True)
    d2 = Device(name="sw2", ip_address="10.0.0.2", enabled=True)
    db_session.add_all([d1, d2])
    db_session.commit()
    db_session.add(
        TopologyEdge(local_device_id=d1.id, remote_device_id=d2.id, local_port="Gi0/0", remote_port_desc="Gi0/1")
    )
    db_session.add(TopologyEdge(local_device_id=d1.id, remote_sysname="external-router", remote_chassis_id="aa:bb:cc"))
    # d2 has an open unreachable alert -> should render as "down"
    db_session.add(
        Alert(alert_type=AlertType.device_unreachable, message="x", device_id=d2.id, status=AlertStatus.open)
    )
    db_session.commit()

    r = client.get("/topology/graph", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()

    status_by_id = {n["id"]: n["status"] for n in data["nodes"]}
    assert status_by_id[d1.id] == "up"
    assert status_by_id[d2.id] == "down"

    assert len(data["edges"]) == 1
    assert data["edges"][0]["source"] == d1.id
    assert data["edges"][0]["target"] == d2.id

    assert len(data["unresolved"]) == 1
    assert data["unresolved"][0]["remote_sysname"] == "external-router"


def test_discover_walks_lldp_and_resolves_neighbours(client, db_session, admin_headers, monkeypatch):
    import routers.topology as topology

    d1 = Device(name="sw1", ip_address="10.0.0.1", enabled=True)
    d2 = Device(name="sw2", ip_address="10.0.0.2", enabled=True)
    db_session.add_all([d1, d2])
    db_session.commit()

    monkeypatch.setattr(topology.time, "sleep", lambda *_: None)
    monkeypatch.setattr(topology, "_resolve_agent_id", lambda device: "agent1")

    def fake_post(url, json=None, headers=None, timeout=None):
        devid = json["params"]["device"]["id"]
        return _FakeResp({"command_id": f"cmd{devid}"})

    def fake_get(url, headers=None, timeout=None):
        cid = url.rsplit("/", 1)[-1]
        if cid == f"cmd{d1.id}":
            # sw1 sees sw2 (resolvable) and an unknown neighbour
            result = [
                {
                    "remote_sysname": "sw2",
                    "remote_port_id": "Gi0/1",
                    "remote_chassis_id": "de:ad",
                    "local_port_desc": "Gi0/0",
                },
                {
                    "remote_sysname": "unknown-host",
                    "remote_port_id": "Gi9",
                    "remote_chassis_id": "be:ef",
                    "local_port_desc": "Gi0/9",
                },
            ]
        else:
            result = []
        return _FakeResp({"status": "done", "result": result})

    monkeypatch.setattr(topology.httpx, "post", fake_post)
    monkeypatch.setattr(topology.httpx, "get", fake_get)

    r = client.post("/topology/discover", headers=admin_headers)
    assert r.status_code == 200
    summary = r.json()
    assert summary["devices_walked"] == 2
    assert summary["edges"] == 2

    edges = db_session.query(TopologyEdge).filter(TopologyEdge.local_device_id == d1.id).all()
    resolved = [e for e in edges if e.remote_device_id is not None]
    unresolved = [e for e in edges if e.remote_device_id is None]
    assert len(resolved) == 1 and resolved[0].remote_device_id == d2.id
    assert len(unresolved) == 1 and unresolved[0].remote_sysname == "unknown-host"
