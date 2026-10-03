import pytest
from models import Device


@pytest.fixture
def many(db_session):
    db_session.add_all(
        [Device(name=f"core-{i:03d}", ip_address=f"10.1.{i // 250}.{i % 250 + 1}") for i in range(30)]
        + [Device(name="edge_100%", ip_address="172.16.0.1")]
    )
    db_session.commit()


def test_pages_cover_every_device_exactly_once(client, admin_headers, many):
    seen = []
    for skip in (0, 10, 20, 30):
        r = client.get("/devices", params={"skip": skip, "limit": 10}, headers=admin_headers)
        assert r.headers["X-Total-Count"] == "31"
        seen += [d["id"] for d in r.json()]
    assert len(seen) == 31 and len(set(seen)) == 31
    assert seen == sorted(seen)


def test_page_size_is_capped(client, admin_headers, many):
    assert client.get("/devices", params={"limit": 1001}, headers=admin_headers).status_code == 422
    assert client.get("/devices", params={"limit": 1000}, headers=admin_headers).status_code == 200


def test_search_matches_name_or_ip(client, admin_headers, many):
    r = client.get("/devices", params={"search": "CORE-02"}, headers=admin_headers)
    assert r.headers["X-Total-Count"] == "10"
    r = client.get("/devices", params={"search": "172.16"}, headers=admin_headers)
    assert [d["name"] for d in r.json()] == ["edge_100%"]


def test_search_treats_wildcards_literally(client, admin_headers, many):
    r = client.get("/devices", params={"search": "%"}, headers=admin_headers)
    assert [d["name"] for d in r.json()] == ["edge_100%"]
    r = client.get("/devices", params={"search": "_"}, headers=admin_headers)
    assert [d["name"] for d in r.json()] == ["edge_100%"]
