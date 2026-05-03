def test_add_device_returns_501(client, auth_headers):
    resp = client.post("/devices", json={}, headers=auth_headers)
    assert resp.status_code == 501

def test_list_devices_returns_501(client, auth_headers):
    resp = client.get("/devices", headers=auth_headers)
    assert resp.status_code == 501

def test_delete_device_returns_501(client, auth_headers):
    resp = client.delete("/devices/some-id", headers=auth_headers)
    assert resp.status_code == 501

def test_devices_no_auth_returns_403(client):
    resp = client.get("/devices")
    assert resp.status_code == 403
