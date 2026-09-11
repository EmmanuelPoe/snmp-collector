"""Password strength policy (Step 6.1).

Enforced on password change and admin user-creation. Default policy is length
(>= settings.password_min_length) plus rejection of common passwords and of the
account's own email local-part — the checks that actually reduce guessability.
Character-class requirements are opt-in (settings.password_require_classes)
because forced classes push users toward predictable "Password1!" shapes.
"""

from config import settings

# A compact list of the most-guessed passwords + obvious app-specific ones.
# Not exhaustive by design (a full corpus belongs in a file/service); it catches
# the values that dominate credential-stuffing lists. Compared case-insensitively.
_COMMON_PASSWORDS = {
    "password", "password1", "password123", "passw0rd", "123456", "1234567",
    "12345678", "123456789", "1234567890", "12345", "qwerty", "qwerty123",
    "qwertyuiop", "abc123", "111111", "123123", "000000", "iloveyou",
    "admin", "administrator", "root", "letmein", "welcome", "welcome1",
    "monkey", "dragon", "master", "login", "princess", "solo", "starwars",
    "changeme", "change-me", "secret", "default", "guest", "test", "test123",
    "snmp", "snmppass", "snmp_metrics", "collector", "grafana", "prometheus",
    "football", "baseball", "superman", "batman", "trustno1", "sunshine",
    "michael", "shadow", "ashley", "whatever", "hello", "hello123",
    "google", "aaaaaa", "666666", "121212", "654321", "1q2w3e4r", "zaq12wsx",
}


class PasswordPolicyError(ValueError):
    """Raised when a password fails the policy. Message is user-facing."""


def validate_password(password: str, email: str | None = None) -> None:
    """Raise PasswordPolicyError with an actionable message if `password` is weak."""
    problems: list[str] = []

    if len(password) < settings.password_min_length:
        problems.append(f"be at least {settings.password_min_length} characters")

    if password.lower() in _COMMON_PASSWORDS:
        problems.append("not be a commonly used password")

    if email:
        local = email.split("@", 1)[0].strip().lower()
        if local and len(local) >= 3 and local in password.lower():
            problems.append("not contain your email name")

    if settings.password_require_classes:
        classes = [
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        ]
        if sum(classes) < 3:
            problems.append("include at least three of: lowercase, uppercase, digit, symbol")

    if problems:
        raise PasswordPolicyError("Password must " + "; ".join(problems) + ".")
