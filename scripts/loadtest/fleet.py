"""Shared by the load-test drivers: the synthetic fleet's address scheme."""


def synthetic_ip(d: int) -> str:
    return f"10.{(d >> 8) & 0xFF}.{d & 0xFF}.1"
