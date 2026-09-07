"""Shared read-only scan engine for MO2 and offline diagnostics."""
from pathlib import Path

from . import __version__
from .compatibility import KNOWN_TARGETS, assess
from .models import Assessment, Report, Row, version_text
from .pe_scan import inspect_file
from .runtime import file_version


def scan(snapshot, progress=None, canceled=None):
    game = Path(snapshot.game_path)
    runtime = file_version(game / "SkyrimSE.exe")
    targets = list(KNOWN_TARGETS)
    if runtime and runtime not in targets:
        targets.append(runtime)
    components = {}
    for path in sorted(game.glob("skse*")):
        if path.is_file() and path.suffix.lower() in (".exe", ".dll"):
            components[path.name] = version_text(file_version(path))
    for path in snapshot.root_candidates:
        components["Root candidate: " + path] = version_text(file_version(Path(path)))
    rows = []
    for index, provider in enumerate(snapshot.providers):
        if canceled and canceled():
            raise InterruptedError("Scan canceled")
        binary = inspect_file(Path(provider.path))
        statuses = {}
        for target in targets:
            suffix = "-".join(map(str, target)) + ".bin"
            present = any((prefix + suffix).casefold() in snapshot.databases for prefix in ("version-", "versionlib-"))
            status = assess(binary, target, effective=provider.effective, database_present=present)
            if status.status == "supported" and snapshot.mode == "offline":
                status = Assessment("review", "Exact runtime declared; effective MO2 mapping is not verified offline")
            statuses[version_text(target)] = status
        rows.append(Row(provider, binary, statuses))
        if progress:
            progress(index + 1, len(snapshot.providers))
    return Report(1, __version__, snapshot, runtime, components, rows)
