"""Shared read-only scan engine for MO2 and offline diagnostics."""
from pathlib import Path

from . import __version__
from .compatibility import KNOWN_TARGETS, assess, environment_assessment
from .address_library import inspect_database
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
    # Root Builder files are candidates, not a verified deployment. Do not silently
    # substitute their version for the SKSE DLL actually present in the game root.
    skse_version = None
    if runtime and not snapshot.root_candidates:
        runtime_dll = game / ("skse64_" + "_".join(map(str, runtime[:3])) + ".dll")
        resource = file_version(runtime_dll)
        loader = file_version(game / "skse64_loader.exe")
        if resource and resource == loader and resource[0] == 0:
            skse_version = (*resource[1:], 0)
    suffix = "-".join(map(str, runtime)) + ".bin" if runtime else ""
    database = inspect_database(snapshot.databases.get(("versionlib-" if runtime and runtime >= (1, 6, 0, 0) else "version-") + suffix), runtime)
    snapshot.warnings.append(database.reason)
    rows = []
    for index, provider in enumerate(snapshot.providers):
        if canceled and canceled():
            raise InterruptedError("Scan canceled")
        binary = inspect_file(Path(provider.path))
        statuses = {}
        for target in targets:
            status = assess(binary, target, effective=provider.effective)
            statuses[version_text(target)] = status
        current = statuses.get(version_text(runtime), Assessment("review", "Game runtime is unknown"))
        environment = environment_assessment(binary, current, database, skse_version,
                                             effective=provider.effective, storefront=snapshot.storefront)
        if snapshot.mode == "offline" and environment.status == "supported":
            environment = Assessment("review", "Local prerequisites pass; live MO2 mappings are unverified",
                                     environment.evidence)
        rows.append(Row(provider, binary, statuses, environment))
        if progress:
            progress(index + 1, len(snapshot.providers))
    return Report(2, __version__, snapshot, runtime, components, rows)
