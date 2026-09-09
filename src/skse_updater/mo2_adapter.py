"""Read-only MO2 calls, captured on the GUI thread before binary work starts."""
from pathlib import Path

from .inventory import collect
from .models import Provider
from .updates import apply_update


def live_snapshot(organizer):
    import mobase
    game = Path(organizer.managedGame().gameDirectory().absolutePath())
    mods = organizer.modList()
    sources = [("Unmanaged Data", game / "Data", False)]
    names = sorted(mods.allMods(), key=mods.priority)
    for name in names:
        if mods.state(name) & mobase.ModState.ACTIVE:
            mod = mods.getMod(name)
            if mod:
                sources.append((name, Path(mod.absolutePath()), True))
    overwrite = Path(organizer.overwritePath())
    if overwrite.is_dir():
        sources.append(("Overwrite", overwrite, False))
    snapshot = collect(organizer.profileName(), game, sources, "live MO2")
    for provider in snapshot.providers:
        mod = mods.getMod(provider.mod) if provider.managed else None
        if mod and callable(getattr(mod, "newestVersion", None)):
            newest = mod.newestVersion()
            if newest.isValid():
                apply_update(provider, newest.canonicalString(), source="MO2 in-memory cache")
    relative_paths = {p.relative.casefold(): p.relative for p in snapshot.providers}
    # Include file-mapper providers that are absent from ordinary mod directories.
    for info in organizer.findFileInfos("SKSE/Plugins", lambda f: str(f.filePath).lower().endswith(".dll")):
        name = Path(info.filePath).name
        relative_paths.setdefault(("SKSE/Plugins/" + name).casefold(), "SKSE/Plugins/" + name)
    by_path = {str(Path(p.path).resolve()).casefold(): p for p in snapshot.providers}
    for key, relative in relative_paths.items():
        actual = organizer.resolvePath(relative)
        for provider in snapshot.providers:
            if provider.relative.casefold() == key:
                provider.effective = (str(Path(provider.path).resolve()).casefold() == str(Path(actual).resolve()).casefold()) if actual else None
        if actual and str(Path(actual).resolve()).casefold() not in by_path:
            snapshot.providers.append(Provider("MO2 virtual provider", actual, relative, False, True))
    snapshot.databases.clear()
    for info in organizer.findFileInfos("SKSE/Plugins", lambda f: str(f.filePath).lower().endswith(".bin")):
        name = Path(info.filePath).name
        if name.lower().startswith(("version-", "versionlib-")):
            actual = organizer.resolvePath("SKSE/Plugins/" + name)
            if actual:
                snapshot.databases[name.casefold()] = actual
    snapshot.capabilities = {
        "nexus_metadata_bridge": callable(getattr(organizer, "createNexusBridge", None)),
        "nexus_download_service": callable(getattr(organizer.downloadManager(), "startDownloadNexusFile", None)),
    }
    return snapshot
