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


@dataclass
class Assessment:
    status: str
    reason: str


@dataclass
class Row:
    provider: Provider
    binary: Binary
    assessments: dict[str, Assessment]


@dataclass
class Report:
    schema: int
    scanner_version: str
    snapshot: Snapshot
    runtime: Version | None
    skse_components: dict[str, str]
    rows: list[Row]
