"""Serializable scanner facts. No credentials or full INI contents are retained."""
from dataclasses import dataclass, field

Version = tuple[int, int, int, int]


def version_text(value: Version | None) -> str:
    return ".".join(map(str, value)) if value else "Unknown"


def unpack_version(value: int) -> Version:
    return value >> 24, (value >> 16) & 255, (value >> 4) & 4095, value & 15


@dataclass
class Declaration:
    schema: int
    plugin_version: int
    name: str
    flags_ex: int
    flags: int
    runtimes: list[Version]
    minimum_skse: int


@dataclass
class Binary:
    sha256: str = ""
    machine: int = 0
    exports: list[str] = field(default_factory=list)
    declaration: Declaration | None = None
    error: str = ""
    timestamp: int = 0


@dataclass
class Provider:
    mod: str
    path: str
    relative: str
    managed: bool = True
    effective: bool | None = None
    release: str = ""
    mod_id: int | None = None
    game_domain: str = ""
    newest_release: str = ""
    update_checked_at: str = ""
    update_status: str = "unknown"
    update_reason: str = "No Nexus version information"
    update_source: str = "MO2 cache"


@dataclass
class Snapshot:
    profile: str
    game_path: str
    mode: str
    providers: list[Provider] = field(default_factory=list)
    databases: dict[str, str] = field(default_factory=dict)
    root_candidates: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    capabilities: dict[str, bool] = field(default_factory=dict)
    storefront: str = "unknown"


@dataclass
class Assessment:
    status: str
    reason: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class Row:
    provider: Provider
    binary: Binary
    assessments: dict[str, Assessment]
    environment: Assessment = field(default_factory=lambda: Assessment("review", "Environment not assessed"))


@dataclass
class Report:
    schema: int
    scanner_version: str
    snapshot: Snapshot
    runtime: Version | None
    skse_components: dict[str, str]
    rows: list[Row]


@dataclass
class Database:
    status: str
    reason: str
    path: str = ""
    format: int | None = None
    runtime: Version | None = None
    entries: int = 0
