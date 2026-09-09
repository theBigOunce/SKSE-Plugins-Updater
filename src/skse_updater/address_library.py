"""Read Address Library header identity and basic bounds, without mapping its payload.

Layout reference: CommonLibSSE-NG REL/ID.h header_t::read.
Formats 1/2 are understood. V5 remains unverified rather than guessed.
"""
import struct
from pathlib import Path

from .models import Database, version_text


def inspect_database(path, target):
    if path is None:
        return Database("missing", "Required runtime Address Library file is absent")
    path = Path(path)
    try:
        with path.open("rb") as stream:
            prefix = stream.read(24)
            if len(prefix) != 24:
                raise ValueError("Truncated database header")
            format_id, *rest = struct.unpack("<6i", prefix)
            runtime, name_length = tuple(rest[:4]), rest[4]
            if format_id not in (1, 2):
                return Database("unknown", f"Database encoding {format_id} is not yet validated",
                                str(path), format_id, runtime)
            if not 1 <= name_length <= 260:
                raise ValueError("Invalid executable name length")
            name = stream.read(name_length)
            tail = stream.read(8)
            if len(name) != name_length or len(tail) != 8:
                raise ValueError("Truncated database identity")
            pointer_size, count = struct.unpack("<2i", tail)
            if name.rstrip(b"\0").lower() != b"skyrimse.exe":
                raise ValueError("Database names a different executable")
            if runtime != target:
                raise ValueError("Database header runtime differs from the requested runtime")
            if pointer_size != 8 or not 0 < count <= 10_000_000:
                raise ValueError("Invalid pointer size or address count")
            # Every encoded address requires at least its type byte.
            if path.stat().st_size - stream.tell() < count:
                raise ValueError("Database payload is too short for its address count")
            expected = 1 if target < (1, 6, 0, 0) else 2
            if format_id != expected:
                raise ValueError("Wrong Address Library encoding for this runtime")
        return Database("valid", f"Address Library format {format_id}, {version_text(runtime)}, "
                        f"64-bit header and payload bounds checked ({count} entries)",
                        str(path), format_id, runtime, count)
    except (OSError, ValueError, struct.error) as exc:
        return Database("invalid", str(exc), str(path))
