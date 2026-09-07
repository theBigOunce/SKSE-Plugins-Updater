"""Read-only standard MO2 layout inventory; live adapter replaces guessed winners."""
import configparser
from pathlib import Path

from .models import Provider, Snapshot


def ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.read(path, encoding="utf-8-sig")
    return parser


def qt_text(value: str) -> str:
    if value.startswith("@ByteArray(") and value.endswith(")"):
        value = value[11:-1]
    return value.replace("\\\\", "\\")


def child(parent: Path, name: str) -> Path:
    """Profile/mod names must remain direct children of their configured directory."""
    if not name or name in (".", "..") or any(c in name for c in "/\\:"):
        raise ValueError("Invalid profile or mod directory name")
    return parent / name


def read_provenance(root: Path) -> tuple[str, int | None, str]:
    try:
        metadata = ini(root / "meta.ini")
        section = metadata["General"] if metadata.has_section("General") else {}
        raw = section.get("modid", "")
        mod_id = int(raw) if raw.isdecimal() and int(raw) > 0 else None
        return section.get("version", ""), mod_id, section.get("gameName", "")
    except (OSError, UnicodeError, configparser.Error):
        return "", None, ""


def collect(profile: str, game: Path, sources: list[tuple[str, Path, bool]],
            mode: str) -> Snapshot:
    result = Snapshot(profile, str(game), mode)
    winners = {}
    for name, root, managed in sources:  # low priority first, overwrite last
        if not root.is_dir():
            result.warnings.append(f"Missing provider directory: {name}")
            continue
        release, mod_id, domain = read_provenance(root) if managed else ("", None, "")
        plugins = root / "SKSE" / "Plugins"
        try:
            files = sorted(plugins.iterdir()) if plugins.is_dir() else []
            for path in files:
                if not path.is_file():
                    continue
                if path.suffix.lower() == ".dll":
                    relative = "SKSE/Plugins/" + path.name
                    provider = Provider(name, str(path), relative, managed, True, release, mod_id, domain)
                    key = relative.casefold()
                    if key in winners:
                        result.providers[winners[key]].effective = False
                    winners[key] = len(result.providers)
                    result.providers.append(provider)
                elif path.name.lower().startswith(("version-", "versionlib-")) and path.suffix.lower() == ".bin":
                    result.databases[path.name.casefold()] = str(path)
            if managed:
                root_dir = root / "Root"
                if root_dir.is_dir():
                    for path in root_dir.iterdir():
                        if path.is_file() and (path.name.lower().startswith("skse") or path.name.lower() == "skyrimse.exe"):
                            result.root_candidates.append(str(path))
        except OSError:
            result.warnings.append(f"Cannot enumerate provider: {name}")
    if result.root_candidates:
        result.warnings.append("Root-managed components detected; their effective runtime mapping is unverified")
    return result


def offline_snapshot(instance: Path, game_override: Path | None = None,
                     profile_override: str | None = None) -> Snapshot:
    config = ini(instance / "ModOrganizer.ini")
    if not config.has_section("General"):
        raise ValueError("MO2 configuration has no General section")
    general = config["General"]
    profile = profile_override or qt_text(general.get("selected_profile", ""))
    settings = config["Settings"] if config.has_section("Settings") else {}
    base = qt_text(settings.get("base_directory", str(instance))) or str(instance)
    base_path = Path(base)
    if not base_path.is_absolute():
        base_path = instance / base_path

    def configured(key: str, default: str) -> Path:
        raw = qt_text(settings.get(key, default)).replace("%BASE_DIR%", str(base_path))
        path = Path(raw)
        return path if path.is_absolute() else base_path / path

    profiles = configured("profiles_directory", "profiles")
    mods = configured("mod_directory", "mods")
    overwrite = configured("overwrite_directory", "overwrite")
    game_raw = str(game_override) if game_override else qt_text(general.get("gamePath", ""))
    if not game_raw:
        raise ValueError("No game path in MO2; supply --game")
    game = Path(game_raw)
    if not (game / "SkyrimSE.exe").is_file():
        raise ValueError("Configured game path does not contain SkyrimSE.exe")
    lines = (child(profiles, profile) / "modlist.txt").read_text(encoding="utf-8-sig").splitlines()
    enabled = [line[1:] for line in reversed(lines) if line.startswith("+")]
    sources = [("Unmanaged Data", game / "Data", False)]
    sources.extend((name, child(mods, name), True) for name in enabled)
    if overwrite.is_dir():
        sources.append(("Overwrite", overwrite, False))
    result = collect(profile, game, sources, "offline")
    result.warnings.insert(0, "Offline snapshot: standard modlist priority only; live MO2 mappings and unsaved changes are not available")
    return result
