from crypto import decrypt_value, encrypt_value
from models import Device
from sqlalchemy import text


def test_encrypt_decrypt_roundtrip():
    token = encrypt_value("s3cr3t-community")
    assert token != "s3cr3t-community"
    assert decrypt_value(token) == "s3cr3t-community"


def test_encrypt_none_is_none():
    assert encrypt_value(None) is None
    assert decrypt_value(None) is None


def test_decrypt_legacy_plaintext_passthrough():
    # A value written before encryption is not a valid Fernet token; reads must
    # not fail — the raw value is returned verbatim.
    assert decrypt_value("public") == "public"


def test_device_credentials_stored_encrypted(db_session):
    device = Device(
        name="router-1",
        ip_address="10.0.0.1",
        snmp_version="3",
        snmp_community="private-string",
        username="netops",
        auth_password="auth-pass",
        priv_password="priv-pass",
    )
    db_session.add(device)
    db_session.commit()
    device_id = device.id
    db_session.expunge_all()

    # Raw column values bypass the ORM type decorator: they must be ciphertext.
    raw = db_session.execute(
        text("SELECT snmp_community, auth_password, priv_password FROM devices WHERE id=:id"),
        {"id": device_id},
    ).one()
    assert raw.snmp_community != "private-string"
    assert raw.auth_password != "auth-pass"
    assert raw.priv_password != "priv-pass"
    assert decrypt_value(raw.snmp_community) == "private-string"

    # Reading through the ORM transparently decrypts.
    fetched = db_session.get(Device, device_id)
    assert fetched.snmp_community == "private-string"
    assert fetched.auth_password == "auth-pass"
    assert fetched.priv_password == "priv-pass"
