from models import Device


def test_internal_devices_returns_assigned_devices(client, db_session):
    device = Device(
        name="test-switch",
        ip_address="10.1.1.1",
        snmp_version="2c",
        snmp_community="public",
        snmp_port=161,
        assigned_agent_id="agent-abc",
        enabled=True,
    )
    db_session.add(device)
    db_session.commit()

    resp = client.get("/internal/devices?agent_id=agent-abc")
    assert resp.status_code == 200
    devices = resp.json()
    assert len(devices) == 1
    assert devices[0]["ip"] == "10.1.1.1"
    assert devices[0]["snmp_version"] == "2c"
    assert devices[0]["snmp_community"] == "public"


def test_internal_devices_excludes_other_agents(client, db_session):
    device = Device(
        name="other-switch",
        ip_address="10.1.1.2",
        snmp_version="2c",
        snmp_community="public",
        assigned_agent_id="agent-xyz",
        enabled=True,
    )
    db_session.add(device)
    db_session.commit()

    resp = client.get("/internal/devices?agent_id=agent-abc")
    assert resp.status_code == 200
    assert resp.json() == []


def test_internal_devices_excludes_disabled(client, db_session):
    device = Device(
        name="disabled-switch",
        ip_address="10.1.1.3",
        snmp_version="2c",
        snmp_community="public",
        assigned_agent_id="agent-abc",
        enabled=False,
    )
    db_session.add(device)
    db_session.commit()

    resp = client.get("/internal/devices?agent_id=agent-abc")
    assert resp.status_code == 200
    assert resp.json() == []


def test_internal_devices_v3_device(client, db_session):
    device = Device(
        name="v3-router",
        ip_address="10.1.1.4",
        snmp_version="3",
        snmp_port=161,
        username="snmpv3user",
        auth_protocol="SHA",
        auth_password="authpass123",
        priv_protocol="AES",
        priv_password="privpass123",
        assigned_agent_id="agent-abc",
        enabled=True,
    )
    db_session.add(device)
    db_session.commit()

    resp = client.get("/internal/devices?agent_id=agent-abc")
    assert resp.status_code == 200
    devices = resp.json()
    assert len(devices) == 1
    assert devices[0]["snmp_version"] == "3"
    assert devices[0]["username"] == "snmpv3user"
    assert devices[0]["auth_password"] == "authpass123"
    assert devices[0]["snmp_community"] is None
