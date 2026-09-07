"""Conservative initial compatibility policy; declarations are not crash guarantees."""
from .models import Assessment, Binary, Version

KNOWN_TARGETS = ((1, 5, 97, 0), (1, 6, 1170, 0), (1, 7, 99, 0))


def assess(binary: Binary, target: Version, *, effective: bool | None = True,
           database_present: bool = False) -> Assessment:
    if effective is False:
        return Assessment("shadowed", "Another provider wins this DLL path")
    if binary.error:
        return Assessment("review", binary.error)
    if binary.machine != 0x8664:
        return Assessment("incompatible", "Not an AMD64 DLL")
    if not any(name.startswith("SKSEPlugin_") for name in binary.exports):
        return Assessment("helper", "No SKSE entry point; may be an auxiliary DLL")
    if effective is None:
        return Assessment("review", "Effective file origin could not be resolved")
    declaration = binary.declaration
    if not declaration:
        return Assessment("review", "Legacy/query-only DLL; runtime support cannot be inferred from exports")
    if declaration.flags & ~7 or declaration.flags_ex & ~3:
        return Assessment("review", "Unknown compatibility flags")
    if target not in KNOWN_TARGETS:
        return Assessment("review", "Runtime/storefront is outside the validated policy targets")
    if not {"SKSEPlugin_Load", "SKSEPlugin_Preload"}.intersection(binary.exports):
        return Assessment("review", "Metadata present but no SKSE load entry point")
    independent = bool(declaration.flags & 3)
    if not independent and target not in declaration.runtimes:
        return Assessment("incompatible", "Explicit runtime declaration excludes this version")
    if declaration.flags & 1 and not database_present:
        return Assessment("incompatible", "Required runtime Address Library file is absent")
    if target >= (1, 7, 99, 0):
        return Assessment("review", "1.7.99 loader/V5 rules need release-matched validation")
    if independent:
        return Assessment("review", "Declares runtime independence; database encoding/ABI still need validation")
    if declaration.minimum_skse:
        return Assessment("review", "Runtime listed; minimum SKSE requirement still needs verification")
    if declaration.flags or declaration.flags_ex:
        return Assessment("review", "Runtime listed with additional ABI flags requiring verification")
    return Assessment("supported", "Exact runtime listed in DLL declaration; does not verify other dependencies")
