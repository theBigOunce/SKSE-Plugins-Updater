"""Update availability is independent of runtime compatibility and file selection."""
import re
from datetime import datetime, timezone


def numeric_version(value):
    # Only compare unambiguous release numbers; do not guess beta/date/version schemes.
    value = value.strip()
    if not re.fullmatch(r"[vV]?\d+(?:\.\d+){0,7}", value):
        return None
    parts = [int(p) for p in value.lstrip("vV").split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def update_status(installed, newest):
    if not newest.strip():
        return "unknown", "Nexus version has not been checked"
    current, available = numeric_version(installed), numeric_version(newest)
    if installed.strip() == newest.strip() and installed.strip():
        return "current", "Installed and reported versions match; compatible files may still differ"
    if current is None or available is None:
        return "unknown", "Version labels differ but cannot be ordered reliably"
    width = max(len(current), len(available))
    current += (0,) * (width - len(current))
    available += (0,) * (width - len(available))
    if available > current:
        return "available", "A newer mod-page release is reported; its files may not support your runtime"
    if available == current:
        return "current", "No newer mod-page release is reported"
    return "ahead", "Installed version sorts above Nexus; metadata or release branches may differ"


def apply_update(provider, newest, checked_at="", source="MO2 cache"):
    provider.newest_release = newest
    provider.update_checked_at = checked_at
    provider.update_source = source
    if not provider.managed or not provider.mod_id:
        provider.update_status = "unknown"
        provider.update_reason = "No reliable Nexus mod identity"
    else:
        provider.update_status, provider.update_reason = update_status(provider.release, newest)


def nexus_game(domain):
    if domain.casefold() in ("skyrimse", "skyrim special edition", "skyrimspecialedition"):
        return "skyrimspecialedition"
    return None


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
