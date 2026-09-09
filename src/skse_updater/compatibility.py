"""Release-specific SKSE metadata rules, separated from current environment checks.

Rules derived from SKSE v2.2.6 PluginManager::CheckPluginCompatibility:
9398d04592a7eb9d754f2997701116df1022f1b4.
The 1.5 loader invokes Query code, so metadata alone cannot prove that branch.
1.7.99 uses SKSE v2.3.1 (7ff865f4a27d6dc936ab5fd0533ff2d706c8f857).
"""
from .models import Assessment, Binary, Version, unpack_version, version_text

KNOWN_TARGETS = ((1, 5, 97, 0), (1, 6, 1170, 0), (1, 7, 99, 0))
ADDRESS_LIBRARY = 1
SIGNATURES = 2
POST_629 = 4
NO_STRUCTS = 1
V5 = 2


def assess(binary: Binary, target: Version, *, effective: bool | None = True,
           database_present=None) -> Assessment:
    # effective and database_present are retained for callers of the 0.1 API.
    # Dependency availability belongs to the environment, not the runtime matrix.
    if effective is False:
        return Assessment("shadowed", "Another provider wins this DLL path")
    if binary.error:
        return Assessment("review", binary.error)
    if binary.machine != 0x8664:
        return Assessment("incompatible", "Not an AMD64 DLL")
    if not any(name.startswith("SKSEPlugin_") for name in binary.exports):
        return Assessment("helper", "No SKSE entry point; may be an auxiliary DLL")
    declaration = binary.declaration
    if not declaration and target in ((1, 6, 1170, 0), (1, 7, 99, 0)):
        return Assessment("incompatible", "This SKSE loader requires SKSEPlugin_Version metadata")
    if not declaration:
        return Assessment("review", "Legacy/query-only DLL; use author evidence or a hash-bound load observation")
    if declaration.flags & ~7 or declaration.flags_ex & ~3:
        return Assessment("review", "Unknown compatibility flags")
    if target not in KNOWN_TARGETS:
        return Assessment("review", "Runtime is outside the release-specific policy targets")
    if not {"SKSEPlugin_Load", "SKSEPlugin_Preload"}.intersection(binary.exports):
        return Assessment("review", "Metadata present but no SKSE load entry point")
    if target == (1, 5, 97, 0):
        if not {"SKSEPlugin_Query", "SKSEPlugin_Load"}.issubset(binary.exports):
            return Assessment("incompatible", "SKSE 2.0.20 requires both legacy Query and Load entry points")
        return Assessment("review", "1.5.97 invokes Query code; AE metadata cannot prove its result")
    independent = bool(declaration.flags & (ADDRESS_LIBRARY | SIGNATURES))
    newer = target == (1, 7, 99, 0)
    evidence = ["SKSE v2.3.1 loader rules for Skyrim 1.7.99" if newer
                else "SKSE v2.2.6 loader metadata rules for Skyrim 1.6.1170"]
    uncertain_encoding = False
    if newer and declaration.flags & ADDRESS_LIBRARY:
        if declaration.flags_ex & V5:
            evidence.append("Address Library V5 capability explicitly declared")
        elif 520128000 <= binary.timestamp < 1748217600:
            independent = False
            evidence.append(f"COFF timestamp {binary.timestamp}: before 2025-05-26; no V5 flag")
            if target not in declaration.runtimes:
                return Assessment("incompatible", "SKSE 2.3.1 rejects this old Address Library build; recompile/update required", evidence)
        else:
            uncertain_encoding = target not in declaration.runtimes
            evidence.append("No V5 flag; timestamp cannot establish the database decoder capability")
    if independent:
        if not (declaration.flags & POST_629 or declaration.flags_ex & NO_STRUCTS):
            return Assessment("incompatible", "Uses pre-1.6.629 structures; this SKSE loader rejects it", evidence)
        evidence.append("Post-1.6.629 structures declared" if declaration.flags & POST_629
                        else "Declares no structure use / cross-layout compatibility")
        if declaration.flags & ADDRESS_LIBRARY:
            evidence.append("Uses Address Library; the matching database is required")
        if declaration.flags & SIGNATURES:
            evidence.append("Declares signature scanning rather than hardcoded addresses")
    elif target not in declaration.runtimes:
        return Assessment("incompatible", "Explicit runtime declaration excludes this version", evidence)
    else:
        evidence.append("Exact runtime appears in the explicit compatibility list")
    if declaration.minimum_skse:
        evidence.append("Requires SKSE >= " + version_text(unpack_version(declaration.minimum_skse)))
    if uncertain_encoding:
        return Assessment("review", "Loader timestamp heuristic passes, but V5 decoding support is unverified", evidence)
    return Assessment("supported", "Passes this runtime's metadata/structure checks", evidence)


def environment_assessment(binary, runtime_assessment, database, skse_version,
                           *, effective=True, storefront="unknown"):
    evidence = list(runtime_assessment.evidence)
    if runtime_assessment.status != "supported":
        return runtime_assessment
    if binary.declaration.flags & ADDRESS_LIBRARY:
        if database.status in ("missing", "invalid"):
            return Assessment("incompatible", database.reason, evidence)
        if database.status != "valid":
            return Assessment("review", database.reason, evidence)
        evidence.append(database.reason)
    minimum = binary.declaration.minimum_skse
    if minimum:
        if skse_version is None:
            return Assessment("review", "Minimum SKSE cannot be checked against a verified root runtime", evidence)
        if skse_version < unpack_version(minimum):
            return Assessment("incompatible", "Installed SKSE is below the DLL's minimum requirement", evidence)
    if skse_version is None:
        return Assessment("review", "DLL runtime supported; effective SKSE root installation is unverified", evidence)
    if storefront != "steam":
        return Assessment("review", "Runtime metadata passes; storefront is not verified as Steam", evidence)
    if effective is None:
        return Assessment("review", "Runtime metadata passes; effective file origin is unknown", evidence)
    evidence.append("Detected SKSE version " + version_text(skse_version))
    return Assessment("supported", "Runtime declaration and checked local prerequisites pass", evidence)
